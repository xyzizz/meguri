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
        print(f"created {path.relative_to(project_root)}")
    for path in skipped:
        print(f"exists  {path.relative_to(project_root)}")
    if not created and skipped:
        print("no changes; pass --force to overwrite generated files")
    return 0


def _write_pack(project_root: Path, pack_root: Path, *, force: bool, skipped: list[Path]) -> list[Path]:
    smoke_command, smoke_checks = _detect_smoke(project_root)
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
        pack_root / "scenarios" / "smoke.yaml": yaml.safe_dump(
            {
                "name": f"{_safe_name(project_root.name)}_smoke",
                "adapter": "shell",
                "project_path": "../..",
                "mode": "dry_run",
                "metadata": {
                    "objective": "Verify the project can run a safe smoke command under Meguri.",
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
            },
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

## Common commands

```bash
meguri validate
meguri run smoke --open
meguri report --last --open
```

Add new scenarios with:

```bash
meguri add "describe the flow" --command "safe command" --pass-criteria "what proves success"
```

Keep scenarios deterministic. Do not treat an LLM's self-evaluation as a passing check.
"""


def _codex_skill() -> str:
    return """---
name: meguri
description: Use when the user wants to initialize, add, run, validate, inspect, or repair Meguri scenarios in this repository. Trigger for $meguri, harness validation, project pack setup, run reports, artifacts, and evidence-driven agent repair.
---

You are using the Meguri project workflow for Codex.

Use `$meguri` as the user-facing command name in conversation, but execute the local CLI with `meguri`.

Workflow:
1. Inspect `.meguri/project.yaml`, existing scenarios, tests, scripts, README, and AGENTS.md before changing anything.
2. For init/setup, run `meguri init --install-skills` when the pack is missing.
3. For adding a scenario, clarify missing goal, execution entry, pass criteria, forbidden side effects, or required credentials before writing files.
4. Prefer deterministic checks over LLM judgment. Never mark a run as passing because the model says it passed.
5. After edits, run `meguri validate` and then `meguri run <scenario> --open` when safe.
6. Inspect `.meguri/runs/<run_id>/run.json`, `report.md`, `index.html`, stdout, stderr, and linked artifacts before proposing fixes.
7. Stop and ask before enabling submit, deploy, payment, production writes, or external sends.
"""


def _claude_skill() -> str:
    return """---
name: meguri
description: Use when the user wants to initialize, add, run, validate, inspect, or repair Meguri scenarios in this repository. Trigger for /meguri, harness validation, project pack setup, run reports, artifacts, and evidence-driven agent repair.
---

You are using the Meguri project workflow for Claude Code.

Use `/meguri` as the user-facing command name in conversation, but execute the local CLI with `meguri`.

Workflow:
1. Inspect `.meguri/project.yaml`, existing scenarios, tests, scripts, README, and CLAUDE.md before changing anything.
2. For init/setup, run `meguri init --install-skills` when the pack is missing.
3. For adding a scenario, clarify missing goal, execution entry, pass criteria, forbidden side effects, or required credentials before writing files.
4. Prefer deterministic checks over LLM judgment. Never mark a run as passing because the model says it passed.
5. After edits, run `meguri validate` and then `meguri run <scenario> --open` when safe.
6. Inspect `.meguri/runs/<run_id>/run.json`, `report.md`, `index.html`, stdout, stderr, and linked artifacts before proposing fixes.
7. Stop and ask before enabling submit, deploy, payment, production writes, or external sends.
"""
