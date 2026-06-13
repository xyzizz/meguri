from __future__ import annotations

import sys
from pathlib import Path

from meguri.scenarios.loader import load_scenario
from meguri.scenarios.runner import run_scenario


def test_load_dapper_example_scenario() -> None:
    root = Path(__file__).resolve().parents[1]
    scenario = load_scenario(root / "examples" / "dapper_assistant" / "scenarios" / "pre_submit_all_flows.yaml")

    assert scenario.name == "dapper_assistant_pre_submit_all_flows"
    assert scenario.adapter == "dapper_assistant"
    assert scenario.mode == "dry_run"
    assert scenario.project_path.name == "dapper_assistant"
    assert len(scenario.steps) == 3


def test_load_dapper_smoke_scenario() -> None:
    root = Path(__file__).resolve().parents[1]
    scenario = load_scenario(root / "examples" / "dapper_assistant" / "scenarios" / "pre_submit_smoke.yaml")

    assert scenario.name == "dapper_assistant_pre_submit_smoke"
    assert scenario.steps[0]["suite"] == "copy_campaign_prompt_nodes"


def test_shell_runner_writes_artifacts(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenario.yaml"
    scenario_path.write_text(
        f"""
name: shell_smoke
adapter: shell
project_path: "."
mode: dry_run
steps:
  - id: emit_json
    command:
      - "{sys.executable}"
      - "-c"
      - "import json; print(json.dumps({{'passed': True}}))"
    checks:
      - id: exit
        type: exit_code
        equals: 0
      - id: passed
        type: stdout_json_path
        path: $.passed
        equals: true
""",
        encoding="utf-8",
    )

    report = run_scenario(scenario_path, runs_dir=tmp_path / "runs")

    assert report.status == "pass"
    assert (Path(report.artifact_dir) / "run.json").is_file()
    assert (Path(report.artifact_dir) / "steps" / "emit_json" / "stdout.txt").is_file()
