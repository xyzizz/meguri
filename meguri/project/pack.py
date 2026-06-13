from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


PACK_DIR_NAME = ".meguri"
LEGACY_PACK_DIR_NAMES = (".ai-harness",)
PACK_DIR_NAMES = (PACK_DIR_NAME, *LEGACY_PACK_DIR_NAMES)
SCENARIOS_DIR_NAME = "scenarios"
RUNS_DIR_NAME = "runs"
PROJECT_FILE_NAME = "project.yaml"


@dataclass(frozen=True)
class ProjectPack:
    project_root: Path
    pack_root: Path
    config: dict[str, Any]

    @property
    def scenarios_dir(self) -> Path:
        return self.pack_root / SCENARIOS_DIR_NAME

    @property
    def runs_dir(self) -> Path:
        configured = self.config.get("runs_dir")
        if configured:
            path = Path(str(configured)).expanduser()
            if path.is_absolute():
                return path
            return (self.project_root / path).resolve()
        return self.pack_root / RUNS_DIR_NAME


def slugify(value: str, *, fallback: str = "loop") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return slug or fallback


def pack_root_for(project_root: Path) -> Path:
    return project_root / PACK_DIR_NAME


def load_project_pack(project_root: Path, *, pack_dir_name: str | None = None) -> ProjectPack:
    if pack_dir_name is None:
        if pack_root_for(project_root).exists() or not any((project_root / name).exists() for name in LEGACY_PACK_DIR_NAMES):
            pack_dir_name = PACK_DIR_NAME
        else:
            pack_dir_name = next(name for name in LEGACY_PACK_DIR_NAMES if (project_root / name).exists())
    pack_root = project_root / pack_dir_name
    config_path = pack_root / PROJECT_FILE_NAME
    if config_path.exists():
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError(f"project pack config must be a mapping: {config_path}")
    else:
        raw = {}
    return ProjectPack(project_root=project_root, pack_root=pack_root, config=raw)


def find_project_pack(start: Path | None = None) -> ProjectPack:
    current = (start or Path.cwd()).resolve()
    if current.is_file():
        current = current.parent
    for candidate in [current, *current.parents]:
        for pack_dir_name in PACK_DIR_NAMES:
            if (candidate / pack_dir_name).is_dir():
                return load_project_pack(candidate, pack_dir_name=pack_dir_name)
    raise FileNotFoundError(f"no {PACK_DIR_NAME} directory found from {current}")


def resolve_scenario(value: str | Path, *, cwd: Path | None = None) -> Path:
    raw = Path(str(value)).expanduser()
    if raw.exists():
        return raw.resolve()
    if raw.suffix in {".yaml", ".yml"}:
        candidate = ((cwd or Path.cwd()) / raw).resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(f"loop file not found: {value}")

    pack = find_project_pack(cwd)
    for suffix in (".yaml", ".yml"):
        candidate = pack.scenarios_dir / f"{raw.name}{suffix}"
        if candidate.exists():
            return candidate.resolve()
    raise FileNotFoundError(f"loop alias not found in {pack.scenarios_dir}: {value}")


def default_runs_dir_for_scenario(scenario_path: Path) -> Path:
    from meguri.scenarios.loader import load_scenario

    scenario = load_scenario(scenario_path)
    pack = load_project_pack(scenario.project_path)
    return pack.runs_dir
