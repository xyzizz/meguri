from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from meguri.project.pack import ProjectPack, find_project_pack


def handle_report(args: Any) -> int:
    try:
        pack = find_project_pack(Path.cwd())
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        html_path = latest_report(pack) if args.last or not args.run_id else report_for_run(pack, args.run_id)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(html_path)
    if args.open:
        if not open_path(html_path):
            print(f"could not open report automatically: {html_path}", file=sys.stderr)
    return 0


def latest_report(pack: ProjectPack) -> Path:
    candidates = _loop_report_dirs(pack)
    candidates.extend(_batch_report_dirs(pack))
    if pack.runs_dir.is_dir():
        candidates.extend([path for path in pack.runs_dir.iterdir() if (path / "index.html").is_file()])
    if not candidates:
        raise FileNotFoundError(f"no HTML reports found in {pack.pack_root}")
    return max(candidates, key=_report_sort_key) / "index.html"


def report_for_run(pack: ProjectPack, run_id: str) -> Path:
    if "/" in run_id:
        loop_id, child_run_id = run_id.split("/", 1)
        path = pack.loops_dir / loop_id / child_run_id / "index.html"
        if path.is_file():
            return path
        raise FileNotFoundError(f"report not found: {path}")

    matches = [path / "index.html" for path in _loop_report_dirs(pack) if path.name == run_id]
    batch = pack.pack_root / "batches" / run_id / "index.html"
    if batch.is_file():
        matches.append(batch)
    legacy = pack.runs_dir / run_id / "index.html"
    if legacy.is_file():
        matches.append(legacy)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise FileNotFoundError(f"run id is ambiguous; use <loop_id>/{run_id}")
    raise FileNotFoundError(f"report not found for run: {run_id}")


def _loop_report_dirs(pack: ProjectPack) -> list[Path]:
    if not pack.loops_dir.is_dir():
        return []
    candidates = []
    for loop_dir in sorted(path for path in pack.loops_dir.iterdir() if path.is_dir()):
        for run_dir in sorted(path for path in loop_dir.iterdir() if path.is_dir() and not path.name.startswith("_")):
            if (run_dir / "index.html").is_file():
                candidates.append(run_dir)
    return candidates


def _batch_report_dirs(pack: ProjectPack) -> list[Path]:
    batches_dir = pack.pack_root / "batches"
    if not batches_dir.is_dir():
        return []
    return [
        batch_dir
        for batch_dir in sorted(path for path in batches_dir.iterdir() if path.is_dir())
        if (batch_dir / "index.html").is_file()
    ]


def _report_sort_key(path: Path) -> tuple[float, str]:
    recorded = _recorded_report_time(path)
    if recorded is not None:
        return (recorded, path.name)
    return (path.stat().st_mtime, path.name)


def _recorded_report_time(report_dir: Path) -> float | None:
    for name in ("run.json", "batch.json"):
        recorded = _recorded_json_time(report_dir / name)
        if recorded is not None:
            return recorded
    return None


def _recorded_json_time(path: Path) -> float | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    for key in ("finished_at", "started_at"):
        value = raw.get(key)
        if not value:
            continue
        parsed = _parse_timestamp(str(value))
        if parsed is not None:
            return parsed
    return None


def _parse_timestamp(value: str) -> float | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


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
