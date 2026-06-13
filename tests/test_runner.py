from __future__ import annotations

import json
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


def test_runner_uses_loop_local_timestamp_directory_and_writes_replay(tmp_path: Path) -> None:
    loop_file = tmp_path / ".meguri" / "loops" / "shell_smoke" / "_loop.yaml"
    loop_file.parent.mkdir(parents=True)
    loop_file.write_text(
        f"""
name: shell_smoke
adapter: shell
project_path: "../../.."
mode: dry_run
metadata:
  kind: loop
  loop_id: shell_smoke
steps:
  - id: emit_env
    command:
      - "{sys.executable}"
      - "-c"
      - "import os; print(os.environ['MEGURI_LOOP_ID']); print(os.environ['MEGURI_RUN_DIR'])"
    checks:
      - id: exit
        type: exit_code
        equals: 0
""",
        encoding="utf-8",
    )

    report = run_scenario(loop_file, runs_dir=None)
    artifact_dir = Path(report.artifact_dir)

    assert artifact_dir.parent == loop_file.parent
    assert artifact_dir.name[:8].isdigit()
    assert (artifact_dir / "replay.json").is_file()
    replay = json.loads((artifact_dir / "replay.json").read_text(encoding="utf-8"))
    assert replay["loop_id"] == "shell_smoke"
    assert replay["scenario_path"] == str(loop_file)
