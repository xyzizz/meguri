from __future__ import annotations

from pathlib import Path
from typing import Any

from meguri.adapters.registry import get_adapter
from meguri.project.pack import find_project_pack, resolve_scenario
from meguri.scenarios.loader import load_scenario


ALLOWED_CHECK_TYPES = {
    "exit_code",
    "stdout_json_path",
    "stdout_not_contains",
    "stderr_not_contains",
}


def handle_validate(args: Any) -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if args.target:
        _validate_scenario_path(resolve_scenario(args.target), errors, warnings)
    else:
        try:
            pack = find_project_pack(Path.cwd())
        except FileNotFoundError as exc:
            errors.append(str(exc))
        else:
            if not (pack.pack_root / "project.yaml").is_file():
                errors.append(f"missing {pack.pack_root / 'project.yaml'}")
            if not pack.scenarios_dir.is_dir():
                errors.append(f"missing scenarios directory: {pack.scenarios_dir}")
            for scenario_path in sorted(pack.scenarios_dir.glob("*.y*ml")):
                _validate_scenario_path(scenario_path, errors, warnings)
            if not (pack.project_root / ".agents" / "skills" / "meguri" / "SKILL.md").is_file():
                warnings.append("Codex skill is not installed in .agents/skills/meguri/SKILL.md")
            if not (pack.project_root / ".claude" / "skills" / "meguri" / "SKILL.md").is_file():
                warnings.append("Claude skill is not installed in .claude/skills/meguri/SKILL.md")

    for warning in warnings:
        print(f"warning: {warning}")
    for error in errors:
        print(f"error: {error}")
    if errors:
        return 1
    print("ok")
    return 0


def _validate_scenario_path(path: Path, errors: list[str], warnings: list[str]) -> None:
    try:
        scenario = load_scenario(path)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{path}: failed to load scenario: {type(exc).__name__}: {exc}")
        return
    try:
        get_adapter(scenario.adapter)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"{path}: unknown adapter {scenario.adapter!r}: {exc}")
    if not scenario.steps:
        errors.append(f"{path}: scenario must contain at least one step")
    for index, step in enumerate(scenario.steps):
        step_id = step.get("id") or f"step[{index}]"
        if not step.get("id"):
            errors.append(f"{path}: step[{index}] is missing id")
        if scenario.adapter == "shell" and not step.get("command"):
            errors.append(f"{path}: shell step {step_id!r} is missing command")
        for check in step.get("checks") or []:
            check_type = check.get("type")
            if check_type not in ALLOWED_CHECK_TYPES:
                errors.append(f"{path}: step {step_id!r} has unknown check type {check_type!r}")
    if not scenario.project_path.exists():
        warnings.append(f"{path}: project_path does not exist yet: {scenario.project_path}")
