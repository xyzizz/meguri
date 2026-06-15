from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

from meguri.cli.inspect import write_inspect_spec
from meguri.project.pack import load_project_pack, pack_root_for


def handle_init(args: Any) -> int:
    project_root = Path.cwd().resolve()
    pack_root = pack_root_for(project_root)
    created: list[Path] = []
    skipped: list[Path] = []
    force = bool(getattr(args, "force", False))

    created.extend(_write_pack(project_root, pack_root, force=force, skipped=skipped))
    created.extend(write_skills(project_root, force=force, skipped=skipped))
    pack = load_project_pack(project_root)
    prompt_path, prompt = write_inspect_spec(pack)

    for path in created:
        print(f"created {_display_path(project_root, path)}")
    for path in skipped:
        print(f"exists  {_display_path(project_root, path)}")
    if not created and skipped:
        print("no changes; pass --force to overwrite generated files")
    print(f"meguri: wrote {_display_path(project_root, prompt_path)}", file=sys.stderr)
    print(prompt)
    return 0


def _write_pack(project_root: Path, pack_root: Path, *, force: bool, skipped: list[Path]) -> list[Path]:
    smoke_command, smoke_checks = _detect_smoke(project_root)
    smoke_base = {
        "name": f"{_safe_name(project_root.name)}_smoke",
        "adapter": "shell",
        "mode": "dry_run",
        "metadata": {
            "kind": "loop",
            "loop_id": "smoke",
            "source": "system",
            "objective": "Verify the project can run a safe smoke command under Meguri.",
            "completion_chain": [
                "verify",
                "collect_evidence",
                "repair_when_safe",
                "rerun",
                "pass_block_or_ask",
            ],
            "forbidden_side_effects": [
                "submit",
                "deploy",
                "payment",
                "production write",
                "external send",
            ],
        },
        "steps": [
            {
                "id": "smoke",
                "command": smoke_command,
                "timeout_seconds": 300,
                "checks": smoke_checks,
            }
        ],
    }
    loop_smoke = {"project_path": "../../..", **smoke_base}
    legacy_smoke = {"project_path": "../..", **smoke_base}
    files = {
        pack_root / "project.yaml": yaml.safe_dump(
            {
                "version": 1,
                "name": project_root.name,
                "project_path": ".",
                "runs_dir": ".meguri/runs",
                "default_scenario": "smoke",
            },
            sort_keys=False,
            allow_unicode=True,
        ),
        pack_root / "loops" / "smoke" / "_loop.yaml": yaml.safe_dump(
            loop_smoke,
            sort_keys=False,
            allow_unicode=True,
        ),
        pack_root / "loops" / "smoke" / "_scripts" / ".gitkeep": "",
        pack_root / "scenarios" / "smoke.yaml": yaml.safe_dump(
            legacy_smoke,
            sort_keys=False,
            allow_unicode=True,
        ),
        pack_root / "README.md": _pack_readme(project_root.name),
    }
    created: list[Path] = []
    for path, text in files.items():
        written = _write_if_allowed(path, text, force=force, skipped=skipped)
        if written is not None:
            created.append(written)
    return created


def write_skills(project_root: Path, *, force: bool, skipped: list[Path]) -> list[Path]:
    files = {
        project_root / ".agents" / "skills" / "meguri" / "SKILL.md": _codex_skill(),
        project_root / ".claude" / "skills" / "meguri" / "SKILL.md": _claude_skill(),
        project_root / ".claude" / "commands" / "meguri.md": _claude_command(),
        Path.home() / ".codex" / "prompts" / "meguri.md": _codex_slash_prompt(),
    }
    created: list[Path] = []
    for path, text in files.items():
        written = _write_if_allowed(path, text, force=force, skipped=skipped)
        if written is not None:
            created.append(written)
    return created


def _write_if_allowed(path: Path, text: str, *, force: bool, skipped: list[Path]) -> Path | None:
    if path.exists() and not force:
        skipped.append(path)
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)


def _detect_smoke(project_root: Path) -> tuple[list[str], list[dict[str, Any]]]:
    package_json = project_root / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
        if isinstance(data, dict) and isinstance(data.get("scripts"), dict) and "test" in data["scripts"]:
            return ["npm", "test"], [{"id": "exit", "type": "exit_code", "equals": 0}]

    if (project_root / "pyproject.toml").exists() or (project_root / "tests").is_dir():
        return [sys.executable, "-m", "pytest", "-q"], [{"id": "exit", "type": "exit_code", "equals": 0}]

    return [
        sys.executable,
        "-c",
        "import json; print(json.dumps({'passed': True}))",
    ], [
        {"id": "exit", "type": "exit_code", "equals": 0},
        {"id": "passed", "type": "stdout_json_path", "path": "$.passed", "equals": True},
    ]


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() else "_" for char in value.lower()).strip("_") or "project"


def _pack_readme(project_name: str) -> str:
    return f"""# Meguri Pack

This directory contains the Meguri project pack for `{project_name}`.

Meguri's user-facing unit is a loop: a verification goal that can move from
check, to evidence, to safe repair, to rerun, and finally pass, blocked, or
needs-confirmation. New loops live under `.meguri/loops/<loop_id>/_loop.yaml`,
and each run writes history under `.meguri/loops/<loop_id>/<run_id>/`. Legacy
`.meguri/scenarios/*.yaml` files remain runnable, but new records are written
into the loop history structure. Multi-loop sequential runs write aggregate
records under `.meguri/batches/<batch_id>/`.
During a run, `timeline.ndjson` is appended as each step advances, and
`run.json`, `report.md`, and `index.html` are refreshed when the loop starts,
when a step starts, when shell stdout/stderr advances, on silent-step
heartbeats, and when a step finishes. `run.json.updated_at` changes on every
snapshot refresh. If a run is interrupted, Meguri records the active step as
blocked, appends a
`run_interrupted` timeline event, and leaves the report readable. Replay
metadata records the run-local `replay.json` status and pre-run project state;
after repair, rerun the named loop directly instead of copying a generated
replay command.
In normal text mode, `meguri run` prints `live_report=...`,
`live_artifact_dir=...`, `live_updated_at=...`, the current step, and live
stdout/stderr artifact paths plus character counts as soon as running snapshots
exist, output advances, or silent heartbeats refresh the run; `--json` stays
clean final JSON only.
Batch reports include `status_counts` for the pass/fail/blocked distribution,
`failed_loops` for failed or blocked loops, plus batch `retry_loops` for failed,
blocked, or unfinished loops, including `running` reports recovered from
separate runs. Batch run summaries include per-loop `mode` so execute risk
remains visible during review. While a loop is
still running, the batch record exposes `current_run` with the live report path
and current step. Batch `attention_flags` surface incomplete agent chains such
as short runs, missing final submit, or crash tracebacks. When structured
execute evidence reports successful writes, batch records expose
`created_resources` so partial side effects can be audited before retry or
cleanup. Batch `repair_hints` group stale or invalid test data, incomplete
agent chains, unfinished loops, and partial execute-mode side effects into
evidence-derived next steps before drilling into raw artifacts. Batch
`failed_items` expose failed execute item type, id, name, error, and source so
prompt or fixture repairs can target the bad object directly. Batch
`validation_issues` expose agent schema and parser failures with object, count,
field path, validation types, and source so broad prompts or output-shape
regressions are visible before reading raw tracebacks.

## AI terminal entrypoints

- Claude Code: type `/`, search `meguri`, choose `/meguri`
- Codex: restart/open a new session, type `/`, search `meguri`, choose `prompts:meguri`
- Codex alternatives: `/skills` -> `meguri`, or `$meguri init`

## Common AI requests

```text
Use Meguri to initialize and inspect this project.
Use Meguri to validate this project pack.
Use Meguri to list loops.
Use Meguri to delete the <name> loop.
Use Meguri to run the smoke loop and open the report.
Use Meguri to open the latest report.
```

Add new loops with:

```text
Use Meguri to add a dry-run loop for <describe the goal>.
```

Keep loops deterministic. Do not treat an LLM's self-evaluation as a passing
check. If you write helper or verifier scripts, write structured JSON evidence
to `MEGURI_EVIDENCE_DIR` in a `finally` path so failures still include partial
input/output, errors, traceback, and artifact paths. Keep loops in `dry_run`
unless the user explicitly approves execute mode; after approval, execute-mode
loops must be run with `meguri run <loop> --allow-execute`.
"""


def _codex_skill() -> str:
    return """---
name: meguri
description: Use when the user wants Codex to initialize, design, add, list, delete, run, validate, inspect, or repair Meguri verification loops in this repository. Trigger for $meguri, loop design, project verification planning, loop generation, loop deletion, run reports, artifacts, and evidence-driven agent repair.
---

You are using the Meguri init workflow for Codex.

Meguri is an agent-facing verification workflow. Its user-facing unit is a
loop: check evidence, repair when safe, rerun, then pass, block, or ask.
Meguri owns specification files, deterministic validation, loop execution, and
reports. Codex owns project understanding, loop design, and any code/test
authoring.

Use `$meguri` as the user-facing entrypoint in conversation.

Workflow:
1. If the request is empty, starts with `init`, or `.meguri/project.yaml` is
   missing, run `meguri init`.
2. Follow the printed Meguri init specification yourself in this Codex session.
3. Read README, AGENTS.md, project manifests, existing tests, scripts, CI config,
   app entrypoints, and existing Meguri loops before editing.
4. Write `.meguri/project-inspect.json` and `.meguri/project-brief.md` from your
   evidence. If user goals, execution entries, pass criteria, credentials, data
   setup, or forbidden side effects are unclear, ask concrete questions and stop.
5. When the user asks to design or add verification, produce deterministic loops
   and any required test/helper code. Use `meguri add` only after the required
   fields are clear.
6. Prefer deterministic checks over LLM judgment. Never mark a run as passing
   because the model says it passed.
7. When writing verifier/helper scripts, make evidence crash-safe: write
   structured JSON evidence to `MEGURI_EVIDENCE_DIR` in a `finally` path, and
   include partial input/output, errors, traceback, and artifact paths even when
   the target app or model response crashes.
8. Keep loops in `dry_run` unless the user explicitly approves execute mode.
   After that approval, run execute-mode loops with
   `meguri run <loop> --allow-execute`; without that confirmation marker Meguri
   will refuse to run execute loops.
9. Use `meguri loops` to list user-added loops. Use `meguri delete <loop>` to
   delete a named user-added loop.
10. If the user asks to refresh Meguri entrypoints or report indexes after an
   update, run `meguri upgrade --skills --refresh-index`.
11. After edits, run `meguri validate` and then `meguri run <loop> --open`
   when safe. When the user asks to run several loops in order, use
   `meguri run <loop1> <loop2>` so Meguri records one sequential batch instead
   of starting loops manually or concurrently. When the user asks to run all
   remaining user-added loops, use `meguri run --all --exclude <loop>` after
   confirming the exclusion list. Batch `batch.json` and `index.html` are
   created when the batch starts, refreshed whenever the current loop writes a
   running snapshot, and refreshed again after each loop completes; use them as
   the live progress surface. Shell stdout/stderr output also refreshes the
   current run's HTML/stdout excerpts while the command is still running, and
   silent-step heartbeats refresh `updated_at` even when stdout is quiet. In
   normal text mode, `meguri run` also prints `live_report=...`,
   `live_artifact_dir=...`, `live_updated_at=...`, `live_step=...`,
   `live_stdout_path=...`, `live_stderr_path=...`, and live character counts
   as soon as a running snapshot exists, output advances, or a silent heartbeat
   refreshes the run; `--json` stays clean final JSON only. Read batch
   `current_run` for the live report path and current step. While long loops are still running, use
   `meguri report --running --json` to find active run/batch report paths and
   current steps instead of guessing from the filesystem. If the batch is
   interrupted, read the blocked batch record's `interrupted` metadata and
   `remaining_loops` before deciding whether to resume, repair, or ask.
12. Inspect the latest `.meguri/loops/<loop_id>/<run_id>/timeline.ndjson`,
   `run.json`, `report.md`, `index.html`, stdout, stderr, evidence, and
   linked artifacts before proposing fixes. For a single completed loop, use
   `meguri report <run_id> --json` or `meguri report --last --json` to get the
   structured run summary, metrics, failure reasons, `evidence_files`,
   `evidence_warnings`, `replay_status`, and `replay_missing` before drilling
   into raw artifacts. If an older single-run `index.html` or `report.md`
   predates the current Meguri renderer, use `meguri report <run_id> --refresh`
   to rebuild both from `run.json` before opening or quoting them. For multi-loop runs, inspect
   `.meguri/batches/<batch_id>/batch.json` and its `index.html` first, use
   `status_counts`, `failed_loops`, per-loop `mode`, per-loop `metrics`,
   `attention_flags`, `created_resources`, `failed_items`, `validation_issues`,
   `repair_hints`, `failure_groups`, and per-loop summaries to prioritize
   shared repairs, identify bad source objects, identify schema/output-shape
   failures, identify incomplete agent chains, and audit partial execute-mode
   side effects, then drill into each linked loop report. If
   earlier runs were started separately and you know the loop names, use
   `meguri report --loops <loop> ...` to group the newest run for each named
   loop before summarizing. If you only know the count, use
   `meguri report --recent <N>` to group the latest standalone reports into a
   recoverable batch report. If you have exact run ids or report paths, use
   `meguri report --runs <run_id-or-path> ...` so unrelated reports are not
   included. Use `meguri report --loops <loop> ... --json`,
   `meguri report --recent <N> --json`, or
   `meguri report --runs <run_id-or-path> ... --json` when you need clean
   structured data for a written summary. After making a repair, use the batch
   `retry_loops` list to understand which failed, blocked, or recovered running
   loops need another pass, then rerun only the named loop(s) intentionally.
13. Stop and ask before enabling submit, deploy, payment, production writes,
    external sends, or data migrations.
"""


def _codex_slash_prompt() -> str:
    return """---
description: Meguri verification loop workflow for the current project
argument-hint: init|add|loops|delete|run|validate|report|upgrade [args]
---

Use Meguri for this request: $ARGUMENTS

Meguri is a specification and harness layer. Use this active Codex session for
project understanding, loop design, and any code/test authoring.

If the request is empty or starts with `init`, run `meguri init`, follow the
printed specification yourself, and write
`.meguri/project-inspect.json` plus `.meguri/project-brief.md`.

If the request asks to add/design a loop, first inspect existing docs,
manifests, tests, scripts, CI, and entrypoints. Ask concrete questions when the
goal, execution entry, pass criteria, credentials, data setup, or forbidden side
effects are unclear. Then write deterministic loops and any needed test/helper
code. Verifier/helper scripts must write structured evidence to
`MEGURI_EVIDENCE_DIR` even on exceptions, including partial transcript, errors,
traceback, and artifact paths; do not rely only on stdout.

If the request asks to list or delete loops, list only user-added loops by
default and delete only a named user-added loop unless the user explicitly asks
to include or remove system loops.

If the request asks to refresh Meguri after an update, run
`meguri upgrade --skills --refresh-index`.

Always prefer deterministic evidence over LLM self-evaluation. Keep loops in
`dry_run` unless the user explicitly approves execute mode. After that approval,
run execute-mode loops with `meguri run <loop> --allow-execute`; without that
confirmation marker Meguri refuses execute loops. Before reporting completion,
run `meguri validate` and the relevant `meguri run <loop> --open` when safe.
"""


def _claude_skill() -> str:
    return """---
name: meguri
description: Use when the user wants Claude Code to initialize, design, add, list, delete, run, validate, inspect, or repair Meguri verification loops in this repository. Trigger for /meguri, loop design, project verification planning, loop generation, loop deletion, run reports, artifacts, and evidence-driven agent repair.
argument-hint: init|add|loops|delete|run|validate|report|upgrade [args]
disable-model-invocation: true
---

You are using the Meguri init workflow for Claude Code.

Meguri is an agent-facing verification workflow. Its user-facing unit is a
loop: check evidence, repair when safe, rerun, then pass, block, or ask.
Meguri owns specification files, deterministic validation, loop execution, and
reports. Claude Code owns project understanding, loop design, and any code/test
authoring.

Use `/meguri` as the user-facing entrypoint in conversation.

Requested Meguri workflow:
$ARGUMENTS

Workflow:
1. If the request is empty, starts with `init`, or `.meguri/project.yaml` is
   missing, run `meguri init`.
2. Follow the printed Meguri init specification yourself in this Claude Code
   session.
3. Read README, CLAUDE.md, project manifests, existing tests, scripts, CI config,
   app entrypoints, and existing Meguri loops before editing.
4. Write `.meguri/project-inspect.json` and `.meguri/project-brief.md` from your
   evidence. If user goals, execution entries, pass criteria, credentials, data
   setup, or forbidden side effects are unclear, ask concrete questions and stop.
5. When the user asks to design or add verification, produce deterministic loops
   and any required test/helper code. Use `meguri add` only after the required
   fields are clear.
6. Prefer deterministic checks over LLM judgment. Never mark a run as passing
   because the model says it passed.
7. When writing verifier/helper scripts, make evidence crash-safe: write
   structured JSON evidence to `MEGURI_EVIDENCE_DIR` in a `finally` path, and
   include partial input/output, errors, traceback, and artifact paths even when
   the target app or model response crashes.
8. Keep loops in `dry_run` unless the user explicitly approves execute mode.
   After that approval, run execute-mode loops with
   `meguri run <loop> --allow-execute`; without that confirmation marker Meguri
   will refuse to run execute loops.
9. Use `meguri loops` to list user-added loops. Use `meguri delete <loop>` to
   delete a named user-added loop.
10. If the user asks to refresh Meguri entrypoints or report indexes after an
   update, run `meguri upgrade --skills --refresh-index`.
11. After edits, run `meguri validate` and then `meguri run <loop> --open`
   when safe. When the user asks to run several loops in order, use
   `meguri run <loop1> <loop2>` so Meguri records one sequential batch instead
   of starting loops manually or concurrently. When the user asks to run all
   remaining user-added loops, use `meguri run --all --exclude <loop>` after
   confirming the exclusion list. Batch `batch.json` and `index.html` are
   created when the batch starts, refreshed whenever the current loop writes a
   running snapshot, and refreshed again after each loop completes; use them as
   the live progress surface. Shell stdout/stderr output also refreshes the
   current run's HTML/stdout excerpts while the command is still running, and
   silent-step heartbeats refresh `updated_at` even when stdout is quiet. In
   normal text mode, `meguri run` also prints `live_report=...`,
   `live_artifact_dir=...`, `live_updated_at=...`, `live_step=...`,
   `live_stdout_path=...`, `live_stderr_path=...`, and live character counts
   as soon as a running snapshot exists, output advances, or a silent heartbeat
   refreshes the run; `--json` stays clean final JSON only. Read batch
   `current_run` for the live report path and current step. While long loops are still running, use
   `meguri report --running --json` to find active run/batch report paths and
   current steps instead of guessing from the filesystem. If the batch is
   interrupted, read the blocked batch record's `interrupted` metadata and
   `remaining_loops` before deciding whether to resume, repair, or ask.
12. Inspect the latest `.meguri/loops/<loop_id>/<run_id>/timeline.ndjson`,
   `run.json`, `report.md`, `index.html`, stdout, stderr, evidence, and
   linked artifacts before proposing fixes. For a single completed loop, use
   `meguri report <run_id> --json` or `meguri report --last --json` to get the
   structured run summary, metrics, failure reasons, `evidence_files`,
   `evidence_warnings`, `replay_status`, and `replay_missing` before drilling
   into raw artifacts. If an older single-run `index.html` or `report.md`
   predates the current Meguri renderer, use `meguri report <run_id> --refresh`
   to rebuild both from `run.json` before opening or quoting them. For multi-loop runs, inspect
   `.meguri/batches/<batch_id>/batch.json` and its `index.html` first, use
   `status_counts`, `failed_loops`, per-loop `mode`, per-loop `metrics`,
   `attention_flags`, `created_resources`, `failed_items`, `validation_issues`,
   `repair_hints`, `failure_groups`, and per-loop summaries to prioritize
   shared repairs, identify bad source objects, identify schema/output-shape
   failures, identify incomplete agent chains, and audit partial execute-mode
   side effects, then drill into each linked loop report. If
   earlier runs were started separately and you know the loop names, use
   `meguri report --loops <loop> ...` to group the newest run for each named
   loop before summarizing. If you only know the count, use
   `meguri report --recent <N>` to group the latest standalone reports into a
   recoverable batch report. If you have exact run ids or report paths, use
   `meguri report --runs <run_id-or-path> ...` so unrelated reports are not
   included. Use `meguri report --loops <loop> ... --json`,
   `meguri report --recent <N> --json`, or
   `meguri report --runs <run_id-or-path> ... --json` when you need clean
   structured data for a written summary. After making a repair, use the batch
   `retry_loops` list to understand which failed, blocked, or recovered running
   loops need another pass, then rerun only the named loop(s) intentionally.
13. Stop and ask before enabling submit, deploy, payment, production writes,
    external sends, or data migrations.
"""


def _claude_command() -> str:
    return """---
description: Meguri verification loop workflow for the current project
argument-hint: init|add|loops|delete|run|validate|report|upgrade [args]
---

Use the Meguri loop workflow in this Claude Code session.

Requested Meguri workflow:
$ARGUMENTS

If the request is empty or starts with `init`, run `meguri init`, follow the
printed specification, and write
`.meguri/project-inspect.json` plus `.meguri/project-brief.md`.

For add, loops, delete, run, validate, report, or upgrade requests, follow the
project-local Meguri pack, prefer deterministic evidence, keep loops in
`dry_run` unless explicitly approved, make helper scripts write crash-safe
evidence to `MEGURI_EVIDENCE_DIR`, and ask before submit, deploy, payment,
production writes, external sends, or data migrations.
"""
