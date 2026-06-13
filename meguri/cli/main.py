from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from meguri.cli.add import handle_add
from meguri.cli.init import handle_init
from meguri.cli.inspect import handle_inspect
from meguri.cli.loops import handle_delete, handle_loops
from meguri.cli.report import handle_report, open_path
from meguri.cli.validate import handle_validate
from meguri.project.pack import resolve_scenario
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

    run = sub.add_parser("run", help="Run a loop.")
    run.add_argument("scenario", nargs="?", default="smoke")
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
            scenario_path = resolve_scenario(args.scenario)
            runs_dir = Path(args.runs_dir).expanduser().resolve() if args.runs_dir else None
            replay_file = Path(args.replay).expanduser().resolve() if args.replay else None
        except Exception as exc:  # noqa: BLE001
            print(f"error: {exc}", file=sys.stderr)
            return 1
        run_report = run_scenario(scenario_path, runs_dir=runs_dir, replay_file=replay_file, retry_of=args.retry_of)
        if args.json:
            print(report_to_json(run_report))
        else:
            print(f"run_id={run_report.run_id}")
            print(f"status={run_report.status}")
            print(f"artifact_dir={run_report.artifact_dir}")
            print(f"html_report={run_report.html_report_path}")
        if args.open:
            if not open_path(Path(run_report.html_report_path)):
                print(f"could not open report automatically: {run_report.html_report_path}", file=sys.stderr)
        return 0 if run_report.status == "pass" else 1
    if args.cmd == "report":
        return handle_report(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
