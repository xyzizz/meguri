from __future__ import annotations

from meguri.core.models import RunReport


def render_markdown_report(report: RunReport) -> str:
    loop_name = _loop_name(report)
    lines = [
        f"# Meguri Loop Run: {loop_name}",
        "",
        f"- run_id: `{report.run_id}`",
        f"- loop: `{loop_name}`",
        f"- status: `{report.status}`",
        f"- project: `{report.project_path}`",
        f"- artifacts: `{report.artifact_dir}`",
        "",
        "## Steps",
        "",
    ]
    for step in report.steps:
        lines.extend([
            f"### {step.step_id}",
            "",
            f"- status: `{step.status}`",
            f"- exit_code: `{step.exit_code}`",
            f"- started_at: `{step.started_at}`",
            f"- finished_at: `{step.finished_at}`",
            "",
            "| Check | Status | Message |",
            "| --- | --- | --- |",
        ])
        for check in step.checks:
            lines.append(f"| `{check.id}` | `{check.status}` | {check.message} |")
        if not step.checks:
            lines.append("| - | - | no checks |")
        lines.append("")
    return "\n".join(lines)


def _loop_name(report: RunReport) -> str:
    return str(report.metadata.get("loop_id") or report.scenario_name)
