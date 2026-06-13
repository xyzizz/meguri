from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from typing import Any

from meguri.core.models import RunReport


def render_html_report(report: RunReport) -> str:
    status_class = html.escape(report.status)
    loop_name = str(report.metadata.get("loop_id") or report.scenario_name)
    metadata = {
        "run_id": report.run_id,
        "loop": loop_name,
        "scenario_file_name": report.scenario_name,
        "status": report.status,
        "started_at": report.started_at,
        "finished_at": report.finished_at,
        "project_path": report.project_path,
        "artifact_dir": report.artifact_dir,
    }
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
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>{html.escape(loop_name)}</h1>
        <p>{html.escape(report.run_id)} · {html.escape(_duration_text(report.started_at, report.finished_at))}</p>
      </div>
      <div class="status {status_class}">{html.escape(report.status)}</div>
    </header>
    <section class="summary" aria-label="Run summary">
      {_metric("Project", report.project_path)}
      {_metric("Loop", loop_name)}
      {_metric("Artifacts", report.artifact_dir)}
      {_metric("Started", report.started_at)}
      {_metric("Finished", report.finished_at)}
    </section>
    <section>
      <h2>Steps</h2>
      <div class="steps">
        {''.join(_render_step(step) for step in report.steps)}
      </div>
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
