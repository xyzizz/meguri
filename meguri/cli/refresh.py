from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from meguri.cli.entrypoints import refresh_entrypoints


def handle_refresh(args: Any) -> int:
    project_root = Path.cwd().resolve()
    offline = bool(getattr(args, "offline", False))

    try:
        written = refresh_entrypoints(project_root, offline=offline)
    except Exception as exc:  # noqa: BLE001
        print(f"error: Meguri refresh failed: {exc}", file=sys.stderr)
        if not offline:
            print("rerun with refresh --offline to use bundled templates without network access", file=sys.stderr)
        return 1

    for path in written:
        print(f"updated {_display_path(project_root, path)}")
    return 0


def _display_path(project_root: Path, path: Path) -> str:
    try:
        return str(path.relative_to(project_root))
    except ValueError:
        return str(path)
