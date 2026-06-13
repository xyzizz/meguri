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


def test_runner_writes_legacy_scenario_runs_under_loop_history(tmp_path: Path) -> None:
    scenario_path = tmp_path / ".meguri" / "scenarios" / "legacy.yaml"
    scenario_path.parent.mkdir(parents=True)
    (tmp_path / ".meguri" / "project.yaml").write_text(
        "version: 1\nname: legacy-project\nproject_path: .\nruns_dir: .meguri/runs\n",
        encoding="utf-8",
    )
    scenario_path.write_text(
        f"""
name: legacy_shell
adapter: shell
project_path: "../.."
mode: dry_run
metadata:
  loop_id: legacy_smoke
steps:
  - id: emit
    command:
      - "{sys.executable}"
      - "-c"
      - "print('legacy ok')"
    checks:
      - id: exit
        type: exit_code
        equals: 0
""",
        encoding="utf-8",
    )

    report = run_scenario(scenario_path, runs_dir=None)
    artifact_dir = Path(report.artifact_dir)

    assert report.status == "pass"
    assert artifact_dir.parent == tmp_path / ".meguri" / "loops" / "legacy_smoke"
    assert not (tmp_path / ".meguri" / "runs").exists()
    assert (artifact_dir.parent / "index.html").is_file()
    assert (tmp_path / ".meguri" / "index.html").is_file()


def test_runner_replay_includes_nested_evidence_files(tmp_path: Path) -> None:
    loop_file = tmp_path / ".meguri" / "loops" / "agent_loop" / "_loop.yaml"
    loop_file.parent.mkdir(parents=True)
    loop_file.write_text(
        f"""
name: agent_loop
adapter: shell
project_path: "../../.."
mode: dry_run
metadata:
  loop_id: agent_loop
steps:
  - id: emit
    command:
      - "{sys.executable}"
      - "-c"
      - "import json, os, pathlib; path=pathlib.Path(os.environ['MEGURI_EVIDENCE_DIR']) / 'agent_multiturn_no_submit' / 'agent_loop' / '20260613-175923' / 'evidence.json'; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps({{'version': 1, 'loop_id': 'agent_loop', 'run_id': os.environ['MEGURI_RUN_ID'], 'attempts': [{{'id': 'attempt_1', 'title': 'Attempt 1', 'status': 'pass', 'events': [{{'id': 'turn_1', 'type': 'user_input', 'title': 'Prompt', 'status': 'pass', 'input': 'hello'}}]}}]}})); print('ok')"
    checks:
      - id: exit
        type: exit_code
        equals: 0
""",
        encoding="utf-8",
    )

    report = run_scenario(loop_file, runs_dir=None)
    replay = json.loads((Path(report.artifact_dir) / "replay.json").read_text(encoding="utf-8"))

    evidence_paths = [item["path"] for item in replay["inputs"]]
    assert "evidence/agent_multiturn_no_submit/agent_loop/20260613-175923/evidence.json" in evidence_paths
    assert report.replay["replay"]["status"] == "full"


def test_runner_refreshes_run_record_after_each_step(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenario.yaml"
    marker_path = tmp_path / "seen_incremental_record.txt"
    scenario_path.write_text(
        f"""
name: incremental_shell
adapter: shell
project_path: "."
mode: dry_run
steps:
  - id: first
    command:
      - "{sys.executable}"
      - "-c"
      - "print('first done')"
    checks:
      - id: exit
        type: exit_code
        equals: 0
  - id: second
    command:
      - "{sys.executable}"
      - "-c"
      - "import json, os, pathlib; data=json.loads(pathlib.Path(os.environ['MEGURI_RUN_DIR'], 'run.json').read_text()); pathlib.Path(r'{marker_path}').write_text(data['steps'][0]['step_id'])"
    checks:
      - id: exit
        type: exit_code
        equals: 0
""",
        encoding="utf-8",
    )

    report = run_scenario(scenario_path, runs_dir=tmp_path / "runs")

    assert report.status == "pass"
    assert marker_path.read_text(encoding="utf-8") == "first"


def test_runner_writes_running_step_snapshot_and_live_stdout(tmp_path: Path) -> None:
    scenario_path = tmp_path / "scenario.yaml"
    running_marker = tmp_path / "saw_running_snapshot.txt"
    live_stdout_marker = tmp_path / "saw_live_stdout.txt"
    scenario_path.write_text(
        f"""
name: live_shell
adapter: shell
project_path: "."
mode: dry_run
steps:
  - id: long
    command:
      - "{sys.executable}"
      - "-c"
      - "import json, os, pathlib, sys, time; run_dir=pathlib.Path(os.environ['MEGURI_RUN_DIR']); data=json.loads((run_dir / 'run.json').read_text()); pathlib.Path(r'{running_marker}').write_text(data['steps'][0]['status']); print('live hello', flush=True); stdout_path=run_dir / 'steps' / 'long' / 'stdout.txt'; deadline=time.time()+2;\\nwhile time.time() < deadline:\\n    if stdout_path.exists() and 'live hello' in stdout_path.read_text():\\n        pathlib.Path(r'{live_stdout_marker}').write_text('seen'); break\\n    time.sleep(0.02)\\nelse:\\n    sys.exit(7)"
    checks:
      - id: exit
        type: exit_code
        equals: 0
""",
        encoding="utf-8",
    )

    report = run_scenario(scenario_path, runs_dir=tmp_path / "runs")

    assert report.status == "pass"
    assert running_marker.read_text(encoding="utf-8") == "running"
    assert live_stdout_marker.read_text(encoding="utf-8") == "seen"
    stdout_path = Path(report.artifact_dir) / "steps" / "long" / "stdout.txt"
    assert "live hello" in stdout_path.read_text(encoding="utf-8")
