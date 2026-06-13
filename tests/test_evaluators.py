from __future__ import annotations

from meguri.core.models import StepResult
from meguri.evaluators.deterministic import evaluate_step_checks, extract_last_json, get_json_path


def test_extract_last_json_uses_final_summary() -> None:
    text = '{"case":"a","passed":true}\nnoise\n{"ok": true, "cases": 3}\n'

    assert extract_last_json(text) == {"ok": True, "cases": 3}


def test_extract_last_json_ignores_nested_late_arrays() -> None:
    text = 'log\n{"passed": false, "cases": [{"errors": [], "actual_cards": []}]}\n'

    assert extract_last_json(text)["passed"] is False


def test_get_json_path_reads_nested_values() -> None:
    assert get_json_path({"a": {"b": [10, 20]}}, "$.a.b.1") == 20


def test_evaluate_step_checks() -> None:
    step = StepResult(
        step_id="s1",
        status="pass",
        started_at="t0",
        finished_at="t1",
        exit_code=0,
        stdout='{"passed": true}',
        stderr="",
    )

    results = evaluate_step_checks(step, [
        {"id": "exit", "type": "exit_code", "equals": 0},
        {"id": "json", "type": "stdout_json_path", "path": "$.passed", "equals": True},
    ])

    assert [r.status for r in results] == ["pass", "pass"]


def test_stdout_json_checks_block_when_failed_step_has_no_json() -> None:
    step = StepResult(
        step_id="s1",
        status="fail",
        started_at="t0",
        finished_at="t1",
        exit_code=1,
        stdout="",
        stderr="Traceback: parser exploded",
    )

    results = evaluate_step_checks(step, [
        {"id": "exit", "type": "exit_code", "equals": 0},
        {"id": "passed", "type": "stdout_json_path", "path": "$.passed", "equals": True},
        {"id": "turn_count", "type": "stdout_json_path", "path": "$.turn_count", "equals": 7},
    ])

    assert [r.status for r in results] == ["fail", "blocked", "blocked"]
    assert all("stdout did not contain JSON" in r.message for r in results[1:])
