from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from meguri.cli.init import _display_path, write_skills
from meguri.project.pack import ProjectPack, find_project_pack
from meguri.reports.indexes import render_loop_index, render_project_index


def handle_upgrade(args: Any) -> int:
    if not args.skills and not args.refresh_index:
        print("error: choose --skills and/or --refresh-index", file=sys.stderr)
        return 2

    project_root = Path.cwd().resolve()
    updated: list[Path] = []

    try:
        if args.skills:
            updated.extend(write_skills(project_root, offline=True))
        if args.refresh_index:
            pack = find_project_pack(project_root)
            updated.extend(refresh_indexes(pack))
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for path in updated:
        print(f"updated {_display_path(project_root, path)}")
    return 0


def refresh_indexes(pack: ProjectPack) -> list[Path]:
    updated: list[Path] = []
    if pack.loops_dir.is_dir():
        for loop_dir in sorted(path for path in pack.loops_dir.iterdir() if path.is_dir()):
            index_path = loop_dir / "index.html"
            index_path.write_text(render_loop_index(loop_dir), encoding="utf-8")
            updated.append(index_path)

    project_index = pack.pack_root / "index.html"
    project_index.write_text(render_project_index(pack.pack_root), encoding="utf-8")
    updated.append(project_index)
    return updated
