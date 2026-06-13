from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any


def failure_groups(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = {}
    for run in runs:
        loop = str(run.get("loop") or "")
        for reason in run.get("failure_reasons") or []:
            if not isinstance(reason, str) or not reason:
                continue
            grouped.setdefault(reason, [])
            if loop and loop not in grouped[reason]:
                grouped[reason].append(loop)
    groups = [
        {"reason": reason, "count": len(loops), "loops": loops}
        for reason, loops in grouped.items()
    ]
    return sorted(groups, key=lambda group: (-int(group["count"]), str(group["reason"])))


def render_batch_html(record: dict[str, Any], batch_dir: Path) -> str:
    rows = []
    for index, run in enumerate(record["runs"], start=1):
        report_path = Path(run["html_report_path"])
        href = os.path.relpath(report_path, batch_dir)
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{html.escape(str(run['loop']))}</td>"
            f"<td>{html.escape(str(run['status']))}</td>"
            f"<td>{html.escape(str(run['run_id']))}</td>"
            f"<td>{html.escape(str(run['summary']))}</td>"
            f"<td><a href=\"{html.escape(href)}\">Open report</a></td>"
            "</tr>"
        )
    group_rows = []
    for group in record.get("failure_groups") or []:
        group_rows.append(
            "<tr>"
            f"<td>{html.escape(str(group['reason']))}</td>"
            f"<td>{html.escape(str(group['count']))} loops</td>"
            f"<td>{html.escape(', '.join(str(loop) for loop in group.get('loops') or []))}</td>"
            "</tr>"
        )
    groups_html = (
        "<h2>Failure Groups</h2>"
        "<table><thead><tr><th>Reason</th><th>Count</th><th>Loops</th></tr></thead><tbody>"
        + "".join(group_rows)
        + "</tbody></table>"
    ) if group_rows else ""
    source = f"Source: {html.escape(str(record.get('source')))}<br>" if record.get("source") else ""
    current = f"<br>Current: {html.escape(str(record.get('current_loop') or '-'))}" if "current_loop" in record else ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Meguri Batch {html.escape(str(record['batch_id']))}</title>"
        "<style>"
        "body{font:14px/1.5 system-ui,sans-serif;margin:32px;color:#1d2430}"
        "main{max-width:980px;margin:0 auto}"
        ".status{font-weight:700;text-transform:uppercase}"
        ".meta{color:#5d6778}"
        "table{border-collapse:collapse;width:100%;margin-top:18px}"
        "th,td{border-bottom:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}"
        "a{color:#8a3b12;text-underline-offset:3px}"
        "</style></head><body><main>"
        f"<h1>Meguri Batch {html.escape(str(record['batch_id']))}</h1>"
        f"<p>Status: <span class=\"status\">{html.escape(str(record['status']))}</span></p>"
        f"<p class=\"meta\">{source}Progress: {html.escape(str(record.get('completed_loops', 0)))}"
        f" / {html.escape(str(record.get('total_loops', len(record.get('runs') or []))))} loops"
        f"{current}"
        f"<br>Started: {html.escape(str(record.get('started_at') or '-'))}"
        f"<br>Updated: {html.escape(str(record.get('updated_at') or '-'))}"
        f"<br>Finished: {html.escape(str(record.get('finished_at') or '-'))}</p>"
        + groups_html +
        "<table><thead><tr><th>#</th><th>Loop</th><th>Status</th><th>Run</th><th>Summary</th><th>Report</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></main></body></html>"
    )
