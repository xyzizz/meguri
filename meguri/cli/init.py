from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

from meguri.cli.entrypoints import refresh_entrypoints
from meguri.cli.inspect import write_inspect_spec
from meguri.project.pack import load_project_pack, pack_root_for


def handle_init(args: Any) -> int:
    project_root = Path.cwd().resolve()
    pack_root = pack_root_for(project_root)
    created: list[Path] = []
    skipped: list[Path] = []
    force = bool(getattr(args, "force", False))
    offline = bool(getattr(args, "offline", False))

    try:
        created.extend(write_skills(project_root, offline=offline))
    except Exception as exc:  # noqa: BLE001
        print(f"error: Meguri skill refresh failed: {exc}", file=sys.stderr)
        if not offline:
            print("rerun with --offline to use bundled templates without network access", file=sys.stderr)
        return 1

    created.extend(_write_pack(project_root, pack_root, force=force, skipped=skipped))
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


def write_skills(project_root: Path, *, offline: bool) -> list[Path]:
    return refresh_entrypoints(project_root, offline=offline)


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
safe execution, to deterministic evidence, to repair when safe, to rerun, and
finally pass, blocked, or ask. New loops live under
`.meguri/loops/<loop_id>/_loop.yaml`, and each run writes history under
`.meguri/loops/<loop_id>/<run_id>/`. Multi-loop sequential runs write aggregate
records under `.meguri/batches/<batch_id>/`.

## AI terminal entrypoints

- Use `/meguri` in Codex or Claude Code.

## Common AI requests

```text
Initialize this project with Meguri.
Add a verification loop for <goal>.
Run all verification.
Open the latest report.
```

The public CLI bottom layer is intentionally small:

```text
meguri init
meguri run <loop>
meguri run <loop1> <loop2>
meguri run all
meguri report [run_or_batch_id]
```

Use natural language through `/meguri` for loop creation and cleanup. The agent
adds or changes loops by editing `.meguri/loops/<loop_id>/_loop.yaml` and removes
a user loop by deleting its loop directory after the user names it clearly.

Keep loops deterministic. Do not treat an LLM's self-evaluation as passing
evidence. If you write helper or verifier scripts, write structured JSON
evidence to `MEGURI_EVIDENCE_DIR` in a `finally` path so failures still include
partial input/output, errors, traceback, and artifact paths. Keep loops in
`dry_run` unless the user explicitly approves execute mode; after approval,
execute-mode runs require the `--allow-execute` confirmation marker. Ask before
submit, deploy, payment, production writes, external sends, or data migrations.
"""
