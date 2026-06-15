from __future__ import annotations

import html
import os
from pathlib import Path
from typing import Any

from meguri.reports.metrics import format_metrics
from meguri.reports.theme import GLOW_BACKGROUND_HTML, GLOW_BASE_CSS


BATCH_GLOW_CSS = GLOW_BASE_CSS + """
main {
  max-width: 1120px;
  margin: 0 auto;
  padding: 32px 24px 54px;
}
h1 {
  margin: 0 0 10px;
  font-size: 1.85rem;
  line-height: 1.18;
}
h2 {
  margin: 26px 0 12px;
  font-size: 1rem;
}
.status {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 3px 9px;
  border: 1px solid rgba(160, 196, 255, 0.32);
  border-radius: 999px;
  color: var(--accent);
  background: rgba(160, 196, 255, 0.12);
  font-weight: 800;
  text-transform: uppercase;
  box-shadow: 0 0 18px rgba(160, 196, 255, 0.16);
}
.summary,
.notice,
table {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow-panel);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}
.summary {
  padding: 14px;
  margin: 18px 0;
}
.summary h2 {
  margin: 0 0 8px;
}
.summary p {
  margin: 4px 0;
}
.meta {
  color: var(--muted);
}
.notice {
  border-left: 3px solid var(--glow-warm);
  padding: 10px 12px;
  color: var(--warning);
  background: rgba(255, 216, 155, 0.1);
}
table {
  width: 100%;
  margin-top: 18px;
  border-collapse: separate;
  border-spacing: 0;
  overflow: hidden;
}
th,
td {
  padding: 9px 10px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
  overflow-wrap: anywhere;
}
tr:last-child td {
  border-bottom: 0;
}
th {
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 800;
}
tr:hover td {
  background: rgba(160, 196, 255, 0.045);
}
pre {
  border-radius: 8px;
  padding: 10px;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.attempt-list {
  margin: 0;
  padding-left: 18px;
}
.attempt-list li {
  margin: 5px 0;
}
.attempt-list .meta {
  display: block;
}
@media (max-width: 720px) {
  main { padding: 22px 14px 40px; }
  table { display: block; overflow-x: auto; }
}
"""


def batch_retry_loops(runs: list[dict[str, Any]], remaining_loops: list[str] | None = None) -> list[str]:
    targets = []
    for run in runs:
        status = str(run.get("status") or "")
        loop = str(run.get("loop") or "")
        if loop and status in {"fail", "blocked", "running"}:
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


def batch_created_resources(runs: list[dict[str, Any]]) -> list[dict[str, str]]:
    resources: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for run in runs:
        loop = str(run.get("loop") or "")
        run_id = str(run.get("run_id") or "")
        for resource in run.get("created_resources") or []:
            if not isinstance(resource, dict):
                continue
            resource_type = str(resource.get("type") or "resource")
            resource_id = str(resource.get("id") or "")
            source = str(resource.get("source") or "")
            if not resource_id:
                continue
            key = (loop, run_id, resource_type, resource_id)
            if key in seen:
                continue
            seen.add(key)
            resources.append({
                "loop": loop,
                "run_id": run_id,
                "type": resource_type,
                "id": resource_id,
                "source": source,
            })
    return resources


def batch_failed_items(runs: list[dict[str, Any]]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for run in runs:
        loop = str(run.get("loop") or "")
        run_id = str(run.get("run_id") or "")
        for item in run.get("failed_items") or []:
            if not isinstance(item, dict):
                continue
            resource_type = str(item.get("type") or "resource")
            resource_id = str(item.get("id") or "")
            name = str(item.get("name") or "")
            error = str(item.get("error") or "")
            source = str(item.get("source") or "")
            if not any((resource_id, name, error)):
                continue
            key = (loop, run_id, resource_type, resource_id, name, error)
            if key in seen:
                continue
            seen.add(key)
            items.append({
                "loop": loop,
                "run_id": run_id,
                "type": resource_type,
                "id": resource_id,
                "name": name,
                "error": error,
                "source": source,
            })
    return items


def batch_validation_issues(runs: list[dict[str, Any]]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str, str, str]] = set()
    for run in runs:
        loop = str(run.get("loop") or "")
        run_id = str(run.get("run_id") or "")
        for issue in run.get("validation_issues") or []:
            if not isinstance(issue, dict):
                continue
            code = str(issue.get("code") or "")
            object_name = str(issue.get("object") or "")
            path = str(issue.get("path") or "")
            types = str(issue.get("types") or "")
            message = str(issue.get("message") or "")
            source = str(issue.get("source") or "")
            if not any((code, object_name, path, types, message)):
                continue
            key = (loop, run_id, code, object_name, path, types, source)
            if key in seen:
                continue
            seen.add(key)
            issues.append({
                "loop": loop,
                "run_id": run_id,
                "code": code,
                "severity": str(issue.get("severity") or "error"),
                "object": object_name,
                "count": str(issue.get("count") or ""),
                "path": path,
                "types": types,
                "message": message,
                "source": source,
            })
    return issues


def batch_attention_flags(runs: list[dict[str, Any]]) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for run in runs:
        loop = str(run.get("loop") or "")
        run_id = str(run.get("run_id") or "")
        for flag in run.get("attention_flags") or []:
            if not isinstance(flag, dict):
                continue
            code = str(flag.get("code") or "")
            if not code:
                continue
            key = (loop, run_id, code)
            if key in seen:
                continue
            seen.add(key)
            flags.append({
                "loop": loop,
                "run_id": run_id,
                "code": code,
                "severity": str(flag.get("severity") or "warning"),
                "message": str(flag.get("message") or ""),
            })
    return flags


def batch_repair_hints(runs: list[dict[str, Any]], remaining_loops: list[str] | None = None) -> list[dict[str, Any]]:
    hints: list[dict[str, Any]] = []
    data_loops: list[str] = []
    data_reasons: list[str] = []
    for group in failure_groups(runs):
        reason = str(group.get("reason") or "")
        loops = [str(loop) for loop in group.get("loops") or [] if loop]
        if _looks_like_test_data_failure(reason):
            data_loops.extend(loops)
            data_reasons.append(reason)
    if data_loops:
        hints.append({
            "code": "verify_test_data",
            "severity": "error",
            "loops": _dedupe(data_loops),
            "reasons": _dedupe(data_reasons),
            "action": "Verify or replace stale, invalid, or conflicting project data before rerun; keep pass criteria unchanged unless the user changes the goal.",
        })

    validation_issues = batch_validation_issues(runs)
    if validation_issues:
        hints.append({
            "code": "fix_schema_output",
            "severity": "error",
            "loops": _dedupe([str(issue.get("loop") or "") for issue in validation_issues if issue.get("loop")]),
            "issue_count": len(validation_issues),
            "issue_codes": _dedupe([str(issue.get("code") or "") for issue in validation_issues if issue.get("code")]),
            "action": "Narrow overly broad prompts, split large batches, or repair the agent output schema before rerun.",
        })

    chain_loops: list[str] = []
    chain_codes: list[str] = []
    for flag in batch_attention_flags(runs):
        code = str(flag.get("code") or "")
        if code not in {"short_run", "not_submitted", "crash_traceback"}:
            continue
        loop = str(flag.get("loop") or "")
        if loop:
            chain_loops.append(loop)
        chain_codes.append(code)
    if chain_loops:
        hints.append({
            "code": "complete_agent_chain",
            "severity": "warning",
            "loops": _dedupe(chain_loops),
            "attention_codes": _dedupe(chain_codes),
            "action": "Repair the prompt, verifier, or agent flow so the loop reaches the required turns and final submit boundary before judging business writes.",
        })

    remaining = _dedupe([str(loop) for loop in (remaining_loops or []) if loop])
    if remaining:
        hints.append({
            "code": "resume_unfinished_loops",
            "severity": "warning",
            "loops": remaining,
            "action": "Resume or rerun these loops after reviewing interruption metadata; they have no final evidence in this batch.",
        })

    resources = batch_created_resources(runs)
    if resources:
        hints.append({
            "code": "audit_execute_side_effects",
            "severity": "warning",
            "loops": _dedupe([str(resource.get("loop") or "") for resource in resources if resource.get("loop")]),
            "resource_count": len(resources),
            "action": "Audit partial execute-mode side effects before retrying or cleaning up created resources.",
        })
    return hints


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


def _looks_like_test_data_failure(reason: str) -> bool:
    lowered = reason.lower()
    if any(
        marker in lowered
        for marker in (
            "validationerror",
            "validation errors for",
            "extra_forbidden",
            "literal_error",
            "agentresponseparseerror",
        )
    ):
        return False
    needles = [
        "archived",
        "not a valid",
        "invalid",
        "conflicting",
        "location",
        "targeting",
        "video_id",
        "campaign",
        "adset",
        "creative",
        "material",
        "素材",
        "归档",
        "冲突",
        "无效",
    ]
    return any(needle in lowered for needle in needles)


def render_batch_html(record: dict[str, Any], batch_dir: Path) -> str:
    rows = []
    runs = list(record["runs"])
    attempt_marks = _loop_attempt_marks(runs)
    for index, run in enumerate(runs, start=1):
        href = _run_report_href(run, batch_dir)
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{html.escape(attempt_marks[index - 1])}</td>"
            f"<td>{html.escape(str(run['loop']))}</td>"
            f"<td>{html.escape(str(run['status']))}</td>"
            f"<td>{html.escape(str(run.get('mode') or '-'))}</td>"
            f"<td>{html.escape(str(run['run_id']))}</td>"
            f"<td>{html.escape(format_metrics(run.get('metrics') or {}))}</td>"
            f"<td>{html.escape(str(run['summary']))}</td>"
            f"<td><a href=\"{html.escape(href)}\">Open report</a></td>"
            "</tr>"
        )
    loop_attempts_html = _render_loop_attempts(runs, batch_dir)
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
    created_rows = []
    for resource in record.get("created_resources") or []:
        if not isinstance(resource, dict):
            continue
        created_rows.append(
            "<tr>"
            f"<td>{html.escape(str(resource.get('loop') or '-'))}</td>"
            f"<td>{html.escape(str(resource.get('run_id') or '-'))}</td>"
            f"<td>{html.escape(str(resource.get('type') or 'resource'))}</td>"
            f"<td>{html.escape(str(resource.get('id') or '-'))}</td>"
            f"<td>{html.escape(str(resource.get('source') or '-'))}</td>"
            "</tr>"
        )
    created_html = (
        "<h2>Created Resources</h2>"
        "<p class=\"meta\">Audit these execute-mode side effects before retrying or cleaning up.</p>"
        "<table><thead><tr><th>Loop</th><th>Run</th><th>Type</th><th>ID</th><th>Source</th></tr></thead><tbody>"
        + "".join(created_rows)
        + "</tbody></table>"
    ) if created_rows else ""
    failed_item_rows = []
    for item in record.get("failed_items") or []:
        if not isinstance(item, dict):
            continue
        failed_item_rows.append(
            "<tr>"
            f"<td>{html.escape(str(item.get('loop') or '-'))}</td>"
            f"<td>{html.escape(str(item.get('run_id') or '-'))}</td>"
            f"<td>{html.escape(str(item.get('type') or 'resource'))}</td>"
            f"<td>{html.escape(str(item.get('id') or '-'))}</td>"
            f"<td>{html.escape(str(item.get('name') or '-'))}</td>"
            f"<td>{html.escape(str(item.get('error') or '-'))}</td>"
            f"<td>{html.escape(str(item.get('source') or '-'))}</td>"
            "</tr>"
        )
    failed_items_html = (
        "<h2>Failed Items</h2>"
        "<p class=\"meta\">Use these IDs and errors to repair prompts, fixtures, or source data before rerun.</p>"
        "<table><thead><tr><th>Loop</th><th>Run</th><th>Type</th><th>ID</th><th>Name</th><th>Error</th><th>Source</th></tr></thead><tbody>"
        + "".join(failed_item_rows)
        + "</tbody></table>"
    ) if failed_item_rows else ""
    validation_rows = []
    for issue in record.get("validation_issues") or []:
        if not isinstance(issue, dict):
            continue
        validation_rows.append(
            "<tr>"
            f"<td>{html.escape(str(issue.get('loop') or '-'))}</td>"
            f"<td>{html.escape(str(issue.get('run_id') or '-'))}</td>"
            f"<td>{html.escape(str(issue.get('code') or '-'))}</td>"
            f"<td>{html.escape(str(issue.get('object') or '-'))}</td>"
            f"<td>{html.escape(str(issue.get('count') or '-'))}</td>"
            f"<td>{html.escape(str(issue.get('types') or '-'))}</td>"
            f"<td>{html.escape(str(issue.get('path') or '-'))}</td>"
            f"<td>{html.escape(str(issue.get('message') or '-'))}</td>"
            f"<td>{html.escape(str(issue.get('source') or '-'))}</td>"
            "</tr>"
        )
    validation_html = (
        "<h2>Validation Issues</h2>"
        "<p class=\"meta\">Schema and parser failures usually need prompt narrowing, output-shape fixes, or smaller execution batches before rerun.</p>"
        "<table><thead><tr><th>Loop</th><th>Run</th><th>Code</th><th>Object</th><th>Count</th><th>Types</th><th>Path</th><th>Message</th><th>Source</th></tr></thead><tbody>"
        + "".join(validation_rows)
        + "</tbody></table>"
    ) if validation_rows else ""
    attention_rows = []
    for flag in record.get("attention_flags") or []:
        if not isinstance(flag, dict):
            continue
        attention_rows.append(
            "<tr>"
            f"<td>{html.escape(str(flag.get('loop') or '-'))}</td>"
            f"<td>{html.escape(str(flag.get('run_id') or '-'))}</td>"
            f"<td>{html.escape(str(flag.get('severity') or 'warning'))}</td>"
            f"<td>{html.escape(str(flag.get('code') or '-'))}</td>"
            f"<td>{html.escape(str(flag.get('message') or '-'))}</td>"
            "</tr>"
        )
    attention_html = (
        "<h2>Attention Flags</h2>"
        "<table><thead><tr><th>Loop</th><th>Run</th><th>Severity</th><th>Code</th><th>Message</th></tr></thead><tbody>"
        + "".join(attention_rows)
        + "</tbody></table>"
    ) if attention_rows else ""
    repair_rows = []
    for hint in record.get("repair_hints") or []:
        if not isinstance(hint, dict):
            continue
        loops = ", ".join(str(loop) for loop in hint.get("loops") or [])
        details = "; ".join(str(reason) for reason in hint.get("reasons") or [])
        if hint.get("attention_codes"):
            details = "; ".join(str(code) for code in hint.get("attention_codes") or [])
        if hint.get("resource_count") is not None:
            details = f"{hint.get('resource_count')} resources"
        repair_rows.append(
            "<tr>"
            f"<td>{html.escape(str(hint.get('severity') or 'info'))}</td>"
            f"<td>{html.escape(str(hint.get('code') or '-'))}</td>"
            f"<td>{html.escape(loops or '-')}</td>"
            f"<td>{html.escape(details or '-')}</td>"
            f"<td>{html.escape(str(hint.get('action') or '-'))}</td>"
            "</tr>"
        )
    repair_html = (
        "<h2>Repair Hints</h2>"
        "<table><thead><tr><th>Severity</th><th>Code</th><th>Loops</th><th>Details</th><th>Action</th></tr></thead><tbody>"
        + "".join(repair_rows)
        + "</tbody></table>"
    ) if repair_rows else ""
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
    current_run = record.get("current_run") if isinstance(record.get("current_run"), dict) else None
    current_run_html = ""
    if current_run:
        href = os.path.relpath(Path(str(current_run.get("html_report_path") or batch_dir / "index.html")), batch_dir)
        current_run_html = (
            "<section class=\"summary\">"
            "<h2>Current Run</h2>"
            f"<p>Loop: {html.escape(str(current_run.get('loop') or '-'))}</p>"
            f"<p>Status: {html.escape(str(current_run.get('status') or '-'))}</p>"
            f"<p>Step: {html.escape(str(current_run.get('current_step') or '-'))}</p>"
            f"<p>Run: {html.escape(str(current_run.get('run_id') or '-'))}</p>"
            f"<p><a href=\"{html.escape(href)}\">Open live report</a></p>"
            "</section>"
        )
    interruption = record.get("interruption") if isinstance(record.get("interruption"), dict) else None
    interruption_html = ""
    if interruption:
        interruption_html = (
            "<p class=\"notice\">Interrupted: "
            f"{html.escape(str(interruption.get('type') or 'unknown'))}"
            f"{': ' + html.escape(str(interruption.get('message'))) if interruption.get('message') else ''}"
            "</p>"
        )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Meguri Batch {html.escape(str(record['batch_id']))}</title>"
        f"<style>{BATCH_GLOW_CSS}</style></head><body>{GLOW_BACKGROUND_HTML}<main>"
        f"<h1>Meguri Batch {html.escape(str(record['batch_id']))}</h1>"
        f"<p>Status: <span class=\"status\">{html.escape(str(record['status']))}</span></p>"
        f"{interruption_html}"
        f"<p class=\"meta\">{source}Progress: {html.escape(str(record.get('completed_loops', 0)))}"
        f" / {html.escape(str(record.get('total_loops', len(record.get('runs') or []))))} loops"
        f"{current}"
        f"<br>Started: {html.escape(str(record.get('started_at') or '-'))}"
        f"<br>Updated: {html.escape(str(record.get('updated_at') or '-'))}"
        f"<br>Finished: {html.escape(str(record.get('finished_at') or '-'))}</p>"
        + current_run_html
        + summary_html
        + loop_attempts_html
        + repair_html
        + attention_html
        + validation_html
        + failed_items_html
        + created_html
        + groups_html
        + "<table><thead><tr><th>#</th><th>Attempt</th><th>Loop</th><th>Status</th><th>Mode</th><th>Run</th><th>Metrics</th><th>Summary</th><th>Report</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table></main></body></html>"
    )


def _render_loop_attempts(runs: list[dict[str, Any]], batch_dir: Path) -> str:
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for run in runs:
        loop = str(run.get("loop") or "-")
        if loop not in groups:
            groups[loop] = []
            order.append(loop)
        groups[loop].append(run)
    rows = []
    for loop in order:
        attempts = groups[loop]
        if len(attempts) <= 1:
            continue
        items = []
        for attempt_index, run in enumerate(attempts, start=1):
            href = _run_report_href(run, batch_dir)
            run_id = str(run.get("run_id") or "-")
            status = str(run.get("status") or "-")
            summary = str(run.get("summary") or "-")
            items.append(
                "<li>"
                f"<a href=\"{html.escape(href)}\">Attempt {attempt_index}</a>"
                f"<span class=\"meta\">run {html.escape(run_id)} - {html.escape(status)} - {html.escape(summary)}</span>"
                "</li>"
            )
        rows.append(
            "<tr>"
            f"<td>{html.escape(loop)}</td>"
            f"<td>{len(attempts)}</td>"
            f"<td>{html.escape(str(attempts[-1].get('status') or '-'))}</td>"
            f"<td><ol class=\"attempt-list\">{''.join(items)}</ol></td>"
            "</tr>"
        )
    if not rows:
        return ""
    return (
        "<h2>Loop Attempts</h2>"
        "<p class=\"meta\">Loops with retries inside this batch are grouped here; each attempt keeps its own run report.</p>"
        "<table><thead><tr><th>Loop</th><th>Attempts</th><th>Latest status</th><th>Records</th></tr></thead><tbody>"
        + "".join(rows)
        + "</tbody></table>"
    )


def _loop_attempt_marks(runs: list[dict[str, Any]]) -> list[str]:
    totals: dict[str, int] = {}
    for run in runs:
        loop = str(run.get("loop") or "-")
        totals[loop] = totals.get(loop, 0) + 1
    seen: dict[str, int] = {}
    marks = []
    for run in runs:
        loop = str(run.get("loop") or "-")
        seen[loop] = seen.get(loop, 0) + 1
        total = totals.get(loop, 1)
        marks.append(f"{seen[loop]} / {total}" if total > 1 else "-")
    return marks


def _run_report_href(run: dict[str, Any], batch_dir: Path) -> str:
    report_path = Path(str(run.get("html_report_path") or batch_dir / "index.html"))
    return os.path.relpath(report_path, batch_dir)


def _dedupe(values: list[str]) -> list[str]:
    deduped = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped
