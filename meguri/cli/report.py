from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path
from typing import Any

from meguri.project.pack import find_project_pack


def handle_report(args: Any) -> int:
    try:
        pack = find_project_pack(Path.cwd())
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        html_path = latest_report(pack.runs_dir) if args.last or not args.run_id else report_for_run(pack.runs_dir, args.run_id)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(html_path)
    if args.open:
        if not open_path(html_path):
            print(f"could not open report automatically: {html_path}", file=sys.stderr)
    return 0


def latest_report(runs_dir: Path) -> Path:
    if not runs_dir.is_dir():
        raise FileNotFoundError(f"runs directory not found: {runs_dir}")
    candidates = [path for path in runs_dir.iterdir() if (path / "index.html").is_file()]
    if not candidates:
        raise FileNotFoundError(f"no HTML reports found in {runs_dir}")
    return max(candidates, key=lambda path: path.stat().st_mtime) / "index.html"


def report_for_run(runs_dir: Path, run_id: str) -> Path:
    path = runs_dir / run_id / "index.html"
    if not path.is_file():
        raise FileNotFoundError(f"report not found: {path}")
    return path


def open_path(path: Path) -> bool:
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", str(path)], check=False)
        elif system == "Windows":
            import os

            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
        return True
    except Exception:
        return False
