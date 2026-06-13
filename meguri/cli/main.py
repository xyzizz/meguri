from __future__ import annotations

import argparse
import html
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from meguri.cli.add import handle_add
from meguri.cli.init import handle_init
from meguri.cli.inspect import handle_inspect
from meguri.cli.loops import handle_delete, handle_loops
from meguri.cli.report import handle_report, open_path
from meguri.cli.validate import handle_validate
from meguri.core.models import utc_now
from meguri.project.pack import find_project_pack, resolve_scenario
from meguri.reports.indexes import render_project_index
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
    run.add_argument("--runs-dir")
    run.add_argument("--replay")
    run.add_argument("--retry-of")
    run.add_argument("--json", action="store_true")
    run.add_argument("--open", action="store_true", help="Open the generated HTML report.")

    report = sub.add_parser("report", help="Show or open an existing HTML run report.")
    report.add_argument("run_id", nargs="?")
    report.add_argument("--last", action="store_true", help="Select the newest run report.")
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
            scenario_names = args.scenarios or ["smoke"]
            scenario_paths = [resolve_scenario(name) for name in scenario_names]
            runs_dir = Path(args.runs_dir).expanduser().resolve() if args.runs_dir else None
            replay_file = Path(args.replay).expanduser().resolve() if args.replay else None
        except Exception as exc:  # noqa: BLE001
            print(f"error: {exc}", file=sys.stderr)
            return 1
        run_reports = []
        started_at = utc_now()
        for scenario_path in scenario_paths:
            run_report = run_scenario(scenario_path, runs_dir=runs_dir, replay_file=replay_file, retry_of=args.retry_of)
            run_reports.append(run_report)
        batch = _write_batch_report(scenario_paths[0], run_reports, started_at=started_at) if len(run_reports) > 1 else None
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


def _run_summary(report) -> dict[str, str]:
    return {
        "loop": _loop_name(report),
        "run_id": report.run_id,
        "status": report.status,
        "artifact_dir": report.artifact_dir,
        "html_report_path": report.html_report_path,
    }


def _write_batch_report(first_scenario_path: Path, run_reports, *, started_at: str) -> dict:
    pack = find_project_pack(first_scenario_path.parent)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    batch_dir = pack.pack_root / "batches" / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    record = {
        "batch_id": batch_id,
        "status": _batch_status(run_reports),
        "started_at": started_at,
        "finished_at": utc_now(),
        "batch_dir": str(batch_dir),
        "html_report_path": str(batch_dir / "index.html"),
        "runs": [_run_summary(report) for report in run_reports],
    }
    batch_dir.joinpath("batch.json").write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    batch_dir.joinpath("index.html").write_text(_render_batch_html(record, batch_dir), encoding="utf-8")
    pack.pack_root.joinpath("index.html").write_text(render_project_index(pack.pack_root), encoding="utf-8")
    return record


def _render_batch_html(record: dict, batch_dir: Path) -> str:
    rows = []
    for index, run in enumerate(record["runs"], start=1):
        report_path = Path(run["html_report_path"])
        href = os.path.relpath(report_path, batch_dir)
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{html.escape(run['loop'])}</td>"
            f"<td>{html.escape(run['status'])}</td>"
            f"<td>{html.escape(run['run_id'])}</td>"
            f"<td><a href=\"{html.escape(href)}\">Open report</a></td>"
            "</tr>"
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Meguri Batch {html.escape(record['batch_id'])}</title>"
        "<style>"
        "body{font:14px/1.5 system-ui,sans-serif;margin:32px;color:#1d2430}"
        "main{max-width:980px;margin:0 auto}"
        ".status{font-weight:700;text-transform:uppercase}"
        "table{border-collapse:collapse;width:100%;margin-top:18px}"
        "th,td{border-bottom:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}"
        "a{color:#8a3b12;text-underline-offset:3px}"
        "</style></head><body><main>"
        f"<h1>Meguri Batch {html.escape(record['batch_id'])}</h1>"
        f"<p>Status: <span class=\"status\">{html.escape(record['status'])}</span></p>"
        f"<p>Started: {html.escape(record['started_at'])}<br>Finished: {html.escape(record['finished_at'])}</p>"
        "<table><thead><tr><th>#</th><th>Loop</th><th>Status</th><th>Run</th><th>Report</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></main></body></html>"
    )


def _loop_name(report) -> str:
    return str(report.metadata.get("loop_id") or report.scenario_name)


if __name__ == "__main__":
    raise SystemExit(main())
