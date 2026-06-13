from __future__ import annotations

from pathlib import Path

from meguri.core.models import StepResult, RunReport, utc_now
from meguri.core.evidence import collect_evidence, redact_value
from meguri.reports.html import render_html_report


def test_collect_evidence_orders_events_by_time_and_preserves_file_order_fallback(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "agent.json").write_text(
        """
{
  "version": 1,
  "run_id": "20260613_152717",
  "loop_id": "agent_loop",
  "attempts": [
    {
      "id": "attempt_1",
      "title": "Attempt 1",
      "status": "fail",
      "events": [
        {"id": "late", "type": "model_output", "time": "2026-06-13T15:27:25+08:00", "title": "Late", "status": "pass", "output": "late"},
        {"id": "early", "type": "user_input", "time": "2026-06-13T15:27:18+08:00", "title": "Early", "status": "pass", "input": "early"},
        {"id": "no_time", "type": "note", "title": "No time", "status": "warning", "output": "kept last"}
      ]
    }
  ]
}
""",
        encoding="utf-8",
    )

    result = collect_evidence(
        run_evidence_dir=evidence_dir,
        project_evidence_dir=tmp_path / "project-evidence",
        loop_id="agent_loop",
        run_id="20260613_152717",
        run_started_at=None,
        run_dir=tmp_path,
    )

    assert result.warnings == []
    assert len(result.bundles) == 1
    events = result.bundles[0].attempts[0].events
    assert [event.id for event in events] == ["early", "late", "no_time"]


def test_collect_evidence_warns_on_parse_error_without_raising(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "broken.json").write_text("{", encoding="utf-8")

    result = collect_evidence(
        run_evidence_dir=evidence_dir,
        project_evidence_dir=tmp_path / "project-evidence",
        loop_id="agent_loop",
        run_id="20260613_152717",
        run_started_at=None,
        run_dir=tmp_path,
    )

    assert result.bundles == []
    assert "broken.json" in result.warnings[0]


def test_collect_evidence_recurses_project_evidence_and_preserves_relative_path(tmp_path: Path) -> None:
    run_evidence_dir = tmp_path / "run" / "evidence"
    project_evidence_file = (
        tmp_path
        / "project-evidence"
        / "agent_multiturn_no_submit"
        / "agent_loop"
        / "20260613-175923"
        / "evidence.json"
    )
    project_evidence_file.parent.mkdir(parents=True)
    project_evidence_file.write_text(
        """
{
  "version": 1,
  "run_id": "20260613_152717",
  "loop_id": "agent_loop",
  "attempts": [
    {
      "id": "attempt_1",
      "title": "Attempt 1",
      "status": "pass",
      "events": [
        {"id": "turn_1", "type": "model_output", "title": "Model", "status": "pass", "output": "nested evidence"}
      ]
    }
  ]
}
""",
        encoding="utf-8",
    )

    result = collect_evidence(
        run_evidence_dir=run_evidence_dir,
        project_evidence_dir=tmp_path / "project-evidence",
        loop_id="agent_loop",
        run_id="20260613_152717",
        run_started_at=None,
        run_dir=tmp_path / "run",
    )

    copied = (
        run_evidence_dir
        / "agent_multiturn_no_submit"
        / "agent_loop"
        / "20260613-175923"
        / "evidence.json"
    )
    assert copied.is_file()
    assert result.warnings == []
    assert len(result.bundles) == 1
    assert result.bundles[0].attempts[0].events[0].output == "nested evidence"


def test_redact_value_hides_explicit_redacted_object_and_secret_patterns() -> None:
    assert redact_value({"text": "Bearer sk-live-secret", "redacted": True, "redacted_label": "LLM token"}) == "[redacted: LLM token]"
    assert "secret" not in redact_value("Authorization: Bearer sk-live-secret")
    assert "pass" not in redact_value("postgres://user:pass@example.com/db")


def test_html_report_renders_evidence_timeline_and_detail_panel(tmp_path: Path) -> None:
    now = utc_now()
    report = RunReport(
        run_id="20260613_152717",
        scenario_name="agent_loop",
        status="pass",
        started_at=now,
        finished_at=now,
        project_path=str(tmp_path),
        artifact_dir=str(tmp_path),
        steps=[],
        checks=[],
        evidence=[
            {
                "loop_id": "agent_loop",
                "attempts": [
                    {
                        "id": "attempt_1",
                        "title": "Attempt 1",
                        "status": "pass",
                        "events": [
                            {
                                "id": "user_1",
                                "type": "user_input",
                                "title": "User input",
                                "status": "pass",
                                "input": "hello",
                                "output": None,
                                "checks": [],
                                "artifacts": [],
                            }
                        ],
                    }
                ],
            }
        ],
    )

    html = render_html_report(report)

    assert "Attempt Timeline" in html
    assert "detail-panel" in html
    assert "User input" in html
    assert "hello" in html


def test_html_report_renders_step_timeline_when_evidence_is_absent(tmp_path: Path) -> None:
    now = utc_now()
    report = RunReport(
        run_id="20260613_152717",
        scenario_name="agent_loop",
        status="fail",
        started_at=now,
        finished_at=now,
        project_path=str(tmp_path),
        artifact_dir=str(tmp_path),
        steps=[
            StepResult(
                step_id="agent_submit",
                status="fail",
                started_at=now,
                finished_at=now,
                exit_code=1,
                stdout="partial transcript before crash",
                stderr="invalid UUID in operation_log_id",
            )
        ],
        checks=[],
    )

    html = render_html_report(report)

    assert "Attempt Timeline" in html
    assert "No structured evidence file found; showing step-level timeline." in html
    assert "agent_submit" in html
    assert "partial transcript before crash" in html
    assert "invalid UUID in operation_log_id" in html


def test_html_report_renders_replay_command(tmp_path: Path) -> None:
    now = utc_now()
    report = RunReport(
        run_id="20260613_152717",
        scenario_name="agent_loop",
        status="fail",
        started_at=now,
        finished_at=now,
        project_path=str(tmp_path),
        artifact_dir=str(tmp_path),
        steps=[],
        checks=[],
        replay={
            "version": 1,
            "source_run_id": "20260613_152717",
            "loop_id": "agent_loop",
            "replay": {"status": "full", "missing": []},
        },
    )

    html = render_html_report(report)

    assert "Replay" in html
    assert "meguri run agent_loop --replay replay.json --retry-of 20260613_152717" in html
