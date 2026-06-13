from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from meguri.project.pack import ProjectPack, find_project_pack, slugify


@dataclass(frozen=True)
class LoopEntry:
    loop_id: str
    name: str
    mode: str
    source: str
    path: Path
    user_goal: str


def handle_loops(args: Any) -> int:
    try:
        pack = find_project_pack(Path.cwd())
    except FileNotFoundError:
        print("Cannot list loops yet: no .meguri/ pack found.")
        return 2

    entries = read_loops(pack)
    visible = entries if args.all else [entry for entry in entries if entry.source == "user"]

    if args.json:
        print(json.dumps({
            "count": len(visible),
            "loops": [
                {
                    "loop_id": entry.loop_id,
                    "name": entry.name,
                    "mode": entry.mode,
                    "source": entry.source,
                    "path": str(entry.path.relative_to(pack.project_root)),
                    "user_goal": entry.user_goal,
                }
                for entry in visible
            ],
        }, ensure_ascii=False, indent=2))
        return 0

    print(f"loops={len(visible)}")
    for entry in visible:
        path = entry.path.relative_to(pack.project_root)
        goal = f"  {entry.user_goal}" if entry.user_goal else ""
        print(f"- {entry.loop_id} [{entry.mode}] {path}{goal}")
    return 0


def handle_delete(args: Any) -> int:
    try:
        pack = find_project_pack(Path.cwd())
    except FileNotFoundError:
        print("Cannot delete a loop yet: no .meguri/ pack found.")
        return 2

    target = slugify(args.name, fallback=args.name)
    matches = [
        entry for entry in read_loops(pack)
        if entry.loop_id == target or entry.name == target or entry.path.stem == target or entry.path.parent.name == target
    ]
    if not matches:
        print(f"Loop not found: {args.name}")
        return 1
    if len(matches) > 1:
        print(f"Loop name is ambiguous: {args.name}")
        for entry in matches:
            print(f"- {entry.loop_id}: {entry.path.relative_to(pack.project_root)}")
        return 1

    entry = matches[0]
    if entry.source != "user" and not args.force:
        print(f"Refusing to delete system loop: {entry.loop_id}")
        print("Pass --force to delete it anyway.")
        return 1

    if args.dry_run:
        print(f"would delete loop {entry.loop_id}: {entry.path.relative_to(pack.project_root)}")
        return 0

    if entry.path.name == "_loop.yaml":
        shutil.rmtree(entry.path.parent)
    else:
        entry.path.unlink()
    print(f"deleted loop {entry.loop_id}: {entry.path.relative_to(pack.project_root)}")
    return 0


def read_loops(pack: ProjectPack) -> list[LoopEntry]:
    entries = _read_loop_folders(pack.loops_dir)
    existing = {entry.loop_id for entry in entries}
    entries.extend(_read_legacy_scenarios(pack.scenarios_dir, existing_ids=existing))
    return entries


def _read_loop_folders(loops_dir: Path) -> list[LoopEntry]:
    entries: list[LoopEntry] = []
    for path in sorted(loops_dir.glob("*/_loop.yaml")):
        entry = _loop_entry_from_path(path)
        if entry is not None:
            entries.append(entry)
    return entries


def _read_legacy_scenarios(scenarios_dir: Path, *, existing_ids: set[str]) -> list[LoopEntry]:
    entries: list[LoopEntry] = []
    for path in sorted(scenarios_dir.glob("*.y*ml")):
        entry = _loop_entry_from_path(path)
        if entry is not None and entry.loop_id not in existing_ids:
            entries.append(entry)
    return entries


def _loop_entry_from_path(path: Path) -> LoopEntry | None:
    raw = _read_yaml(path)
    if not isinstance(raw, dict):
        return None
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    loop_id = str(metadata.get("loop_id") or raw.get("name") or path.stem)
    source = str(metadata.get("source") or _infer_source(loop_id, metadata))
    return LoopEntry(
        loop_id=loop_id,
        name=str(raw.get("name") or path.stem),
        mode=str(raw.get("mode") or "dry_run"),
        source=source,
        path=path,
        user_goal=str(metadata.get("user_goal") or metadata.get("objective") or ""),
    )


def _read_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _infer_source(loop_id: str, metadata: dict[str, Any]) -> str:
    if metadata.get("kind") == "loop" and loop_id != "smoke":
        return "user"
    return "system"
