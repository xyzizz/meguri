from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

from meguri.project.pack import pack_root_for


def handle_init(args: Any) -> int:
    project_root = Path.cwd().resolve()
    pack_root = pack_root_for(project_root)
    created: list[Path] = []
    skipped: list[Path] = []

    created.extend(_write_pack(project_root, pack_root, force=bool(args.force), skipped=skipped))
    if args.install_skills:
        created.extend(_write_skills(project_root, force=bool(args.force), skipped=skipped))

    for path in created:
        print(f"created {_display_path(project_root, path)}")
    for path in skipped:
        print(f"exists  {_display_path(project_root, path)}")
    if not created and skipped:
        print("no changes; pass --force to overwrite generated files")
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


def _write_skills(project_root: Path, *, force: bool, skipped: list[Path]) -> list[Path]:
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
into the loop history structure.

## AI terminal entrypoints

- Claude Code: type `/`, search `meguri`, choose `/meguri`
- Codex: restart/open a new session, type `/`, search `meguri`, choose `prompts:meguri`
- Codex alternatives: `/skills` -> `meguri`, or `$meguri inspect`

## Common AI requests

```text
Use Meguri to inspect this project.
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
input/output, errors, traceback, and artifact paths.
"""


def _codex_skill() -> str:
    return """---
name: meguri
description: Use when the user wants Codex to design, add, list, delete, run, validate, inspect, or repair Meguri verification loops in this repository. Trigger for $meguri, loop design, project verification planning, loop generation, loop deletion, run reports, artifacts, and evidence-driven agent repair.
---

You are using the Meguri project workflow for Codex.

Meguri is an agent-facing verification workflow. Its user-facing unit is a
loop: check evidence, repair when safe, rerun, then pass, block, or ask.
Meguri owns specification files, deterministic validation, loop execution, and
reports. Codex owns project understanding, loop design, and any code/test
authoring.

Use `$meguri` as the user-facing entrypoint in conversation.

Workflow:
1. If `.meguri/project.yaml` is missing, run `meguri init --install-skills`.
2. Start the Meguri inspect workflow to materialize and print the current
   Meguri inspect specification. Follow that spec yourself in this Codex session.
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
9. Use `meguri loops` to list user-added loops. Use `meguri delete <loop>` to
   delete a named user-added loop.
10. After edits, run `meguri validate` and then `meguri run <loop> --open`
   when safe. When the user asks to run several loops in order, use
   `meguri run <loop1> <loop2>` so Meguri records one sequential batch instead
   of starting loops manually or concurrently.
11. Inspect the latest `.meguri/loops/<loop_id>/<run_id>/timeline.ndjson`,
   `run.json`, `report.md`, `index.html`, stdout, stderr, evidence, and
   linked artifacts before proposing fixes.
12. Stop and ask before enabling submit, deploy, payment, production writes,
    external sends, or data migrations.
"""


def _codex_slash_prompt() -> str:
    return """---
description: Meguri verification loop workflow for the current project
argument-hint: inspect|add|loops|delete|run|validate|report [args]
---

Use Meguri for this request: $ARGUMENTS

Meguri is a specification and harness layer. Use this active Codex session for
project understanding, loop design, and any code/test authoring.

If the request is empty or starts with `inspect`, start the Meguri inspect
workflow, follow the printed specification yourself, and write
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

Always prefer deterministic evidence over LLM self-evaluation. Keep loops in
`dry_run` unless the user explicitly approves execute mode. Before reporting
completion, run `meguri validate` and the relevant `meguri run <loop> --open`
when safe.
"""


def _claude_skill() -> str:
    return """---
name: meguri
description: Use when the user wants Claude Code to design, add, list, delete, run, validate, inspect, or repair Meguri verification loops in this repository. Trigger for /meguri, loop design, project verification planning, loop generation, loop deletion, run reports, artifacts, and evidence-driven agent repair.
argument-hint: inspect|add|loops|delete|run|validate|report [args]
disable-model-invocation: true
---

You are using the Meguri project workflow for Claude Code.

Meguri is an agent-facing verification workflow. Its user-facing unit is a
loop: check evidence, repair when safe, rerun, then pass, block, or ask.
Meguri owns specification files, deterministic validation, loop execution, and
reports. Claude Code owns project understanding, loop design, and any code/test
authoring.

Use `/meguri` as the user-facing entrypoint in conversation.

Requested Meguri workflow:
$ARGUMENTS

Workflow:
1. If `.meguri/project.yaml` is missing, run `meguri init --install-skills`.
2. Start the Meguri inspect workflow to materialize and print the current
   Meguri inspect specification. Follow that spec yourself in this Claude Code
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
9. Use `meguri loops` to list user-added loops. Use `meguri delete <loop>` to
   delete a named user-added loop.
10. After edits, run `meguri validate` and then `meguri run <loop> --open`
   when safe. When the user asks to run several loops in order, use
   `meguri run <loop1> <loop2>` so Meguri records one sequential batch instead
   of starting loops manually or concurrently.
11. Inspect the latest `.meguri/loops/<loop_id>/<run_id>/timeline.ndjson`,
   `run.json`, `report.md`, `index.html`, stdout, stderr, evidence, and
   linked artifacts before proposing fixes.
12. Stop and ask before enabling submit, deploy, payment, production writes,
    external sends, or data migrations.
"""


def _claude_command() -> str:
    return """---
description: Meguri verification loop workflow for the current project
argument-hint: inspect|add|loops|delete|run|validate|report [args]
---

Use the Meguri loop workflow in this Claude Code session.

Requested Meguri workflow:
$ARGUMENTS

If the request is empty or starts with `inspect`, start the Meguri inspect
workflow, follow the printed specification, and write
`.meguri/project-inspect.json` plus `.meguri/project-brief.md`.

For add, loops, delete, run, validate, or report requests, follow the
project-local Meguri pack, prefer deterministic evidence, keep loops in
`dry_run` unless explicitly approved, make helper scripts write crash-safe
evidence to `MEGURI_EVIDENCE_DIR`, and ask before submit, deploy, payment,
production writes, external sends, or data migrations.
"""
