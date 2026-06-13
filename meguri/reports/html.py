from __future__ import annotations

import html
import json
import shlex
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from meguri.core.evidence import redact_value
from meguri.core.models import RunReport


def render_html_report(report: RunReport) -> str:
    status_class = html.escape(report.status)
    loop_name = str(report.metadata.get("loop_id") or report.scenario_name)
    evidence_attempts = _normalise_evidence_attempts(report.evidence)
    if not evidence_attempts and report.steps:
        evidence_attempts = _normalise_step_attempts(report)
    metadata = {
        "run_id": report.run_id,
        "loop": loop_name,
        "scenario_file_name": report.scenario_name,
        "status": report.status,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "project_path": report.project_path,
        "artifact_dir": report.artifact_dir,
        "evidence_warnings": report.evidence_warnings,
        "replay": report.replay,
    }
    main_view = _render_evidence_timeline(
        evidence_attempts,
        notice="" if report.evidence else "No structured evidence file found; showing step-level timeline.",
        fallback_html=_render_legacy_steps(report) if not report.evidence else "",
    ) if evidence_attempts else _render_legacy_steps(report)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Meguri Run {html.escape(report.run_id)}</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: oklch(1 0 0);
      --surface: oklch(0.965 0.003 250);
      --ink: oklch(0.17 0.018 255);
      --muted: oklch(0.44 0.018 255);
      --line: oklch(0.89 0.006 255);
      --pass: oklch(0.45 0.13 150);
      --fail: oklch(0.54 0.18 28);
      --blocked: oklch(0.52 0.13 65);
      --warning: oklch(0.58 0.15 80);
      --accent: oklch(0.43 0.14 35);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font: 14px/1.5 ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--ink);
      background: var(--bg);
    }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 32px 24px 48px; }}
    header {{
      display: flex;
      justify-content: space-between;
      gap: 20px;
      align-items: flex-start;
      padding-bottom: 24px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{ margin: 0 0 8px; font-size: 1.55rem; line-height: 1.2; letter-spacing: 0; text-wrap: balance; }}
    h2 {{ margin: 28px 0 12px; font-size: 1rem; letter-spacing: 0; }}
    h3 {{ margin: 0 0 10px; font-size: 0.95rem; }}
    p {{ margin: 0; color: var(--muted); }}
    code, pre {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .status {{
      display: inline-flex;
      align-items: center;
      min-height: 32px;
      padding: 4px 10px;
      border-radius: 999px;
      color: white;
      font-weight: 700;
      text-transform: uppercase;
      background: var(--accent);
    }}
    .status.pass {{ background: var(--pass); }}
    .status.fail {{ background: var(--fail); }}
    .status.blocked {{ background: var(--blocked); }}
    .status.warning {{ background: var(--warning); color: var(--ink); }}
    .status.running {{ background: var(--accent); }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 10px;
      margin: 24px 0;
    }}
    .metric {{ padding: 12px; background: var(--surface); border-radius: 8px; }}
    .metric span {{ display: block; color: var(--muted); font-size: 0.78rem; }}
    .metric strong {{ display: block; margin-top: 3px; overflow-wrap: anywhere; }}
    .steps {{ display: grid; gap: 14px; }}
    .step {{ border: 1px solid var(--line); border-radius: 10px; padding: 14px; }}
    .step-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; }}
    table {{ width: 100%; border-collapse: collapse; margin-top: 12px; }}
    th, td {{ padding: 9px 8px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 0.78rem; font-weight: 650; }}
    td {{ overflow-wrap: anywhere; }}
    a {{ color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 3px; }}
    details {{ margin-top: 10px; background: var(--surface); border-radius: 8px; padding: 10px 12px; }}
    summary {{ cursor: pointer; font-weight: 650; }}
    .notice {{ margin: 0 0 14px; padding: 10px 12px; background: var(--surface); border-left: 3px solid var(--warning); }}
    .timeline-shell {{ display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 20px; align-items: start; }}
    .attempts {{ display: grid; gap: 18px; min-width: 0; }}
    .attempt {{ border: 1px solid var(--line); border-radius: 10px; padding: 14px; overflow-x: auto; }}
    .attempt-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-bottom: 14px; }}
    .event-chain {{ display: flex; align-items: flex-start; gap: 0; min-width: max-content; padding: 4px 0 2px; }}
    .event-wrap {{ display: grid; grid-template-columns: 72px; justify-items: center; position: relative; }}
    .event-wrap:not(:last-child)::after {{
      content: "";
      position: absolute;
      top: 17px;
      left: 48px;
      width: 48px;
      height: 2px;
      background: var(--line);
    }}
    .event-node {{
      width: 34px;
      height: 34px;
      border-radius: 999px;
      border: 2px solid var(--line);
      background: white;
      color: var(--ink);
      font-weight: 750;
      cursor: pointer;
      position: relative;
      z-index: 1;
    }}
    .event-node.pass {{ border-color: var(--pass); }}
    .event-node.fail {{ border-color: var(--fail); color: var(--fail); }}
    .event-node.blocked {{ border-color: var(--blocked); color: var(--blocked); }}
    .event-node.warning {{ border-color: var(--warning); color: var(--ink); }}
    .event-node.running {{ border-color: var(--accent); color: var(--accent); }}
    .event-node.active {{ outline: 3px solid color-mix(in oklch, var(--accent), transparent 75%); }}
    .event-label {{ margin-top: 7px; width: 70px; color: var(--muted); font-size: 0.72rem; line-height: 1.2; text-align: center; overflow-wrap: anywhere; }}
    .detail-panel {{
      position: sticky;
      top: 18px;
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 14px;
      background: white;
      min-width: 0;
    }}
    .detail-panel dl {{ display: grid; grid-template-columns: 80px 1fr; gap: 4px 10px; margin: 0 0 12px; }}
    .detail-panel dt {{ color: var(--muted); }}
    .detail-panel dd {{ margin: 0; overflow-wrap: anywhere; }}
    .detail-panel h3 {{ margin-top: 14px; }}
    .detail-list {{ margin: 8px 0 0; padding-left: 18px; }}
    pre {{
      max-height: 260px;
      overflow: auto;
      margin: 10px 0 0;
      padding: 10px;
      background: white;
      border: 1px solid var(--line);
      border-radius: 6px;
      white-space: pre-wrap;
      overflow-wrap: anywhere;
    }}
    @media (max-width: 640px) {{
      main {{ padding: 22px 14px 36px; }}
      header {{ display: block; }}
      header .status {{ margin-top: 14px; }}
      .step-head {{ display: block; }}
      .timeline-shell {{ display: block; }}
      .detail-panel {{ position: static; margin-top: 16px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>{html.escape(loop_name)}</h1>
        <p>{html.escape(report.run_id)} · {html.escape(_duration_text(report.started_at, report.finished_at or report.updated_at))}</p>
      </div>
      <div class="status {status_class}">{html.escape(report.status)}</div>
    </header>
    <section class="summary" aria-label="Run summary">
      {_metric("Project", report.project_path)}
      {_metric("Loop", loop_name)}
      {_metric("Artifacts", report.artifact_dir)}
      {_metric("Started", report.started_at)}
      {_metric("Updated", report.updated_at or report.finished_at)}
      {_metric("Finished", report.finished_at or "-")}
    </section>
    {_render_replay(report, loop_name)}
    <section>
      {main_view}
    </section>
    <section>
      <h2>Metadata</h2>
      <pre>{html.escape(_pretty(metadata))}</pre>
    </section>
  </main>
</body>
</html>
"""


def _metric(label: str, value: str) -> str:
    return f'<div class="metric"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>'


def _render_replay(report: RunReport, loop_name: str) -> str:
    replay = report.replay if isinstance(report.replay, dict) else None
    if not replay:
        return ""
    replay_status = "-"
    if isinstance(replay.get("replay"), dict):
        replay_status = str(replay["replay"].get("status") or "-")
    loop = str(replay.get("loop_id") or loop_name)
    source_run_id = str(replay.get("source_run_id") or report.run_id)
    command = shlex.join(["meguri", "run", loop, "--replay", "replay.json", "--retry-of", source_run_id])
    return f"""
    <section>
      <h2>Replay</h2>
      <p class="notice">Status: {html.escape(replay_status)}. Re-run after repair with:</p>
      <pre>{html.escape(command)}</pre>
    </section>
"""


def _render_step(step: Any) -> str:
    checks = "".join(
        "<tr>"
        f"<td><code>{html.escape(check.id)}</code></td>"
        f"<td><span class=\"status {html.escape(check.status)}\">{html.escape(check.status)}</span></td>"
        f"<td>{html.escape(check.message)}</td>"
        "</tr>"
        for check in step.checks
    ) or '<tr><td colspan="3">No checks</td></tr>'
    artifacts = "".join(
        "<tr>"
        f"<td>{html.escape(artifact.kind)}</td>"
        f"<td><a href=\"{html.escape(_artifact_href(artifact.name))}\">{html.escape(artifact.name)}</a></td>"
        "</tr>"
        for artifact in step.artifacts
    ) or '<tr><td colspan="2">No artifacts</td></tr>'
    return f"""
<article class="step">
  <div class="step-head">
    <h3>{html.escape(step.step_id)}</h3>
    <span class="status {html.escape(step.status)}">{html.escape(step.status)}</span>
  </div>
  <p>exit_code={html.escape(str(step.exit_code))} · {_duration_text(step.started_at, step.finished_at)}</p>
  <table aria-label="Checks for {html.escape(step.step_id)}">
    <thead><tr><th>Check</th><th>Status</th><th>Message</th></tr></thead>
    <tbody>{checks}</tbody>
  </table>
  <details>
    <summary>Artifacts</summary>
    <table>
      <thead><tr><th>Kind</th><th>Path</th></tr></thead>
      <tbody>{artifacts}</tbody>
    </table>
  </details>
  <details>
    <summary>stdout excerpt</summary>
    <pre>{html.escape(_excerpt(step.stdout))}</pre>
  </details>
  <details>
    <summary>stderr excerpt</summary>
    <pre>{html.escape(_excerpt(step.stderr))}</pre>
  </details>
</article>
"""


def _render_legacy_steps(report: RunReport) -> str:
    return f"""
      <h2>Steps</h2>
      <div class="steps">
        {''.join(_render_step(step) for step in report.steps)}
      </div>
"""


def _render_evidence_timeline(attempts: list[dict[str, Any]], *, notice: str = "", fallback_html: str = "") -> str:
    events = _flatten_events(attempts)
    selected = _initial_event_index(events)
    event_json = _safe_json(events)
    attempt_html = "".join(_render_attempt(attempt, start_index=_attempt_start_index(attempts, attempt)) for attempt in attempts)
    notice_html = f'<p class="notice">{html.escape(notice)}</p>' if notice else ""
    return f"""
      <h2>Attempt Timeline</h2>
      {notice_html}
      <div class="timeline-shell">
        <div class="attempts">
          {attempt_html}
        </div>
        <aside class="detail-panel" id="detail-panel" aria-live="polite">
          <h2 id="detail-title">Select an event</h2>
          <dl id="detail-meta"></dl>
          <section><h3>Input</h3><pre id="detail-input"></pre></section>
          <section><h3>Output</h3><pre id="detail-output"></pre></section>
          <section id="detail-checks"></section>
          <section id="detail-artifacts"></section>
        </aside>
      </div>
      <script id="evidence-data" type="application/json">{event_json}</script>
      <script>
        (() => {{
          const events = JSON.parse(document.getElementById("evidence-data").textContent || "[]");
          const title = document.getElementById("detail-title");
          const meta = document.getElementById("detail-meta");
          const input = document.getElementById("detail-input");
          const output = document.getElementById("detail-output");
          const checks = document.getElementById("detail-checks");
          const artifacts = document.getElementById("detail-artifacts");
          const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[ch]));
          function render(index) {{
            const event = events[index];
            if (!event) return;
            document.querySelectorAll(".event-node").forEach((node) => node.classList.toggle("active", node.dataset.eventIndex === String(index)));
            title.textContent = event.title || event.id || "Event";
            meta.innerHTML = `
              <dt>Type</dt><dd>${{esc(event.type)}}</dd>
              <dt>Status</dt><dd>${{esc(event.status)}}</dd>
              <dt>Time</dt><dd>${{esc(event.time || "-")}}</dd>
              <dt>Attempt</dt><dd>${{esc(event.attempt_title || event.attempt_id || "-")}}</dd>
            `;
            input.textContent = event.input || "";
            output.textContent = event.output || "";
            checks.innerHTML = "<h3>Checks</h3>" + (event.checks || []).map((check) => `<li><strong>${{esc(check.status)}}</strong> ${{esc(check.id)}}: ${{esc(check.message)}}</li>`).join("");
            if (event.checks && event.checks.length) checks.innerHTML = `<h3>Checks</h3><ul class="detail-list">${{(event.checks || []).map((check) => `<li><strong>${{esc(check.status)}}</strong> ${{esc(check.id)}}: ${{esc(check.message)}}</li>`).join("")}}</ul>`;
            else checks.innerHTML = "<h3>Checks</h3><p>No checks</p>";
            if (event.artifacts && event.artifacts.length) artifacts.innerHTML = `<h3>Artifacts</h3><ul class="detail-list">${{event.artifacts.map((artifact) => `<li><a href="${{esc(artifact.path)}}">${{esc(artifact.label || artifact.path)}}</a></li>`).join("")}}</ul>`;
            else artifacts.innerHTML = "<h3>Artifacts</h3><p>No artifacts</p>";
          }}
          document.querySelectorAll(".event-node").forEach((node) => node.addEventListener("click", () => render(Number(node.dataset.eventIndex))));
          render({selected});
        }})();
      </script>
      {fallback_html}
"""


def _render_attempt(attempt: dict[str, Any], *, start_index: int) -> str:
    events = list(attempt.get("events") or [])
    nodes = []
    for offset, event in enumerate(events):
        index = start_index + offset
        status = html.escape(str(event.get("status") or "warning"))
        label = html.escape(_short_event_label(event))
        title = html.escape(str(event.get("title") or event.get("id") or f"Event {offset + 1}"))
        nodes.append(
            "<div class=\"event-wrap\">"
            f"<button class=\"event-node {status}\" data-event-index=\"{index}\" title=\"{title}\" aria-label=\"{title}\">{offset + 1}</button>"
            f"<div class=\"event-label\">{label}</div>"
            "</div>"
        )
    return f"""
<article class="attempt">
  <div class="attempt-head">
    <h3>{html.escape(str(attempt.get("title") or attempt.get("id") or "Attempt"))}</h3>
    <span class="status {html.escape(str(attempt.get("status") or "warning"))}">{html.escape(str(attempt.get("status") or "warning"))}</span>
  </div>
  <div class="event-chain">{''.join(nodes)}</div>
</article>
"""


def _normalise_evidence_attempts(evidence: list[Any]) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for bundle in evidence or []:
        raw_bundle = _plain(bundle)
        for attempt in list(raw_bundle.get("attempts") or []):
            raw_attempt = _plain(attempt)
            attempt_id = str(raw_attempt.get("id") or f"attempt_{len(attempts) + 1}")
            attempt_title = str(raw_attempt.get("title") or attempt_id)
            events = []
            for event in list(raw_attempt.get("events") or []):
                raw_event = _plain(event)
                checks = [_plain(check) for check in list(raw_event.get("checks") or [])]
                artifacts = [_plain(artifact) for artifact in list(raw_event.get("artifacts") or [])]
                events.append({
                    "id": str(raw_event.get("id") or f"event_{len(events) + 1}"),
                    "type": str(raw_event.get("type") or "note"),
                    "title": str(raw_event.get("title") or raw_event.get("id") or "Event"),
                    "status": str(raw_event.get("status") or "warning"),
                    "time": raw_event.get("time"),
                    "input": redact_value(raw_event.get("input")),
                    "output": redact_value(raw_event.get("output")),
                    "checks": [
                        {
                            "id": str(check.get("id") or "check"),
                            "status": str(check.get("status") or "blocked"),
                            "message": str(check.get("message") or ""),
                        }
                        for check in checks
                    ],
                    "artifacts": [
                        {
                            "label": str(artifact.get("label") or artifact.get("name") or artifact.get("path") or "artifact"),
                            "path": str(artifact.get("path") or artifact.get("name") or ""),
                        }
                        for artifact in artifacts
                    ],
                    "attempt_id": attempt_id,
                    "attempt_title": attempt_title,
                })
            attempts.append({
                "id": attempt_id,
                "title": attempt_title,
                "status": str(raw_attempt.get("status") or _status_from_events(events)),
                "events": events,
            })
    return attempts


def _normalise_step_attempts(report: RunReport) -> list[dict[str, Any]]:
    events = []
    for step in report.steps:
        artifacts = [
            {
                "label": str(getattr(artifact, "name", "") or getattr(artifact, "path", "") or "artifact"),
                "path": str(getattr(artifact, "name", "") or getattr(artifact, "path", "")),
            }
            for artifact in step.artifacts
        ]
        checks = [
            {
                "id": str(check.id),
                "status": str(check.status),
                "message": str(check.message),
            }
            for check in step.checks
        ]
        events.append({
            "id": str(step.step_id),
            "type": "step",
            "title": str(step.step_id),
            "status": str(step.status),
            "time": step.started_at,
            "input": f"exit_code={step.exit_code}",
            "output": _step_output(step),
            "checks": checks,
            "artifacts": artifacts,
            "attempt_id": "steps",
            "attempt_title": "Step Execution",
        })
    return [{
        "id": "steps",
        "title": "Step Execution",
        "status": str(report.status),
        "events": events,
    }]


def _step_output(step: Any) -> str:
    parts = []
    if step.stdout:
        parts.append(f"stdout:\n{step.stdout}")
    if step.stderr:
        parts.append(f"stderr:\n{step.stderr}")
    return "\n\n".join(parts)


def _plain(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        value = asdict(value)
    return value if isinstance(value, dict) else {}


def _flatten_events(attempts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for attempt in attempts:
        events.extend(list(attempt.get("events") or []))
    return events


def _attempt_start_index(attempts: list[dict[str, Any]], attempt: dict[str, Any]) -> int:
    index = 0
    for candidate in attempts:
        if candidate is attempt:
            return index
        index += len(list(candidate.get("events") or []))
    return index


def _initial_event_index(events: list[dict[str, Any]]) -> int:
    for index, event in enumerate(events):
        if event.get("status") in {"fail", "blocked"}:
            return index
    return 0


def _short_event_label(event: dict[str, Any]) -> str:
    event_type = str(event.get("type") or "event")
    mapping = {
        "user_input": "User",
        "model_output": "Model",
        "tool_call": "Tool",
        "check": "Check",
        "repair": "Repair",
        "rerun": "Rerun",
        "artifact": "Artifact",
        "note": "Note",
        "step": "Step",
    }
    return mapping.get(event_type, event_type[:10])


def _status_from_events(events: list[dict[str, Any]]) -> str:
    statuses = [str(event.get("status") or "") for event in events]
    if "fail" in statuses:
        return "fail"
    if "blocked" in statuses:
        return "blocked"
    if "warning" in statuses:
        return "warning"
    return "pass"


def _safe_json(value: Any) -> str:
    return html.escape(json.dumps(value, ensure_ascii=False, default=str).replace("</", "<\\/"))


def _artifact_href(name: str) -> str:
    return str(Path(name).as_posix())


def _excerpt(text: str, limit: int = 8000) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... truncated ..."


def _duration_text(started_at: str, finished_at: str) -> str:
    try:
        start = datetime.fromisoformat(started_at)
        finish = datetime.fromisoformat(finished_at)
        total = max(0.0, (finish - start).total_seconds())
        if total < 60:
            return f"{total:.1f}s"
        return f"{total / 60:.1f}m"
    except ValueError:
        return f"{started_at} -> {finished_at}"


def _pretty(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, indent=2, default=str)
