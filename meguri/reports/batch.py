from __future__ import annotations

import html
import os
import shlex
from pathlib import Path
from typing import Any

from meguri.reports.metrics import format_metrics


def batch_retry_command(
    runs: list[dict[str, Any]],
    remaining_loops: list[str] | None = None,
    *,
    allow_execute: bool = False,
) -> str:
    targets = batch_retry_loops(runs, remaining_loops)
    if not targets:
        return ""
    command = ["meguri", "run", *targets]
    if allow_execute:
        command.append("--allow-execute")
    return shlex.join(command)


def batch_retry_loops(runs: list[dict[str, Any]], remaining_loops: list[str] | None = None) -> list[str]:
    targets = []
    for run in runs:
        status = str(run.get("status") or "")
        loop = str(run.get("loop") or "")
        if loop and status in {"fail", "blocked"}:
            targets.append(loop)
    targets.extend(str(loop) for loop in (remaining_loops or []) if loop)
    return _dedupe(targets)


def batch_status_counts(runs: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in runs:
        status = str(run.get("status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def batch_failed_loops(runs: list[dict[str, Any]]) -> list[str]:
    targets = []
    for run in runs:
        status = str(run.get("status") or "")
        loop = str(run.get("loop") or "")
        if loop and status in {"fail", "blocked"}:
            targets.append(loop)
    return _dedupe(targets)


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
            f"<td>{html.escape(str(run.get('mode') or '-'))}</td>"
            f"<td>{html.escape(str(run['run_id']))}</td>"
            f"<td>{html.escape(format_metrics(run.get('metrics') or {}))}</td>"
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
    counts = record.get("status_counts") if isinstance(record.get("status_counts"), dict) else {}
    status_summary = ", ".join(f"{key}: {value}" for key, value in counts.items())
    failed_loops = ", ".join(str(loop) for loop in record.get("failed_loops") or [])
    summary_html = ""
    if status_summary or failed_loops:
        summary_html = (
            "<section class=\"summary\">"
            "<h2>Status Summary</h2>"
            f"<p>{html.escape(status_summary or '-')}</p>"
            f"<p class=\"meta\">Failed loops: {html.escape(failed_loops or '-')}</p>"
            "</section>"
        )
    source = f"Source: {html.escape(str(record.get('source')))}<br>" if record.get("source") else ""
    current = f"<br>Current: {html.escape(str(record.get('current_loop') or '-'))}" if "current_loop" in record else ""
    interruption = record.get("interruption") if isinstance(record.get("interruption"), dict) else None
    interruption_html = ""
    if interruption:
        interruption_html = (
            "<p class=\"notice\">Interrupted: "
            f"{html.escape(str(interruption.get('type') or 'unknown'))}"
            f"{': ' + html.escape(str(interruption.get('message'))) if interruption.get('message') else ''}"
            "</p>"
        )
    retry_command = str(record.get("retry_command") or "")
    retry_html = ""
    if retry_command:
        retry_html = (
            "<h2>Retry Failed Loops</h2>"
            "<p class=\"meta\">Run from the project root after repair. Execute-mode loops still require explicit approval.</p>"
            f"<pre>{html.escape(retry_command)}</pre>"
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Meguri Batch {html.escape(str(record['batch_id']))}</title>"
        "<style>"
        "body{font:14px/1.5 system-ui,sans-serif;margin:32px;color:#1d2430}"
        "main{max-width:980px;margin:0 auto}"
        ".status{font-weight:700;text-transform:uppercase}"
        ".summary{border:1px solid #ddd;border-radius:6px;padding:12px;margin:18px 0}"
        ".summary h2{margin:0 0 8px;font-size:16px}"
        ".summary p{margin:4px 0}"
        ".meta{color:#5d6778}"
        ".notice{background:#fff4df;border-left:3px solid #b06a00;padding:10px 12px}"
        "pre{background:#f5f6f8;border:1px solid #ddd;border-radius:6px;padding:10px;white-space:pre-wrap;overflow-wrap:anywhere}"
        "table{border-collapse:collapse;width:100%;margin-top:18px}"
        "th,td{border-bottom:1px solid #ddd;padding:8px;text-align:left;vertical-align:top}"
        "a{color:#8a3b12;text-underline-offset:3px}"
        "</style></head><body><main>"
        f"<h1>Meguri Batch {html.escape(str(record['batch_id']))}</h1>"
        f"<p>Status: <span class=\"status\">{html.escape(str(record['status']))}</span></p>"
        f"{interruption_html}"
        f"<p class=\"meta\">{source}Progress: {html.escape(str(record.get('completed_loops', 0)))}"
        f" / {html.escape(str(record.get('total_loops', len(record.get('runs') or []))))} loops"
        f"{current}"
        f"<br>Started: {html.escape(str(record.get('started_at') or '-'))}"
        f"<br>Updated: {html.escape(str(record.get('updated_at') or '-'))}"
        f"<br>Finished: {html.escape(str(record.get('finished_at') or '-'))}</p>"
        + summary_html
        + retry_html
        + groups_html
        + "<table><thead><tr><th>#</th><th>Loop</th><th>Status</th><th>Mode</th><th>Run</th><th>Metrics</th><th>Summary</th><th>Report</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></main></body></html>"
    )


def _dedupe(values: list[str]) -> list[str]:
    deduped = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
