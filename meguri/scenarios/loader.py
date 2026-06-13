from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from meguri.core.models import Scenario


def load_scenario(path: Path) -> Scenario:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"scenario must be a mapping: {path}")
    project_path = Path(str(raw["project_path"])).expanduser()
    if not project_path.is_absolute():
        project_path = (path.parent / project_path).resolve()
    return Scenario(
        name=str(raw["name"]),
        adapter=str(raw["adapter"]),
        project_path=project_path,
        mode=str(raw.get("mode") or "dry_run"),  # type: ignore[arg-type]
        steps=list(raw.get("steps") or []),
        checks=list(raw.get("checks") or []),
        budgets=dict(raw.get("budgets") or {}),
        metadata=dict(raw.get("metadata") or {}),
    )

