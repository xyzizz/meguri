from __future__ import annotations

import json
from pathlib import Path

from meguri.adapters.registry import get_adapter
from meguri.core.artifacts import ArtifactStore
from meguri.core.models import CheckResult, RunContext, RunReport, new_run_id, utc_now
from meguri.evaluators.deterministic import evaluate_step_checks
from meguri.reports.html import render_html_report
from meguri.scenarios.loader import load_scenario


def run_scenario(scenario_path: Path, *, runs_dir: Path) -> RunReport:
    scenario = load_scenario(scenario_path)
    run_id = new_run_id("run")
    artifact_dir = runs_dir / run_id
    store = ArtifactStore(artifact_dir)
    ctx = RunContext(
        run_id=run_id,
        project_path=scenario.project_path,
        artifact_dir=artifact_dir,
        mode=scenario.mode,
        metadata={"scenario_path": str(scenario_path), **scenario.metadata},
    )
    adapter = get_adapter(scenario.adapter)
    started = utc_now()
    steps = []
    all_checks = []
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
            if step.get("stop_on_fail", True) and not result.ok:
                break
    finally:
        adapter.cleanup(ctx)
    status = _overall_status(steps, all_checks)
    report = RunReport(
        run_id=run_id,
        scenario_name=scenario.name,
        status=status,
        started_at=started,
        finished_at=utc_now(),
        project_path=str(scenario.project_path),
        artifact_dir=str(artifact_dir),
        steps=steps,
        checks=all_checks,
        html_report_path=str(artifact_dir / "index.html"),
        metadata=scenario.metadata,
    )
    store.write_json("run.json", report.to_dict())
    store.write_text("report.md", render_markdown_report(report), kind="markdown")
    store.write_text("index.html", render_html_report(report), kind="html")
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
