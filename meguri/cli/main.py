from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from meguri.cli.add import handle_add
from meguri.cli.init import handle_init
from meguri.cli.inspect import handle_inspect
from meguri.cli.loops import handle_delete, handle_loops, read_loops
from meguri.cli.report import handle_report, open_path
from meguri.cli.validate import handle_validate
from meguri.core.models import utc_now
from meguri.evaluators.deterministic import extract_last_json
from meguri.project.pack import find_project_pack, resolve_scenario, slugify
from meguri.reports.batch import (
    batch_failed_loops,
    batch_retry_command,
    batch_retry_loops,
    batch_status_counts,
    failure_groups,
    render_batch_html,
)
from meguri.reports.indexes import render_project_index
from meguri.reports.metrics import extract_run_metrics_from_steps
from meguri.scenarios.loader import load_scenario
from meguri.scenarios.runner import report_to_json, run_scenario


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="meguri")
    sub = parser.add_subparsers(dest="cmd", required=True)

    init = sub.add_parser("init", help="Initialize a Meguri project pack in the current project.")
    init.add_argument("--install-skills", action="store_true", help="Install repo-local Codex and Claude Code skills.")
    init.add_argument("--force", action="store_true", help="Overwrite generated files.")

    sub.add_parser("inspect", help="Print the Meguri inspection spec for the current Codex or Claude Code agent.")

    add = sub.add_parser("add", help="Add a verification loop when enough deterministic information is provided.")
    add.add_argument("description", help="Natural-language description of the loop to close.")
    add.add_argument("--name", help="Loop file/name. Defaults to a slug from the description.")
    add.add_argument("--command", help="Safe execution entry for this loop.")
    add.add_argument("--pass-criteria", help="Deterministic evidence that proves success.")
    add.add_argument("--forbid", action="append", default=[], help="Forbidden side effect or output text. Can be repeated.")
    add.add_argument("--mode", choices=["dry_run", "execute"], default="dry_run")
    add.add_argument("--allow-execute", action="store_true", help="Confirm execute mode for this loop.")
    add.add_argument("--timeout-seconds", type=float, default=300)
    add.add_argument("--force", action="store_true", help="Overwrite an existing loop.")

    loops = sub.add_parser("loops", help="List user-added loops.")
    loops.add_argument("--all", action="store_true", help="Include system loops such as smoke.")
    loops.add_argument("--json", action="store_true", help="Print clean JSON.")

    delete = sub.add_parser("delete", help="Delete a named user-added loop.")
    delete.add_argument("name", help="Loop name or alias to delete.")
    delete.add_argument("--force", action="store_true", help="Allow deleting system loops.")
    delete.add_argument("--dry-run", action="store_true", help="Show what would be deleted.")

    validate_pack = sub.add_parser("validate", help="Validate a project pack or loop.")
    validate_pack.add_argument("target", nargs="?", help="Loop alias/path. Defaults to the current project pack.")

    validate_scenario = sub.add_parser("validate-scenario", help="Compatibility alias: load and validate a scenario file.")
    validate_scenario.add_argument("scenario")

    run = sub.add_parser("run", help="Run one or more loops.")
    run.add_argument("scenarios", nargs="*", help="Loop aliases/paths. Defaults to smoke.")
    run.add_argument("--all", dest="run_all", action="store_true", help="Run all user-added loops sequentially.")
    run.add_argument("--exclude", action="append", default=[], help="Skip a loop when using --all. Can be repeated.")
    run.add_argument("--include-system", action="store_true", help="Include system loops such as smoke when using --all.")
    run.add_argument("--runs-dir")
    run.add_argument("--replay")
    run.add_argument("--retry-of")
    run.add_argument("--allow-execute", action="store_true", help="Confirm execute-mode loops for this run.")
    run.add_argument("--json", action="store_true")
    run.add_argument("--open", action="store_true", help="Open the generated HTML report.")

    report = sub.add_parser("report", help="Show or open an existing HTML run report.")
    report.add_argument("run_id", nargs="?")
    report.add_argument("--last", action="store_true", help="Select the newest run report.")
    report.add_argument("--recent", type=int, help="Create a batch report from the newest N standalone run reports.")
    report.add_argument("--runs", nargs="+", help="Create a batch report from explicit run ids or report paths.")
    report.add_argument("--loops", nargs="+", help="Create a batch report from the newest run for each named loop.")
    report.add_argument("--running", action="store_true", help="List run and batch reports that are currently marked running.")
    report.add_argument("--json", action="store_true", help="Print clean JSON when creating a batch report.")
    report.add_argument("--open", action="store_true", help="Open the report.")

    args = parser.parse_args(argv)
    if args.cmd == "init":
        return handle_init(args)
    if args.cmd == "inspect":
        return handle_inspect(args)
    if args.cmd == "add":
        return handle_add(args)
    if args.cmd == "loops":
        return handle_loops(args)
    if args.cmd == "delete":
        return handle_delete(args)
    if args.cmd == "validate":
        return handle_validate(args)
    if args.cmd == "validate-scenario":
        scenario = load_scenario(Path(args.scenario))
        print(json.dumps({
            "name": scenario.name,
            "adapter": scenario.adapter,
            "project_path": str(scenario.project_path),
            "mode": scenario.mode,
            "steps": len(scenario.steps),
        }, ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "run":
        try:
            scenario_names = _select_run_targets(args)
            scenario_paths = [resolve_scenario(name) for name in scenario_names]
            runs_dir = Path(args.runs_dir).expanduser().resolve() if args.runs_dir else None
            replay_file = Path(args.replay).expanduser().resolve() if args.replay else None
        except Exception as exc:  # noqa: BLE001
            print(f"error: {exc}", file=sys.stderr)
            return 1
        execute_loops = _execute_loop_names(scenario_paths)
        if execute_loops and not args.allow_execute:
            print(
                "error: execute-mode loops require explicit user approval; rerun with "
                f"--allow-execute after confirmation: {', '.join(execute_loops)}",
                file=sys.stderr,
            )
            return 2
        run_reports = []
        started_at = utc_now()
        batch_context = (
            _create_batch_context(scenario_paths[0], allow_execute=args.allow_execute)
            if len(scenario_paths) > 1
            else None
        )
        batch = (
            _write_batch_report(
                batch_context,
                run_reports,
                started_at=started_at,
                planned_loops=scenario_names,
                status="running",
            )
            if batch_context
            else None
        )
        try:
            for scenario_path in scenario_paths:
                run_report = run_scenario(
                    scenario_path,
                    runs_dir=runs_dir,
                    replay_file=replay_file,
                    retry_of=args.retry_of,
                    on_snapshot=_batch_snapshot_writer(
                        batch_context,
                        run_reports,
                        started_at=started_at,
                        planned_loops=scenario_names,
                    ) if batch_context else None,
                )
                run_reports.append(run_report)
                if batch_context and len(run_reports) < len(scenario_paths):
                    batch = _write_batch_report(
                        batch_context,
                        run_reports,
                        started_at=started_at,
                        planned_loops=scenario_names,
                        status="running",
                    )
        except BaseException as exc:
            if batch_context:
                _write_batch_report(
                    batch_context,
                    run_reports,
                    started_at=started_at,
                    planned_loops=scenario_names,
                    status="blocked",
                    finished_at=utc_now(),
                    interruption={
                        "type": type(exc).__name__,
                        "message": str(exc),
                    },
                )
            raise
        if batch_context:
            batch = _write_batch_report(
                batch_context,
                run_reports,
                started_at=started_at,
                planned_loops=scenario_names,
                status=_batch_status(run_reports),
                finished_at=utc_now(),
            )
        if args.json and len(run_reports) == 1:
            print(report_to_json(run_reports[0]))
        elif args.json:
            print(json.dumps(batch, ensure_ascii=False, indent=2, default=str))
        else:
            for run_report in run_reports:
                if len(run_reports) > 1:
                    print(f"loop={_loop_name(run_report)}")
                print(f"run_id={run_report.run_id}")
                print(f"status={run_report.status}")
                print(f"artifact_dir={run_report.artifact_dir}")
                print(f"html_report={run_report.html_report_path}")
            if len(run_reports) > 1:
                print(f"batch_status={batch['status']}")
                print(f"batch_report={batch['html_report_path']}")
        if args.open:
            target_path = Path(batch["html_report_path"]) if batch else Path(run_reports[-1].html_report_path)
            if not open_path(target_path):
                print(f"could not open report automatically: {target_path}", file=sys.stderr)
        return 0 if _batch_status(run_reports) == "pass" else 1
    if args.cmd == "report":
        return handle_report(args)
    return 2


def _select_run_targets(args) -> list[str]:
    if args.run_all and args.scenarios:
        raise ValueError("use either explicit loop names or --all, not both")
    if args.include_system and not args.run_all:
        raise ValueError("--include-system can only be used with --all")
    if args.run_all:
        pack = find_project_pack(Path.cwd())
        entries = read_loops(pack)
        if not args.include_system:
            entries = [entry for entry in entries if entry.source == "user"]
        scenario_names = [entry.loop_id for entry in entries]
    else:
        scenario_names = args.scenarios or ["smoke"]
    if args.exclude:
        raw_excludes = {str(value) for value in args.exclude}
        normalized_excludes = {slugify(str(value), fallback=str(value)) for value in args.exclude}
        scenario_names = [
            name for name in scenario_names
            if name not in raw_excludes and slugify(name, fallback=name) not in normalized_excludes
        ]
    if not scenario_names:
        raise ValueError("no loops selected")
    return scenario_names


def _execute_loop_names(scenario_paths: list[Path]) -> list[str]:
    names = []
    for scenario_path in scenario_paths:
        scenario = load_scenario(scenario_path)
        if scenario.mode == "execute":
            names.append(str(scenario.metadata.get("loop_id") or scenario.name))
    return names


def _batch_status(run_reports) -> str:
    if not run_reports:
        return "blocked"
    if any(report.status == "fail" for report in run_reports):
        return "fail"
    if any(report.status == "blocked" for report in run_reports):
        return "blocked"
    if any(report.status == "warning" for report in run_reports):
        return "warning"
    if any(report.status == "running" for report in run_reports):
        return "running"
    return "pass"


def _run_summary(report) -> dict:
    failure_reasons = _failure_reasons(report)
    summary = {
        "loop": _loop_name(report),
        "run_id": report.run_id,
        "status": report.status,
        "mode": str(getattr(report, "mode", "") or ""),
        "artifact_dir": report.artifact_dir,
        "html_report_path": report.html_report_path,
        "summary": "; ".join(failure_reasons) if failure_reasons else report.status,
        "failure_reasons": failure_reasons,
    }
    metrics = extract_run_metrics_from_steps(report.steps)
    if metrics:
        summary["metrics"] = metrics
    return summary


def _running_step_id(report) -> str:
    for step in reversed(report.steps):
        if step.status == "running":
            return step.step_id
    return ""


def _batch_snapshot_writer(
    batch_context: dict | None,
    run_reports,
    *,
    started_at: str,
    planned_loops: list[str],
):
    if not batch_context:
        return None

    def write_current_snapshot(report) -> None:
        if report.status != "running":
            return
        _write_batch_report(
            batch_context,
            run_reports,
            started_at=started_at,
            planned_loops=planned_loops,
            status="running",
            current_run=report,
        )

    return write_current_snapshot


def _failure_reasons(report) -> list[str]:
    if report.status == "pass":
        return []
    json_reasons: list[str] = []
    fallback_reasons: list[str] = []
    for step in report.steps:
        if step.stdout:
            try:
                json_reasons.extend(_json_failure_reasons(extract_last_json(step.stdout)))
            except ValueError:
                pass
        for check in step.checks:
            if check.status not in {"pass", "warning"}:
                fallback_reasons.append(check.message)
        if not fallback_reasons and step.stderr:
            fallback_reasons.append(_last_nonempty_line(step.stderr))
    reasons = json_reasons or fallback_reasons
    return _dedupe_reasons(reasons)


def _json_failure_reasons(value) -> list[str]:
    reasons: list[str] = []
    if isinstance(value, dict):
        reasons.extend(_string_list(value.get("failure_reasons")))
        reasons.extend(_string_list(value.get("errors")))
        if isinstance(value.get("error"), str):
            reasons.append(value["error"])
        for key in ("submit_results", "tool_results", "results", "items", "failed_submit_items"):
            reasons.extend(_failed_item_reasons(value.get(key)))
    return reasons


def _failed_item_reasons(value) -> list[str]:
    if not isinstance(value, list):
        return []
    reasons: list[str] = []
    for item in value:
        if isinstance(item, str):
            reasons.append(item)
            continue
        if not isinstance(item, dict):
            continue
        ok = item.get("ok")
        status = str(item.get("status") or item.get("result") or "").lower()
        failed = ok is False or status in {"fail", "failed", "error", "blocked"}
        if not failed and not item.get("error"):
            continue
        for key in ("error", "message", "reason"):
            if isinstance(item.get(key), str):
                reasons.append(item[key])
        result = item.get("result")
        if isinstance(result, dict):
            for key in ("error", "message", "reason"):
                if isinstance(result.get(key), str):
                    reasons.append(result[key])
    return reasons


def _string_list(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _last_nonempty_line(value: str) -> str:
    for line in reversed(value.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return value.strip()


def _dedupe_reasons(values: list[str], *, limit: int = 5) -> list[str]:
    reasons: list[str] = []
    seen: set[str] = set()
    for value in values:
        reason = " ".join(str(value).split())
        if not reason or reason in seen:
            continue
        seen.add(reason)
        reasons.append(reason[:500])
        if len(reasons) >= limit:
            break
    return reasons


def _create_batch_context(first_scenario_path: Path, *, allow_execute: bool = False) -> dict:
    pack = find_project_pack(first_scenario_path.parent)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    batch_dir = pack.pack_root / "batches" / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    return {"pack": pack, "batch_id": batch_id, "batch_dir": batch_dir, "allow_execute": allow_execute}


def _batch_current_loop(
    remaining_loops: list[str],
    *,
    status: str,
    interruption: dict | None,
    current_run_summary: dict | None,
) -> str:
    if current_run_summary is not None:
        return str(current_run_summary["loop"])
    if remaining_loops and (status == "running" or interruption):
        return remaining_loops[0]
    return ""


def _write_batch_report(
    batch_context: dict,
    run_reports,
    *,
    started_at: str,
    planned_loops: list[str],
    status: str,
    finished_at: str | None = None,
    interruption: dict | None = None,
    current_run=None,
) -> dict:
    pack = batch_context["pack"]
    batch_id = batch_context["batch_id"]
    batch_dir = batch_context["batch_dir"]
    runs = [_run_summary(report) for report in run_reports]
    completed = len(runs)
    remaining_loops = planned_loops[completed:]
    retry_loops = batch_retry_loops(runs, remaining_loops)
    current_run_summary = _run_summary(current_run) if current_run is not None else None
    if current_run_summary is not None:
        current_step = _running_step_id(current_run)
        if current_step:
            current_run_summary["current_step"] = current_step
    record = {
        "batch_id": batch_id,
        "status": status,
        "started_at": started_at,
        "updated_at": utc_now(),
        "finished_at": finished_at or "",
        "batch_dir": str(batch_dir),
        "html_report_path": str(batch_dir / "index.html"),
        "planned_loops": planned_loops,
        "completed_loops": completed,
        "total_loops": len(planned_loops),
        "current_loop": _batch_current_loop(
            remaining_loops,
            status=status,
            interruption=interruption,
            current_run_summary=current_run_summary,
        ),
        "remaining_loops": remaining_loops,
        "status_counts": batch_status_counts(runs),
        "failed_loops": batch_failed_loops(runs),
        "retry_loops": retry_loops,
        "retry_command": batch_retry_command(
            runs,
            remaining_loops,
            allow_execute=bool(batch_context.get("allow_execute")),
        ),
        "failure_groups": failure_groups(runs),
        "runs": runs,
    }
    if current_run_summary is not None:
        record["current_run"] = current_run_summary
    if interruption:
        record["interrupted"] = True
        record["interruption"] = interruption
    batch_dir.joinpath("batch.json").write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    batch_dir.joinpath("index.html").write_text(render_batch_html(record, batch_dir), encoding="utf-8")
    pack.pack_root.joinpath("index.html").write_text(render_project_index(pack.pack_root), encoding="utf-8")
    return record


def _loop_name(report) -> str:
    return str(report.metadata.get("loop_id") or report.scenario_name)


if __name__ == "__main__":
    raise SystemExit(main())
