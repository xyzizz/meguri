from __future__ import annotations

import html
import json
import os
from pathlib import Path
from typing import Any

from meguri.reports.theme import GLOW_BACKGROUND_HTML, GLOW_BASE_CSS


def render_project_index(pack_root: Path) -> str:
    loops = _loop_summaries(pack_root)
    batch_records = _batch_summaries(pack_root)
    batches = [record for record in batch_records if not _is_report_snapshot(record)]
    snapshots = [record for record in batch_records if _is_report_snapshot(record)]
    standalone_runs = _standalone_run_summaries(pack_root)
    latest_activity = _latest_activity(loops, batches, standalone_runs, snapshots)
    latest_update = latest_activity[0]["timestamp"] if latest_activity else "-"
    attention_count = sum(
        1
        for item in [*loops, *batches, *standalone_runs]
        if _status_key(item.get("status")) in {"fail", "blocked", "running", "warning"}
    )
    run_count = sum(int(loop["run_count"]) for loop in loops) + len(standalone_runs)
    body = (
        '<section class="workspace-kpis" aria-label="Workspace summary">'
        + _metric("Loops", str(len(loops)), "configured")
        + _metric("Runs", str(run_count), "recorded")
        + _metric("Batches", str(len(batches)), "run batches")
        + _metric("Needs attention", str(attention_count), "latest state")
        + "</section>"
        + _render_status_strip([*loops, *batches, *standalone_runs])
        + _render_activity(latest_activity)
        + _render_loop_table(loops)
        + _render_batch_table(batches)
        + _render_snapshot_table(snapshots)
        + _render_standalone_table(standalone_runs)
    )
    return _page(
        "Meguri Control Room",
        body,
        subtitle=f"Latest activity {_display_time(latest_update)}",
    )


def render_loop_index(loop_dir: Path) -> str:
    runs = [_run_summary(loop_dir.name, record, base_href="") for record in _run_records(loop_dir)]
    latest = runs[0] if runs else {}
    body = (
        '<section class="workspace-kpis" aria-label="Loop summary">'
        + _metric("Runs", str(len(runs)), "recorded")
        + _metric("Latest status", _label_for_status(str(latest.get("status") or "")), "current")
        + _metric("Latest run", str(latest.get("run_id") or "-"), "run id")
        + _metric("Replay", str(latest.get("replay_status") or "-"), "latest")
        + "</section>"
        + _render_run_table(runs)
    )
    return _page(
        f"Loop {loop_dir.name}",
        body,
        eyebrow="Loop Detail",
        subtitle=f"{loop_dir.name} run history",
        back_href="../../index.html",
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
            record = dict(raw)
            record.setdefault("run_id", child.name)
            record["_dir_name"] = child.name
            record["_dir_path"] = str(child)
            records.append(record)
    return records


def _batch_records(pack_root: Path) -> list[dict[str, Any]]:
    batches_dir = pack_root / "batches"
    batch_dirs = sorted(
        [path for path in batches_dir.iterdir() if path.is_dir()],
        reverse=True,
    ) if batches_dir.is_dir() else []
    records = []
    for child in batch_dirs:
        batch_json = child / "batch.json"
        if not batch_json.is_file():
            continue
        try:
            raw = json.loads(batch_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(raw, dict):
            record = dict(raw)
            record.setdefault("batch_id", child.name)
            record["_dir_name"] = child.name
            record["_dir_path"] = str(child)
            records.append(record)
    return records


def _standalone_run_summaries(pack_root: Path) -> list[dict[str, Any]]:
    runs_dir = pack_root / "runs"
    records = _run_records(runs_dir)
    return [_run_summary("", record, base_href="runs/") for record in records]


def _loop_summaries(pack_root: Path) -> list[dict[str, Any]]:
    loops_dir = pack_root / "loops"
    loop_dirs = sorted([path for path in loops_dir.iterdir() if path.is_dir()]) if loops_dir.is_dir() else []
    summaries = []
    for loop_dir in loop_dirs:
        runs = _run_records(loop_dir)
        latest = runs[0] if runs else {}
        latest_run = _run_summary(loop_dir.name, latest, base_href=f"loops/{loop_dir.name}/") if latest else {}
        summaries.append({
            "loop": loop_dir.name,
            "run_count": len(runs),
            "status": latest_run.get("status") or "",
            "mode": latest_run.get("mode") or "-",
            "timestamp": latest_run.get("timestamp") or "",
            "run_id": latest_run.get("run_id") or "-",
            "summary": latest_run.get("summary") or "No runs recorded",
            "href": f"loops/{loop_dir.name}/index.html",
            "latest_href": latest_run.get("href") or f"loops/{loop_dir.name}/index.html",
        })
    return summaries


def _batch_summaries(pack_root: Path) -> list[dict[str, Any]]:
    summaries = []
    for record in _batch_records(pack_root):
        batch_id = str(record.get("batch_id") or record.get("_dir_name") or "")
        completed = record.get("completed_loops")
        total = record.get("total_loops")
        runs = record.get("runs") if isinstance(record.get("runs"), list) else []
        progress = f"{completed} / {total}" if completed is not None and total is not None else str(len(runs))
        current = str(record.get("current_loop") or "")
        summary = f"Current: {current}" if current else _batch_summary_text(record)
        summaries.append({
            "batch_id": batch_id,
            "status": str(record.get("status") or ""),
            "source": str(record.get("source") or ""),
            "progress": progress,
            "run_count": len(runs),
            "timestamp": _best_timestamp(record),
            "summary": summary or "-",
            "href": f"batches/{batch_id}/index.html",
        })
    return summaries


def _run_summary(loop_name: str, record: dict[str, Any], *, base_href: str) -> dict[str, Any]:
    run_id = str(record.get("run_id") or record.get("_dir_name") or "")
    replay = record.get("replay") if isinstance(record.get("replay"), dict) else {}
    replay_data = replay.get("replay") if isinstance(replay.get("replay"), dict) else {}
    href = f"{base_href}{run_id}/index.html" if run_id else "#"
    return {
        "loop": loop_name or str(record.get("loop") or "-"),
        "run_id": run_id or "-",
        "status": str(record.get("status") or ""),
        "mode": str(record.get("mode") or "-"),
        "timestamp": _best_timestamp(record),
        "summary": _summary_text(record),
        "replay_status": str(replay_data.get("status") or record.get("replay_status") or "-"),
        "href": href,
    }


def _latest_activity(
    loops: list[dict[str, Any]],
    batches: list[dict[str, Any]],
    standalone_runs: list[dict[str, Any]],
    snapshots: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    activity = []
    for loop in loops:
        if not loop.get("timestamp"):
            continue
        activity.append({
            "kind": "loop",
            "name": loop["loop"],
            "status": loop.get("status") or "",
            "timestamp": loop.get("timestamp") or "",
            "summary": loop.get("summary") or "-",
            "href": loop.get("latest_href") or loop.get("href") or "#",
        })
    for batch in batches:
        activity.append({
            "kind": "batch",
            "name": batch["batch_id"],
            "status": batch.get("status") or "",
            "timestamp": batch.get("timestamp") or "",
            "summary": f"{batch.get('progress') or '-'} loops - {batch.get('summary') or '-'}",
            "href": batch.get("href") or "#",
        })
    for run in standalone_runs:
        activity.append({
            "kind": "run",
            "name": run["run_id"],
            "status": run.get("status") or "",
            "timestamp": run.get("timestamp") or "",
            "summary": run.get("summary") or "-",
            "href": run.get("href") or "#",
        })
    for snapshot in snapshots or []:
        activity.append({
            "kind": "snapshot",
            "name": snapshot["batch_id"],
            "status": snapshot.get("status") or "",
            "timestamp": snapshot.get("timestamp") or "",
            "summary": f"{snapshot.get('source') or 'report'} - {snapshot.get('progress') or '-'} loops",
            "href": snapshot.get("href") or "#",
        })
    return sorted(activity, key=lambda item: str(item.get("timestamp") or ""), reverse=True)[:6]


def _render_status_strip(items: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for item in items:
        status = _status_key(item.get("status"))
        if status == "empty":
            continue
        counts[status] = counts.get(status, 0) + 1
    if not counts:
        return ""
    order = ["running", "fail", "blocked", "warning", "pass", "unknown"]
    chips = [
        f'<span class="status-chip status-{_esc(status)}">{_esc(_label_for_status(status))}: {_esc(str(counts[status]))}</span>'
        for status in order
        if status in counts
    ]
    return '<section class="status-strip" aria-label="Status counts">' + "".join(chips) + "</section>"


def _render_activity(items: list[dict[str, Any]]) -> str:
    rows = []
    for item in items:
        rows.append(
            '<a class="activity-row" '
            f'href="{_attr(str(item.get("href") or "#"))}">'
            f'<span class="activity-kind">{_esc(str(item.get("kind") or "-"))}</span>'
            f'<span class="activity-main"><strong>{_esc(str(item.get("name") or "-"))}</strong>'
            f'<span>{_esc(str(item.get("summary") or "-"))}</span></span>'
            f'{_status_badge(str(item.get("status") or ""))}'
            f'<span class="activity-time">{_esc(_display_time(str(item.get("timestamp") or "")))}</span>'
            "</a>"
        )
    content = "".join(rows) if rows else '<p class="empty-state">No activity recorded yet.</p>'
    return (
        '<section class="section-block">'
        '<div class="section-heading"><h2>Latest activity</h2></div>'
        f'<div class="activity-list">{content}</div>'
        "</section>"
    )


def _render_loop_table(loops: list[dict[str, Any]]) -> str:
    rows = []
    for loop in loops:
        rows.append(
            "<tr>"
            f'<td><a class="primary-link" href="{_attr(str(loop["href"]))}">{_esc(str(loop["loop"]))}</a>'
            f'<span class="cell-note">latest run { _esc(str(loop.get("run_id") or "-")) }</span></td>'
            f'<td>{_status_badge(str(loop.get("status") or ""))}<span class="cell-note">{_esc(_display_time(str(loop.get("timestamp") or "")))}</span></td>'
            f'<td>{_esc(str(loop.get("run_count") or 0))}</td>'
            f'<td><span class="token">{_esc(str(loop.get("mode") or "-"))}</span></td>'
            f'<td><span class="summary-text">{_esc(str(loop.get("summary") or "-"))}</span>'
            f'<a class="inline-action" href="{_attr(str(loop.get("latest_href") or loop["href"]))}">Open report</a></td>'
            "</tr>"
        )
    body = "".join(rows) if rows else '<tr><td colspan="5" class="empty-state">No loops configured yet.</td></tr>'
    return (
        '<section class="section-block">'
        '<div class="section-heading"><h2>Loops</h2></div>'
        '<div class="table-wrap"><table>'
        "<thead><tr><th>Loop</th><th>Latest</th><th>Runs</th><th>Mode</th><th>Evidence</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div></section>"
    )


def _render_batch_table(batches: list[dict[str, Any]]) -> str:
    rows = []
    for batch in batches:
        rows.append(
            "<tr>"
            f'<td><a class="primary-link" href="{_attr(str(batch["href"]))}">{_esc(str(batch["batch_id"]))}</a>'
            f'<span class="cell-note">{_esc(_display_time(str(batch.get("timestamp") or "")))}</span></td>'
            f'<td>{_status_badge(str(batch.get("status") or ""))}</td>'
            f'<td>{_esc(str(batch.get("progress") or "-"))}</td>'
            f'<td><span class="summary-text">{_esc(str(batch.get("summary") or "-"))}</span>'
            f'<a class="inline-action" href="{_attr(str(batch["href"]))}">Open batch</a></td>'
            "</tr>"
        )
    body = "".join(rows) if rows else '<tr><td colspan="4" class="empty-state">No batch runs recorded yet.</td></tr>'
    return (
        '<section class="section-block">'
        '<div class="section-heading"><h2>Batch Runs</h2></div>'
        '<div class="table-wrap"><table>'
        "<thead><tr><th>Batch</th><th>Status</th><th>Progress</th><th>Focus</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div></section>"
    )


def _render_snapshot_table(snapshots: list[dict[str, Any]]) -> str:
    if not snapshots:
        return ""
    rows = []
    for snapshot in snapshots:
        rows.append(
            "<tr>"
            f'<td><a class="primary-link" href="{_attr(str(snapshot["href"]))}">{_esc(str(snapshot["batch_id"]))}</a>'
            f'<span class="cell-note">{_esc(_display_time(str(snapshot.get("timestamp") or "")))}</span></td>'
            f'<td><span class="token">{_esc(str(snapshot.get("source") or "report"))}</span></td>'
            f'<td>{_status_badge(str(snapshot.get("status") or ""))}</td>'
            f'<td>{_esc(str(snapshot.get("progress") or "-"))}</td>'
            f'<td><span class="summary-text">{_esc(str(snapshot.get("summary") or "-"))}</span>'
            f'<a class="inline-action" href="{_attr(str(snapshot["href"]))}">Open snapshot</a></td>'
            "</tr>"
        )
    return (
        '<section class="section-block">'
        '<div class="section-heading"><h2>Report Snapshots</h2></div>'
        '<div class="table-wrap"><table>'
        "<thead><tr><th>Snapshot</th><th>Source</th><th>Status</th><th>Coverage</th><th>Focus</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div></section>"
    )


def _render_standalone_table(runs: list[dict[str, Any]]) -> str:
    if not runs:
        return ""
    rows = []
    for run in runs:
        rows.append(
            "<tr>"
            f'<td><a class="primary-link" href="{_attr(str(run["href"]))}">{_esc(str(run["run_id"]))}</a>'
            f'<span class="cell-note">{_esc(_display_time(str(run.get("timestamp") or "")))}</span></td>'
            f'<td>{_status_badge(str(run.get("status") or ""))}</td>'
            f'<td><span class="token">{_esc(str(run.get("mode") or "-"))}</span></td>'
            f'<td>{_esc(str(run.get("summary") or "-"))}</td>'
            "</tr>"
        )
    return (
        '<section class="section-block">'
        '<div class="section-heading"><h2>Standalone Runs</h2></div>'
        '<div class="table-wrap"><table>'
        "<thead><tr><th>Run</th><th>Status</th><th>Mode</th><th>Summary</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody></table></div></section>"
    )


def _render_run_table(runs: list[dict[str, Any]]) -> str:
    rows = []
    for run in runs:
        rows.append(
            "<tr>"
            f'<td><a class="primary-link" href="{_attr(str(run["href"]))}">{_esc(str(run["run_id"]))}</a>'
            f'<span class="cell-note">{_esc(_display_time(str(run.get("timestamp") or "")))}</span></td>'
            f'<td>{_status_badge(str(run.get("status") or ""))}</td>'
            f'<td><span class="token">{_esc(str(run.get("mode") or "-"))}</span></td>'
            f'<td><span class="token">{_esc(str(run.get("replay_status") or "-"))}</span></td>'
            f'<td><span class="summary-text">{_esc(str(run.get("summary") or "-"))}</span>'
            f'<a class="inline-action" href="{_attr(str(run["href"]))}">Open report</a></td>'
            "</tr>"
        )
    body = "".join(rows) if rows else '<tr><td colspan="5" class="empty-state">No runs recorded for this loop yet.</td></tr>'
    return (
        '<section class="section-block">'
        '<div class="section-heading"><h2>Run history</h2></div>'
        '<div class="table-wrap"><table class="run-history">'
        "<thead><tr><th>Run</th><th>Status</th><th>Mode</th><th>Replay</th><th>Evidence</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div></section>"
    )


def _metric(label: str, value: str, caption: str) -> str:
    return (
        '<div class="metric">'
        f"<span>{_esc(label)}</span>"
        f"<strong>{_esc(value)}</strong>"
        f"<small>{_esc(caption)}</small>"
        "</div>"
    )


def _status_badge(status: str) -> str:
    key = _status_key(status)
    return f'<span class="status-badge status-{_esc(key)}">{_esc(_label_for_status(key))}</span>'


def _is_report_snapshot(record: dict[str, Any]) -> bool:
    return bool(str(record.get("source") or ""))


def _status_key(status: object) -> str:
    value = str(status or "").strip().lower().replace("_", "-")
    if value in {"pass", "fail", "blocked", "running", "warning"}:
        return value
    if not value or value == "-":
        return "empty"
    return "unknown"


def _label_for_status(status: str) -> str:
    labels = {
        "pass": "pass",
        "fail": "fail",
        "blocked": "blocked",
        "running": "running",
        "warning": "warning",
        "empty": "not run",
        "unknown": "unknown",
    }
    return labels.get(_status_key(status), "unknown")


def _best_timestamp(record: dict[str, Any]) -> str:
    for key in ("updated_at", "finished_at", "started_at", "run_id", "batch_id"):
        value = record.get(key)
        if value:
            return str(value)
    return ""


def _display_time(value: str) -> str:
    if not value:
        return "-"
    return value.replace("T", " ").replace("+00:00", " UTC")


def _summary_text(record: dict[str, Any]) -> str:
    failure_reasons = record.get("failure_reasons")
    if isinstance(failure_reasons, list) and failure_reasons:
        return "; ".join(str(reason) for reason in failure_reasons if reason) or str(record.get("status") or "-")
    return str(record.get("summary") or record.get("status") or "-")


def _batch_summary_text(record: dict[str, Any]) -> str:
    failed_loops = record.get("failed_loops")
    if isinstance(failed_loops, list) and failed_loops:
        return "Failed: " + ", ".join(str(loop) for loop in failed_loops if loop)
    remaining_loops = record.get("remaining_loops")
    if isinstance(remaining_loops, list) and remaining_loops:
        return "Remaining: " + ", ".join(str(loop) for loop in remaining_loops if loop)
    return str(record.get("status") or "-")


def _esc(value: str) -> str:
    return html.escape(value, quote=False)


def _attr(value: str) -> str:
    return html.escape(_portable_href(value), quote=True)


def _portable_href(value: str) -> str:
    if not value:
        return "#"
    path = Path(value)
    if path.is_absolute():
        try:
            return os.path.relpath(path, Path.cwd())
        except ValueError:
            return value
    return value


def _page(
    title: str,
    body: str,
    *,
    eyebrow: str = "Workspace",
    subtitle: str = "",
    back_href: str | None = None,
) -> str:
    back = f'<a class="back-link" href="{_attr(back_href)}">Back to project</a>' if back_href else ""
    subtitle_html = f"<p>{_esc(subtitle)}</p>" if subtitle else ""
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_esc(title)}</title>"
        f"<style>{_INDEX_CSS}</style></head>"
        f"<body>{GLOW_BACKGROUND_HTML}<main>"
        f"{back}<header class=\"page-header\"><div><span class=\"eyebrow\">{_esc(eyebrow)}</span>"
        f"<h1>{_esc(title)}</h1>{subtitle_html}</div></header>{body}</main></body></html>"
    )


_INDEX_CSS = ("""
:root {
  color-scheme: light;
  --bg: oklch(0.985 0.004 250);
  --surface: oklch(1 0 0);
  --surface-soft: oklch(0.958 0.006 250);
  --ink: oklch(0.18 0.018 252);
  --muted: oklch(0.43 0.018 252);
  --line: oklch(0.88 0.008 252);
  --accent: oklch(0.42 0.12 205);
  --pass: oklch(0.43 0.13 150);
  --fail: oklch(0.52 0.18 28);
  --blocked: oklch(0.52 0.13 68);
  --warning: oklch(0.58 0.14 80);
  --unknown: oklch(0.45 0.018 252);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  color: var(--ink);
  background: var(--bg);
}
main {
  max-width: 1240px;
  margin: 0 auto;
  padding: 30px 24px 48px;
}
.back-link,
a {
  color: var(--accent);
  text-decoration-thickness: 1px;
  text-underline-offset: 3px;
}
a:hover { text-decoration-thickness: 2px; }
a:focus-visible,
button:focus-visible {
  outline: 3px solid color-mix(in oklch, var(--accent), transparent 70%);
  outline-offset: 3px;
}
.back-link {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  margin-bottom: 14px;
  font-weight: 650;
}
.page-header {
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: flex-end;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--line);
}
.eyebrow {
  display: block;
  margin-bottom: 6px;
  color: var(--muted);
  font-size: 0.82rem;
  font-weight: 700;
}
h1,
h2 {
  margin: 0;
  letter-spacing: 0;
  text-wrap: balance;
}
h1 {
  font-size: 1.7rem;
  line-height: 1.18;
}
h2 {
  font-size: 1rem;
  line-height: 1.3;
}
p {
  margin: 8px 0 0;
  color: var(--muted);
  max-width: 72ch;
}
.workspace-kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 10px;
  margin: 22px 0 12px;
}
.metric {
  min-height: 96px;
  padding: 14px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
}
.metric span,
.metric small,
.cell-note,
.activity-time,
.activity-kind {
  color: var(--muted);
}
.metric span,
.metric small {
  display: block;
}
.metric strong {
  display: block;
  margin: 5px 0 2px;
  font-size: 1.45rem;
  line-height: 1.15;
  overflow-wrap: anywhere;
}
.metric small {
  font-size: 0.8rem;
}
.status-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 0 0 24px;
}
.status-chip,
.status-badge,
.token {
  display: inline-flex;
  align-items: center;
  min-height: 26px;
  border-radius: 999px;
  padding: 3px 9px;
  font-weight: 700;
  white-space: nowrap;
}
.status-chip,
.status-badge {
  gap: 7px;
  border: 1px solid color-mix(in oklch, var(--status-color, var(--unknown)), white 58%);
  color: color-mix(in oklch, var(--status-color, var(--unknown)), black 14%);
  background: color-mix(in oklch, var(--status-color, var(--unknown)), white 88%);
}
.status-chip::before,
.status-badge::before {
  content: "";
  width: 7px;
  height: 7px;
  border-radius: 999px;
  background: var(--status-color, var(--unknown));
}
.status-pass { --status-color: var(--pass); }
.status-fail { --status-color: var(--fail); }
.status-blocked { --status-color: var(--blocked); }
.status-running { --status-color: var(--accent); }
.status-warning { --status-color: var(--warning); }
.status-empty,
.status-unknown { --status-color: var(--unknown); }
.token {
  border: 1px solid var(--line);
  background: var(--surface-soft);
  color: var(--ink);
  font-size: 0.82rem;
}
.section-block {
  margin-top: 24px;
}
.section-heading {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 10px;
}
.activity-list {
  display: grid;
  gap: 8px;
}
.activity-row {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr) auto minmax(132px, auto);
  gap: 12px;
  align-items: center;
  min-height: 58px;
  padding: 10px 12px;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
  color: inherit;
  text-decoration: none;
}
.activity-row:hover {
  border-color: color-mix(in oklch, var(--accent), white 35%);
  background: color-mix(in oklch, var(--accent), white 95%);
}
.activity-kind {
  font-size: 0.78rem;
  font-weight: 800;
}
.activity-main {
  min-width: 0;
}
.activity-main strong,
.activity-main span,
.cell-note,
.summary-text,
.inline-action {
  display: block;
}
.activity-main strong,
.primary-link {
  font-weight: 750;
  overflow-wrap: anywhere;
}
.activity-main span,
.summary-text {
  color: var(--muted);
  overflow-wrap: anywhere;
}
.table-wrap {
  overflow-x: auto;
  border: 1px solid var(--line);
  border-radius: 8px;
  background: var(--surface);
}
table {
  width: 100%;
  min-width: 760px;
  border-collapse: collapse;
}
th,
td {
  padding: 11px 12px;
  border-bottom: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}
tr:last-child td {
  border-bottom: 0;
}
th {
  color: var(--muted);
  font-size: 0.78rem;
  font-weight: 750;
}
td {
  overflow-wrap: anywhere;
}
.cell-note {
  margin-top: 3px;
  font-size: 0.8rem;
}
.inline-action {
  margin-top: 5px;
  font-weight: 650;
}
.empty-state {
  margin: 0;
  padding: 16px;
  color: var(--muted);
}
@media (max-width: 720px) {
  main { padding: 22px 14px 36px; }
  .page-header { display: block; }
  .workspace-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .activity-row {
    grid-template-columns: 1fr auto;
    align-items: start;
  }
  .activity-kind,
  .activity-time {
    grid-column: 1 / -1;
  }
}
@media (max-width: 440px) {
  .workspace-kpis { grid-template-columns: 1fr; }
}
""" + "\n" + GLOW_BASE_CSS + """
.back-link {
  color: var(--glow-primary);
}
.page-header,
.metric,
.activity-row,
.table-wrap {
  background: var(--surface);
  border: 1px solid var(--line);
  border-radius: 8px;
  box-shadow: var(--shadow-panel);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
}
.page-header {
  padding: 18px;
  align-items: center;
}
.eyebrow {
  color: var(--glow-accent);
  text-shadow: 0 0 16px rgba(180, 255, 219, 0.24);
}
.metric,
.activity-row,
.table-wrap {
  transition: transform 180ms ease, border-color 180ms ease, box-shadow 180ms ease;
}
.metric:hover,
.activity-row:hover {
  transform: translateY(-2px);
  border-color: var(--line-strong);
  background: var(--surface-strong);
  box-shadow: var(--shadow-panel), var(--shadow-glow);
}
.metric strong {
  color: var(--ink);
  text-shadow: 0 0 20px rgba(160, 196, 255, 0.2);
}
.status-chip,
.status-badge {
  border: 1px solid color-mix(in srgb, var(--status-color, var(--unknown)) 52%, transparent);
  color: var(--status-color, var(--unknown));
  background: color-mix(in srgb, var(--status-color, var(--unknown)) 13%, transparent);
  box-shadow: 0 0 18px color-mix(in srgb, var(--status-color, var(--unknown)) 22%, transparent);
}
.status-chip::before,
.status-badge::before {
  box-shadow: 0 0 12px var(--status-color, var(--unknown));
}
.token {
  color: var(--glow-primary);
  border: 1px solid rgba(160, 196, 255, 0.22);
  background: rgba(160, 196, 255, 0.08);
}
.activity-row {
  color: inherit;
}
.activity-row:hover {
  color: inherit;
}
.activity-kind {
  color: var(--glow-secondary);
}
.table-wrap {
  background: rgba(7, 10, 18, 0.42);
}
table {
  background: rgba(7, 10, 18, 0.26);
}
th,
td {
  border-bottom-color: var(--line);
}
tr:hover td {
  background: rgba(160, 196, 255, 0.045);
}
.inline-action,
.primary-link {
  color: var(--glow-primary);
}
.empty-state {
  color: var(--muted);
}
""").strip()
