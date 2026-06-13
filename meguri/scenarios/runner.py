from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from meguri.adapters.registry import get_adapter
from meguri.core.artifacts import ArtifactStore
from meguri.core.evidence import collect_evidence
from meguri.core.models import CheckResult, RunContext, RunReport, utc_now
from meguri.core.replay import build_replay_bundle
from meguri.evaluators.deterministic import evaluate_step_checks
from meguri.project.pack import find_project_pack
from meguri.reports.html import render_html_report
from meguri.reports.indexes import write_indexes
from meguri.scenarios.loader import load_scenario


def run_scenario(
    scenario_path: Path,
    *,
    runs_dir: Path | None = None,
    replay_file: Path | None = None,
    retry_of: str | None = None,
) -> RunReport:
    scenario_path = scenario_path.resolve()
    scenario = load_scenario(scenario_path)
    loop_id = str(scenario.metadata.get("loop_id") or scenario.name)
    run_id = _new_loop_run_id()
    artifact_dir = _artifact_dir_for(scenario_path, loop_id=loop_id, run_id=run_id, runs_dir=runs_dir)
    store = ArtifactStore(artifact_dir)
    evidence_dir = artifact_dir / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    started_dt = datetime.now(timezone.utc)
    ctx = RunContext(
        run_id=run_id,
        project_path=scenario.project_path,
        artifact_dir=artifact_dir,
        mode=scenario.mode,
        env={
            "MEGURI_RUN_ID": run_id,
            "MEGURI_LOOP_ID": loop_id,
            "MEGURI_RUN_DIR": str(artifact_dir),
            "MEGURI_ARTIFACT_DIR": str(artifact_dir),
            "MEGURI_EVIDENCE_DIR": str(evidence_dir),
            **({"MEGURI_REPLAY_FILE": str(replay_file)} if replay_file else {}),
        },
        metadata={"scenario_path": str(scenario_path), "loop_id": loop_id, **scenario.metadata},
    )
    adapter = get_adapter(scenario.adapter)
    started = started_dt.isoformat()
    steps = []
    all_checks = []
    _write_run_snapshot(
        store=store,
        scenario=scenario,
        scenario_path=scenario_path,
        artifact_dir=artifact_dir,
        evidence_dir=evidence_dir,
        loop_id=loop_id,
        run_id=run_id,
        started=started,
        started_dt=started_dt,
        steps=steps,
        all_checks=all_checks,
        status="running",
        replay_file=replay_file,
        retry_of=retry_of,
        runs_dir=runs_dir,
    )
    try:
        adapter.setup(ctx)
        for step in scenario.steps:
            result = adapter.run_step(step, ctx)
            result.artifacts.extend([
                store.write_text(f"steps/{result.step_id}/stdout.txt", result.stdout, kind="stdout"),
                store.write_text(f"steps/{result.step_id}/stderr.txt", result.stderr, kind="stderr"),
                store.write_json(f"steps/{result.step_id}/result.json", {
                    "status": result.status,
                    "exit_code": result.exit_code,
                    "data": result.data,
                }),
            ])
            if result.status == "blocked":
                result.checks = [
                    CheckResult(
                        id=f"{result.step_id}_blocked",
                        status="blocked",
                        message="step blocked before checks; inspect stderr artifact",
                    )
                ]
            else:
                result.checks = evaluate_step_checks(result, list(step.get("checks") or []))
            all_checks.extend(result.checks)
            steps.append(result)
            _write_run_snapshot(
                store=store,
                scenario=scenario,
                scenario_path=scenario_path,
                artifact_dir=artifact_dir,
                evidence_dir=evidence_dir,
                loop_id=loop_id,
                run_id=run_id,
                started=started,
                started_dt=started_dt,
                steps=steps,
                all_checks=all_checks,
                status="running",
                replay_file=replay_file,
                retry_of=retry_of,
                runs_dir=runs_dir,
            )
            if step.get("stop_on_fail", True) and not result.ok:
                break
    finally:
        adapter.cleanup(ctx)
    status = _overall_status(steps, all_checks)
    return _write_run_snapshot(
        store=store,
        scenario=scenario,
        scenario_path=scenario_path,
        artifact_dir=artifact_dir,
        evidence_dir=evidence_dir,
        loop_id=loop_id,
        run_id=run_id,
        started=started,
        started_dt=started_dt,
        steps=steps,
        all_checks=all_checks,
        status=status,
        replay_file=replay_file,
        retry_of=retry_of,
        runs_dir=runs_dir,
    )


def _write_run_snapshot(
    *,
    store: ArtifactStore,
    scenario,
    scenario_path: Path,
    artifact_dir: Path,
    evidence_dir: Path,
    loop_id: str,
    run_id: str,
    started: str,
    started_dt: datetime,
    steps: list,
    all_checks: list,
    status: str,
    replay_file: Path | None,
    retry_of: str | None,
    runs_dir: Path | None,
) -> RunReport:
    evidence = collect_evidence(
        run_evidence_dir=evidence_dir,
        project_evidence_dir=_project_evidence_dir(scenario_path),
        loop_id=loop_id,
        run_id=run_id,
        run_started_at=started_dt,
        run_dir=artifact_dir,
    )
    replay = build_replay_bundle(
        source_run_id=run_id,
        loop_id=loop_id,
        scenario_path=scenario_path,
        command=_first_command(steps, scenario.steps),
        evidence_files=[path.relative_to(artifact_dir) for path in sorted(evidence_dir.glob("*.json"))],
        replay_source=str(replay_file) if replay_file else None,
        retry_of=retry_of,
    )
    report = RunReport(
        run_id=run_id,
        scenario_name=scenario.name,
        status=status,
        started_at=started,
        finished_at=utc_now(),
        project_path=str(scenario.project_path),
        artifact_dir=str(artifact_dir),
        steps=list(steps),
        checks=list(all_checks),
        html_report_path=str(artifact_dir / "index.html"),
        metadata=scenario.metadata,
        evidence=evidence.bundles,
        evidence_warnings=evidence.warnings,
        replay=replay,
        legacy_artifact_dir=str(runs_dir) if runs_dir else "",
    )
    store.write_json("replay.json", replay)
    store.write_json("run.json", report.to_dict())
    store.write_text("report.md", render_markdown_report(report), kind="markdown")
    store.write_text("index.html", render_html_report(report), kind="html")
    _write_history_indexes(artifact_dir)
    return report


def render_markdown_report(report: RunReport) -> str:
    loop_name = _loop_name(report)
    lines = [
        f"# Meguri Loop Run: {loop_name}",
        "",
        f"- run_id: `{report.run_id}`",
        f"- loop: `{loop_name}`",
        f"- status: `{report.status}`",
        f"- project: `{report.project_path}`",
        f"- artifacts: `{report.artifact_dir}`",
        "",
        "## Steps",
        "",
    ]
    for step in report.steps:
        lines.extend([
            f"### {step.step_id}",
            "",
            f"- status: `{step.status}`",
            f"- exit_code: `{step.exit_code}`",
            f"- started_at: `{step.started_at}`",
            f"- finished_at: `{step.finished_at}`",
            "",
            "| Check | Status | Message |",
            "| --- | --- | --- |",
        ])
        for check in step.checks:
            lines.append(f"| `{check.id}` | `{check.status}` | {check.message} |")
        if not step.checks:
            lines.append("| - | - | no checks |")
        lines.append("")
    return "\n".join(lines)


def report_to_json(report: RunReport) -> str:
    return json.dumps(report.to_dict(), ensure_ascii=False, indent=2, default=str)


def _loop_name(report: RunReport) -> str:
    return str(report.metadata.get("loop_id") or report.scenario_name)


def _overall_status(steps, checks):
    if not steps:
        return "blocked"
    if any(step.status == "fail" for step in steps) or any(check.status == "fail" for check in checks):
        return "fail"
    if any(step.status == "blocked" for step in steps) or any(check.status == "blocked" for check in checks):
        return "blocked"
    return "pass"


def _new_loop_run_id() -> str:
    base = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base


def _artifact_dir_for(scenario_path: Path, *, loop_id: str, run_id: str, runs_dir: Path | None) -> Path:
    if runs_dir is not None:
        return runs_dir / run_id
    if scenario_path.name == "_loop.yaml" and scenario_path.parent.parent.name == "loops":
        candidate = scenario_path.parent / run_id
        if not candidate.exists():
            return candidate
        suffix = datetime.now().strftime("%f")[:4]
        return scenario_path.parent / f"{run_id}_{suffix}"
    pack = find_project_pack(scenario_path.parent)
    return pack.runs_dir / run_id


def _project_evidence_dir(scenario_path: Path) -> Path:
    try:
        pack = find_project_pack(scenario_path.parent)
    except FileNotFoundError:
        return scenario_path.parent / ".meguri" / "evidence"
    return pack.pack_root / "evidence"


def _first_command(steps, raw_steps: list[dict]) -> list[str] | None:
    for step in steps:
        command = step.data.get("command") if isinstance(step.data, dict) else None
        if isinstance(command, list):
            return [str(part) for part in command]
    for raw in raw_steps:
        command = raw.get("command")
        if isinstance(command, list):
            return [str(part) for part in command]
    return None


def _write_history_indexes(artifact_dir: Path) -> None:
    loop_dir = artifact_dir.parent
    loops_dir = loop_dir.parent
    pack_root = loops_dir.parent
    if loops_dir.name != "loops":
        return
    write_indexes(pack_root, loop_dir)
