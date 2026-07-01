from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from meguri.cli.init import handle_init
from meguri.cli.loops import read_loops
from meguri.cli.report import handle_report, open_path
from meguri.cli.validate import validate_scenario_files
from meguri.core.models import utc_now
from meguri.project.pack import find_project_pack, resolve_scenario
from meguri.reports.batch import (
    batch_attention_flags,
    batch_created_resources,
    batch_failed_items,
    batch_failed_loops,
    batch_repair_hints,
    batch_retry_loops,
    batch_status_counts,
    batch_validation_issues,
    failure_groups,
    render_batch_html,
)
from meguri.reports.indexes import render_project_index
from meguri.reports.metrics import (
    extract_attention_flags_from_steps,
    extract_created_resources_from_steps,
    extract_failed_items_from_steps,
    extract_failure_reasons_from_steps,
    extract_run_metrics_from_steps,
    extract_validation_issues_from_steps,
)
from meguri.scenarios.loader import load_scenario
from meguri.scenarios.runner import report_to_json, run_scenario


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="meguri", allow_abbrev=False)
    sub = parser.add_subparsers(dest="cmd", required=True, parser_class=_MeguriArgumentParser)

    init = sub.add_parser("init", help="Initialize Meguri and refresh Meguri agent entrypoints.")
    init.add_argument("--offline", action="store_true", help="Use bundled entrypoint templates instead of fetching from the official repository.")
    init.add_argument("--force", action="store_true", help="Overwrite generated Meguri system files.")

    run = sub.add_parser("run", help="Run one or more targets.")
    run.add_argument("targets", nargs="*", help="Loop aliases/paths, or all for all user-added loops.")
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
    report.add_argument("--refresh", action="store_true", help="Regenerate single-run HTML and Markdown reports from run.json.")

    args = parser.parse_args(argv)
    if args.cmd == "init":
        return handle_init(args)
    if args.cmd == "run":
        try:
            scenario_names = _select_run_targets(args)
            scenario_paths = [resolve_scenario(name) for name in scenario_names]
            runs_dir = Path(args.runs_dir).expanduser().resolve() if args.runs_dir else None
            replay_file = Path(args.replay).expanduser().resolve() if args.replay else None
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        except Exception as exc:  # noqa: BLE001
            print(f"error: {exc}", file=sys.stderr)
            return 1
        errors, warnings = validate_scenario_files(scenario_paths)
        for warning in warnings:
            print(f"warning: {warning}", file=sys.stderr)
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        if errors:
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
                    on_snapshot=_run_snapshot_writer(
                        batch_context,
                        run_reports,
                        started_at=started_at,
                        planned_loops=scenario_names,
                        emit_live=not args.json,
                    ),
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


class _MeguriArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("allow_abbrev", False)
        super().__init__(*args, **kwargs)


def _select_run_targets(args) -> list[str]:
    targets = list(args.targets)
    if not targets:
        raise ValueError("provide a loop name or all")
    if "all" in targets:
        if targets != ["all"]:
            raise ValueError("use either all or explicit loop names, not both")
        pack = find_project_pack(Path.cwd())
        entries = read_loops(pack)
        scenario_names = [entry.loop_id for entry in entries if entry.source == "user"]
        if not scenario_names:
            raise ValueError("no user loops found; ask /meguri to add a loop first")
        return scenario_names
    return targets


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
    created_resources = extract_created_resources_from_steps(report.steps)
    if created_resources:
        summary["created_resources"] = created_resources
        summary["created_resource_count"] = len(created_resources)
    failed_items = extract_failed_items_from_steps(report.steps)
    if failed_items:
        summary["failed_items"] = failed_items
        summary["failed_item_count"] = len(failed_items)
    validation_issues = extract_validation_issues_from_steps(report.steps)
    if validation_issues:
        summary["validation_issues"] = validation_issues
        summary["validation_issue_count"] = len(validation_issues)
    attention_flags = extract_attention_flags_from_steps(report.steps)
    if attention_flags:
        summary["attention_flags"] = attention_flags
        summary["attention_count"] = len(attention_flags)
    return summary


def _running_step_id(report) -> str:
    step = _running_step(report)
    return str(step.step_id) if step else ""


def _running_step(report):
    for step in reversed(report.steps):
        if step.status == "running":
            return step
    return None


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


def _run_snapshot_writer(
    batch_context: dict | None,
    run_reports,
    *,
    started_at: str,
    planned_loops: list[str],
    emit_live: bool,
):
    batch_writer = _batch_snapshot_writer(
        batch_context,
        run_reports,
        started_at=started_at,
        planned_loops=planned_loops,
    )
    live_writer = _live_snapshot_printer() if emit_live else None
    if batch_writer is None and live_writer is None:
        return None

    def write_snapshot(report) -> None:
        if batch_writer is not None:
            batch_writer(report)
        if live_writer is not None:
            live_writer(report)

    return write_snapshot


def _live_snapshot_printer():
    seen: set[tuple[str, str, str, int, int]] = set()

    def print_live_snapshot(report) -> None:
        if report.status != "running":
            return
        step = _running_step(report)
        current_step = str(step.step_id) if step else ""
        if report.steps and not current_step:
            return
        stdout_chars = _live_stream_chars(step, "stdout")
        stderr_chars = _live_stream_chars(step, "stderr")
        key = (str(report.run_id), current_step, str(report.updated_at or ""), stdout_chars, stderr_chars)
        if key in seen:
            return
        seen.add(key)
        print(f"live_loop={_loop_name(report)}", flush=True)
        print(f"live_run_id={report.run_id}", flush=True)
        print(f"live_step={current_step or '-'}", flush=True)
        if report.updated_at:
            print(f"live_updated_at={report.updated_at}", flush=True)
        print(f"live_artifact_dir={report.artifact_dir}", flush=True)
        print(f"live_report={report.html_report_path}", flush=True)
        _print_live_stream(step, "stdout", stdout_chars)
        _print_live_stream(step, "stderr", stderr_chars)

    return print_live_snapshot


def _live_stream_chars(step, kind: str) -> int:
    if step is None:
        return -1
    data = getattr(step, "data", {}) or {}
    value = data.get(f"live_{kind}_chars")
    if isinstance(value, int):
        return value
    text = getattr(step, kind, "")
    return len(text) if isinstance(text, str) else -1


def _print_live_stream(step, kind: str, chars: int) -> None:
    artifact = _live_stream_artifact(step, kind)
    if artifact is None and chars < 0:
        return
    if artifact is not None:
        name = getattr(artifact, "name", "") or getattr(artifact, "path", "")
        path = getattr(artifact, "path", "") or name
        print(f"live_{kind}={name}", flush=True)
        print(f"live_{kind}_path={path}", flush=True)
    if chars >= 0:
        print(f"live_{kind}_chars={chars}", flush=True)


def _live_stream_artifact(step, kind: str):
    if step is None:
        return None
    for artifact in getattr(step, "artifacts", []) or []:
        if getattr(artifact, "kind", "") == kind:
            return artifact
    return None


def _failure_reasons(report) -> list[str]:
    if report.status == "pass":
        return []
    json_reasons = extract_failure_reasons_from_steps(report.steps)
    fallback_reasons: list[str] = []
    for step in report.steps:
        for check in step.checks:
            if check.status not in {"pass", "warning"}:
                fallback_reasons.append(check.message)
        if not fallback_reasons and step.stderr:
            fallback_reasons.append(_last_nonempty_line(step.stderr))
    reasons = json_reasons or fallback_reasons
    return _dedupe_reasons(reasons)


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
    created_resources = batch_created_resources(runs)
    failed_items = batch_failed_items(runs)
    validation_issues = batch_validation_issues(runs)
    attention_flags = batch_attention_flags(runs)
    repair_hints = batch_repair_hints(runs, remaining_loops)
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
        "failure_groups": failure_groups(runs),
        "repair_hints": repair_hints,
        "attention_flags": attention_flags,
        "attention_count": len(attention_flags),
        "created_resources": created_resources,
        "created_resource_count": len(created_resources),
        "failed_items": failed_items,
        "failed_item_count": len(failed_items),
        "validation_issues": validation_issues,
        "validation_issue_count": len(validation_issues),
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
