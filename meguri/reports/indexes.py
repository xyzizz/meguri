from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def render_project_index(pack_root: Path) -> str:
    rows = []
    loops_dir = pack_root / "loops"
    loop_dirs = sorted([path for path in loops_dir.iterdir() if path.is_dir()]) if loops_dir.is_dir() else []
    for loop_dir in loop_dirs:
        runs = _run_records(loop_dir)
        latest = runs[0] if runs else {}
        rows.append(
            "<tr>"
            f"<td><a href=\"loops/{html.escape(loop_dir.name)}/index.html\">{html.escape(loop_dir.name)}</a></td>"
            f"<td>{len(runs)}</td>"
            f"<td>{html.escape(str(latest.get('status') or '-'))}</td>"
            f"<td>{html.escape(str(latest.get('run_id') or '-'))}</td>"
            "</tr>"
        )
    return _page(
        "Meguri Loops",
        "<table><thead><tr><th>Loop</th><th>Runs</th><th>Latest status</th><th>Latest run</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>",
    )


def render_loop_index(loop_dir: Path) -> str:
    rows = []
    for record in _run_records(loop_dir):
        run_id = str(record.get("run_id") or "")
        replay = record.get("replay") if isinstance(record.get("replay"), dict) else {}
        replay_status = replay.get("replay", {}).get("status") if isinstance(replay.get("replay"), dict) else "-"
        rows.append(
            "<tr>"
            f"<td>{html.escape(run_id)}</td>"
            f"<td>{html.escape(str(record.get('status') or '-'))}</td>"
            f"<td>{html.escape(str(replay_status or '-'))}</td>"
            f"<td><a href=\"{html.escape(run_id)}/index.html\">Open</a></td>"
            "</tr>"
        )
    return _page(
        f"Loop {loop_dir.name}",
        "<table><thead><tr><th>Run time</th><th>Status</th><th>Replay</th><th>Links</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>",
    )


def write_indexes(pack_root: Path, loop_dir: Path) -> None:
    loop_dir.joinpath("index.html").write_text(render_loop_index(loop_dir), encoding="utf-8")
    pack_root.joinpath("index.html").write_text(render_project_index(pack_root), encoding="utf-8")


def _run_records(loop_dir: Path) -> list[dict[str, Any]]:
    records = []
    run_dirs = sorted(
        [path for path in loop_dir.iterdir() if path.is_dir() and not path.name.startswith("_")],
        reverse=True,
    ) if loop_dir.is_dir() else []
    for child in run_dirs:
        run_json = child / "run.json"
        if not run_json.is_file():
            continue
        try:
            raw = json.loads(run_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(raw, dict):
            records.append(raw)
    return records


def _page(title: str, body: str) -> str:
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title>"
        "<style>"
        "body{font:14px/1.5 system-ui,sans-serif;margin:32px;color:#1d2430}"
        "main{max-width:980px;margin:0 auto}"
        "table{border-collapse:collapse;width:100%}"
        "th,td{border-bottom:1px solid #ddd;padding:8px;text-align:left}"
        "a{color:#8a3b12;text-underline-offset:3px}"
        "</style></head>"
        f"<body><main><h1>{html.escape(title)}</h1>{body}</main></body></html>"
    )
