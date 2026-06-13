from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import yaml

from meguri.cli.main import main


def _write_loop(tmp_path: Path, name: str, command: list[str]) -> None:
    loop_dir = tmp_path / ".meguri" / "loops" / name
    loop_dir.mkdir(parents=True, exist_ok=True)
    loop_dir.joinpath("_loop.yaml").write_text(
        yaml.safe_dump(
            {
                "name": name,
                "adapter": "shell",
                "project_path": "../../..",
                "mode": "dry_run",
                "metadata": {"kind": "loop", "loop_id": name, "source": "user"},
                "steps": [
                    {
                        "id": "run",
                        "command": command,
                        "checks": [{"id": "exit", "type": "exit_code", "equals": 0}],
                    }
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def test_init_creates_project_pack_and_skills(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    assert main(["init", "--install-skills"]) == 0

    assert (tmp_path / ".meguri" / "project.yaml").is_file()
    assert (tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml").is_file()
    assert (tmp_path / ".meguri" / "scenarios" / "smoke.yaml").is_file()
    assert (tmp_path / ".meguri" / "README.md").is_file()
    assert (tmp_path / ".agents" / "skills" / "meguri" / "SKILL.md").is_file()
    assert (tmp_path / ".claude" / "skills" / "meguri" / "SKILL.md").is_file()
    assert (tmp_path / ".claude" / "commands" / "meguri.md").is_file()
    assert (tmp_path / "home" / ".codex" / "prompts" / "meguri.md").is_file()
    smoke = yaml.safe_load((tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml").read_text(encoding="utf-8"))
    assert smoke["metadata"]["kind"] == "loop"
    assert smoke["metadata"]["loop_id"] == "smoke"
    assert smoke["metadata"]["source"] == "system"
    codex_skill = (tmp_path / ".agents" / "skills" / "meguri" / "SKILL.md").read_text(encoding="utf-8")
    claude_skill = (tmp_path / ".claude" / "skills" / "meguri" / "SKILL.md").read_text(encoding="utf-8")
    claude_command = (tmp_path / ".claude" / "commands" / "meguri.md").read_text(encoding="utf-8")
    codex_prompt = (tmp_path / "home" / ".codex" / "prompts" / "meguri.md").read_text(encoding="utf-8")
    assert "Meguri inspect workflow" in codex_skill
    assert "loop design" in codex_skill
    assert "evidence crash-safe" in codex_skill
    assert ".meguri/loops/<loop_id>/<run_id>/timeline.ndjson" in codex_skill
    assert "`run.json`, `report.md`, `index.html`" in codex_skill
    assert "meguri run <loop1> <loop2>" in codex_skill
    assert "meguri run --all --exclude <loop>" in codex_skill
    assert "meguri run <loop> --allow-execute" in codex_skill
    assert ".meguri/batches/<batch_id>/batch.json" in codex_skill
    assert "live progress surface" in codex_skill
    assert "meguri report <run_id> --json" in codex_skill
    assert "meguri report --last --json" in codex_skill
    assert "meguri report --recent <N>" in codex_skill
    assert "meguri report --recent <N> --json" in codex_skill
    assert "meguri report --runs <run_id-or-path> ..." in codex_skill
    assert "`status_counts`" in codex_skill
    assert "`failed_loops`" in codex_skill
    assert "batch `retry_command`" in codex_skill
    assert "batch `retry_loops`" in codex_skill
    assert "per-loop `mode`" in codex_skill
    assert "preserves `--allow-execute`" in codex_skill
    assert "per-loop `metrics`" in codex_skill
    assert "Replay command" in codex_skill
    assert "argument-hint: inspect|add|loops|delete|run|validate|report [args]" in codex_prompt
    assert "Use this active Codex session" in codex_prompt
    assert "MEGURI_EVIDENCE_DIR" in codex_prompt
    assert "--allow-execute" in codex_prompt
    assert "Meguri inspect workflow" in claude_skill
    assert "evidence crash-safe" in claude_skill
    assert "meguri run --all --exclude <loop>" in claude_skill
    assert "meguri run <loop> --allow-execute" in claude_skill
    assert "live progress surface" in claude_skill
    assert "meguri report <run_id> --json" in claude_skill
    assert "meguri report --last --json" in claude_skill
    assert "meguri report --recent <N>" in claude_skill
    assert "meguri report --recent <N> --json" in claude_skill
    assert "meguri report --runs <run_id-or-path> ..." in claude_skill
    assert "`status_counts`" in claude_skill
    assert "`failed_loops`" in claude_skill
    assert "batch `retry_command`" in claude_skill
    assert "batch `retry_loops`" in claude_skill
    assert "per-loop `mode`" in claude_skill
    assert "preserves `--allow-execute`" in claude_skill
    assert "per-loop `metrics`" in claude_skill
    assert "Replay command" in claude_skill
    assert "argument-hint: inspect|add|loops|delete|run|validate|report [args]" in claude_skill
    assert "Meguri verification loop workflow" in claude_command
    assert "MEGURI_EVIDENCE_DIR" in claude_command


def test_init_preserves_existing_files_without_force(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_yaml = tmp_path / ".meguri" / "project.yaml"
    project_yaml.parent.mkdir(parents=True)
    project_yaml.write_text("custom: true\n", encoding="utf-8")

    assert main(["init"]) == 0

    assert project_yaml.read_text(encoding="utf-8") == "custom: true\n"


def test_add_asks_for_clarification_without_required_information(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()

    assert main(["add", "login"]) == 2
    output = capsys.readouterr().out

    assert "Please clarify" in output
    assert "Provide --command" in output
    assert not (tmp_path / ".meguri" / "scenarios" / "login.yaml").exists()


def test_inspect_writes_current_agent_spec_only(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()

    assert main(["inspect"]) == 0
    output = capsys.readouterr().out

    prompt_path = tmp_path / ".meguri" / "prompts" / "inspect.md"
    assert prompt_path.is_file()
    prompt = prompt_path.read_text(encoding="utf-8")
    assert "specification and harness layer" in prompt
    assert "Use the active AI session" in prompt
    assert "understanding, loop design" in prompt
    assert ".meguri/project-inspect.json" in prompt
    assert "MEGURI_EVIDENCE_DIR" in prompt
    assert "Evidence must survive" in prompt
    assert "You are the current Codex / Claude Code agent" in output
    assert not (tmp_path / ".meguri" / "project-inspect.json").exists()
    assert not (tmp_path / ".meguri" / "project-brief.md").exists()


def test_inspect_requires_project_pack(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    assert main(["inspect"]) == 2
    assert "meguri init --install-skills" in capsys.readouterr().err


def test_add_writes_valid_scenario_when_required_fields_are_supplied(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0

    assert main([
        "add",
        "login flow",
        "--name",
        "login_flow",
        "--command",
        f"{sys.executable} -c \"print('ok')\"",
        "--pass-criteria",
        "command exits with ok",
    ]) == 0

    scenario_path = tmp_path / ".meguri" / "loops" / "login_flow" / "_loop.yaml"
    raw = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    assert raw["name"] == "login_flow"
    assert raw["adapter"] == "shell"
    assert raw["metadata"]["kind"] == "loop"
    assert raw["metadata"]["loop_id"] == "login_flow"
    assert raw["metadata"]["source"] == "user"
    assert raw["metadata"]["pass_criteria"] == "command exits with ok"


def test_loops_lists_user_added_loops_and_delete_removes_named_loop(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()

    assert main([
        "add",
        "checkout flow",
        "--name",
        "checkout",
        "--command",
        f"{sys.executable} -c \"print('ok')\"",
        "--pass-criteria",
        "command exits",
    ]) == 0
    capsys.readouterr()

    assert main(["loops"]) == 0
    output = capsys.readouterr().out
    assert "loops=1" in output
    assert "checkout" in output
    assert "smoke" not in output

    assert main(["loops", "--all"]) == 0
    output = capsys.readouterr().out
    assert "loops=2" in output
    assert "checkout" in output
    assert "smoke" in output

    assert main(["delete", "checkout"]) == 0
    output = capsys.readouterr().out
    assert "deleted loop checkout" in output
    assert not (tmp_path / ".meguri" / "loops" / "checkout").exists()

    assert main(["loops"]) == 0
    assert "loops=0" in capsys.readouterr().out


def test_delete_refuses_system_loop_without_force(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()

    assert main(["delete", "smoke"]) == 1
    output = capsys.readouterr().out
    assert "Refusing to delete system loop" in output
    assert (tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml").exists()


def test_run_alias_writes_project_local_html_report(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()

    assert main(["run", "smoke", "--json"]) == 0
    output = capsys.readouterr().out
    report = json.loads(output)

    assert report["status"] == "pass"
    html_path = Path(report["html_report_path"])
    assert html_path.is_file()
    assert html_path.parent.parent == tmp_path / ".meguri" / "loops" / "smoke"
    assert (html_path.parent / "replay.json").is_file()
    html = html_path.read_text(encoding="utf-8")
    assert "smoke" in html
    assert "passed" in html


def test_run_json_output_compacts_large_stdout(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()
    loop_path = tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml"
    raw = yaml.safe_load(loop_path.read_text(encoding="utf-8"))
    raw["steps"][0]["command"] = [sys.executable, "-c", "print('A' * 20000)"]
    raw["steps"][0]["checks"] = [{"id": "exit", "type": "exit_code", "equals": 0}]
    loop_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    assert main(["run", "smoke", "--json"]) == 0
    output = capsys.readouterr().out
    report = json.loads(output)

    step = report["steps"][0]
    assert len(step["stdout"]) < 9000
    assert step["stdout_truncated"] is True
    assert step["stdout_chars"] > 20000


def test_run_execute_loop_requires_explicit_approval(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()
    marker_path = tmp_path / "execute_ran.txt"
    _write_loop(
        tmp_path,
        "real_submit",
        [sys.executable, "-c", f"from pathlib import Path; Path(r'{marker_path}').write_text('ran', encoding='utf-8')"],
    )
    loop_path = tmp_path / ".meguri" / "loops" / "real_submit" / "_loop.yaml"
    raw = yaml.safe_load(loop_path.read_text(encoding="utf-8"))
    raw["mode"] = "execute"
    loop_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    assert main(["run", "real_submit"]) == 2
    assert "--allow-execute" in capsys.readouterr().err
    assert not marker_path.exists()

    assert main(["run", "real_submit", "--allow-execute"]) == 0
    assert marker_path.read_text(encoding="utf-8") == "ran"


def test_batch_retry_command_preserves_execute_approval(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()
    for loop_name in ("first_execute_fail", "second_execute_fail"):
        _write_loop(
            tmp_path,
            loop_name,
            [
                sys.executable,
                "-c",
                "import json, sys; print(json.dumps({'errors': ['target data invalid']})); sys.exit(5)",
            ],
        )
        loop_path = tmp_path / ".meguri" / "loops" / loop_name / "_loop.yaml"
        raw = yaml.safe_load(loop_path.read_text(encoding="utf-8"))
        raw["mode"] = "execute"
        loop_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    assert main(["run", "first_execute_fail", "second_execute_fail", "--allow-execute", "--json"]) == 1
    batch = json.loads(capsys.readouterr().out)

    assert [run["mode"] for run in batch["runs"]] == ["execute", "execute"]
    assert batch["retry_loops"] == ["first_execute_fail", "second_execute_fail"]
    assert batch["retry_command"] == "meguri run first_execute_fail second_execute_fail --allow-execute"
    html = Path(batch["html_report_path"]).read_text(encoding="utf-8")
    assert "<th>Mode</th>" in html
    assert "<td>execute</td>" in html
    assert "meguri run first_execute_fail second_execute_fail --allow-execute" in html


def test_run_multiple_loops_continues_in_order_after_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()
    marker_path = tmp_path / "second_loop_ran.txt"
    _write_loop(
        tmp_path,
        "first_fail",
        [
            sys.executable,
            "-c",
            (
                "import json, sys; "
                "print(json.dumps({'passed': False, 'errors': ['video_id is not valid'], "
                "'submit_results': [{'ok': False, 'error': 'archived campaign'}]})); "
                "sys.exit(3)"
            ),
        ],
    )
    _write_loop(
        tmp_path,
        "second_pass",
        [
            sys.executable,
            "-c",
            (
                "import json; "
                f"from pathlib import Path; Path(r'{marker_path}').write_text('ran', encoding='utf-8'); "
                "print(json.dumps({'turn_count': 7, 'submitted': True, 'closed_status_verified': True, "
                "'submit_results': [{'ok': True}, {'ok': True}]}))"
            ),
        ],
    )
    _write_loop(
        tmp_path,
        "third_fail",
        [
            sys.executable,
            "-c",
            (
                "import json, sys; "
                "print(json.dumps({'passed': False, 'errors': ['video_id is not valid']})); "
                "sys.exit(4)"
            ),
        ],
    )

    assert main(["run", "first_fail", "second_pass", "third_fail", "--json"]) == 1
    output = capsys.readouterr().out
    batch = json.loads(output)

    assert batch["status"] == "fail"
    assert [run["loop"] for run in batch["runs"]] == ["first_fail", "second_pass", "third_fail"]
    assert [run["status"] for run in batch["runs"]] == ["fail", "pass", "fail"]
    assert [run["mode"] for run in batch["runs"]] == ["dry_run", "dry_run", "dry_run"]
    assert batch["status_counts"] == {"fail": 2, "pass": 1}
    assert batch["failed_loops"] == ["first_fail", "third_fail"]
    assert batch["runs"][0]["summary"] == "video_id is not valid; archived campaign"
    assert batch["runs"][0]["failure_reasons"] == ["video_id is not valid", "archived campaign"]
    assert batch["runs"][1]["metrics"]["turn_count"] == 7
    assert batch["runs"][1]["metrics"]["submit_success_count"] == 2
    assert batch["failure_groups"][0] == {
        "reason": "video_id is not valid",
        "count": 2,
        "loops": ["first_fail", "third_fail"],
    }
    batch_dir = Path(batch["batch_dir"])
    assert batch_dir.parent == tmp_path / ".meguri" / "batches"
    assert batch["html_report_path"] == str(batch_dir / "index.html")
    assert (batch_dir / "batch.json").is_file()
    assert (batch_dir / "index.html").is_file()
    batch_record = json.loads((batch_dir / "batch.json").read_text(encoding="utf-8"))
    assert batch_record["status"] == "fail"
    assert [run["loop"] for run in batch_record["runs"]] == ["first_fail", "second_pass", "third_fail"]
    assert batch_record["status_counts"] == {"fail": 2, "pass": 1}
    assert batch_record["failed_loops"] == ["first_fail", "third_fail"]
    assert batch_record["retry_loops"] == ["first_fail", "third_fail"]
    assert batch_record["retry_command"] == "meguri run first_fail third_fail"
    html = (batch_dir / "index.html").read_text(encoding="utf-8")
    assert "first_fail" in html
    assert "Status Summary" in html
    assert "fail: 2" in html
    assert "pass: 1" in html
    assert "video_id is not valid" in html
    assert "2 loops" in html
    assert "Retry Failed Loops" in html
    assert "meguri run first_fail third_fail" in html
    assert "second_pass" in html
    assert marker_path.read_text(encoding="utf-8") == "ran"
    assert Path(batch["runs"][0]["html_report_path"]).is_file()
    assert Path(batch["runs"][1]["html_report_path"]).is_file()

    assert main(["report", "--last"]) == 0
    assert capsys.readouterr().out.strip() == batch["html_report_path"]


def test_run_multiple_loops_updates_batch_record_after_each_loop(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()
    marker_path = tmp_path / "batch_snapshot_seen.txt"
    _write_loop(
        tmp_path,
        "first_pass",
        [sys.executable, "-c", "print('first passed')"],
    )
    _write_loop(
        tmp_path,
        "second_probe",
        [
            sys.executable,
            "-c",
            (
                "import json, pathlib; "
                f"root = pathlib.Path(r'{tmp_path}') / '.meguri' / 'batches'; "
                "records = sorted(root.glob('*/batch.json')); "
                "assert records, 'batch record missing while second loop is running'; "
                "data = json.loads(records[-1].read_text(encoding='utf-8')); "
                "assert data['status'] == 'running', data; "
                "assert data['completed_loops'] == 1, data; "
                "assert data['planned_loops'] == ['first_pass', 'second_probe'], data; "
                "assert [run['loop'] for run in data['runs']] == ['first_pass'], data; "
                f"pathlib.Path(r'{marker_path}').write_text(data['runs'][0]['status'], encoding='utf-8')"
            ),
        ],
    )

    assert main(["run", "first_pass", "second_probe", "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)

    assert batch["status"] == "pass"
    assert batch["completed_loops"] == 2
    assert marker_path.read_text(encoding="utf-8") == "pass"
    batch_record = json.loads(Path(batch["batch_dir"]).joinpath("batch.json").read_text(encoding="utf-8"))
    assert batch_record["status"] == "pass"
    assert [run["loop"] for run in batch_record["runs"]] == ["first_pass", "second_probe"]


def test_run_multiple_loops_blocks_batch_when_interrupted(tmp_path: Path, monkeypatch, capsys) -> None:
    from meguri.core.models import RunReport, utc_now

    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()
    _write_loop(tmp_path, "first_pass", [sys.executable, "-c", "print('first')"])
    _write_loop(tmp_path, "second_interrupt", [sys.executable, "-c", "print('second')"])

    def fake_run_scenario(scenario_path, **kwargs):
        loop_id = scenario_path.parent.name
        if loop_id == "second_interrupt":
            raise KeyboardInterrupt()
        run_dir = tmp_path / ".meguri" / "loops" / loop_id / "20260613_120000"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "index.html").write_text("<html>first</html>", encoding="utf-8")
        now = utc_now()
        return RunReport(
            run_id=run_dir.name,
            scenario_name=loop_id,
            status="pass",
            started_at=now,
            finished_at=now,
            project_path=str(tmp_path),
            artifact_dir=str(run_dir),
            steps=[],
            checks=[],
            html_report_path=str(run_dir / "index.html"),
            metadata={"loop_id": loop_id},
            updated_at=now,
        )

    monkeypatch.setattr("meguri.cli.main.run_scenario", fake_run_scenario)

    with pytest.raises(KeyboardInterrupt):
        main(["run", "first_pass", "second_interrupt", "--json"])

    [batch_dir] = list((tmp_path / ".meguri" / "batches").iterdir())
    batch_record = json.loads((batch_dir / "batch.json").read_text(encoding="utf-8"))

    assert batch_record["status"] == "blocked"
    assert batch_record["completed_loops"] == 1
    assert batch_record["current_loop"] == "second_interrupt"
    assert batch_record["remaining_loops"] == ["second_interrupt"]
    assert batch_record["interrupted"] is True
    assert batch_record["interruption"]["type"] == "KeyboardInterrupt"
    assert [run["loop"] for run in batch_record["runs"]] == ["first_pass"]
    html = (batch_dir / "index.html").read_text(encoding="utf-8")
    assert "KeyboardInterrupt" in html


def test_run_all_user_loops_excludes_named_loop_and_system_smoke(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()
    ran_path = tmp_path / "ran.txt"
    _write_loop(
        tmp_path,
        "first_done",
        [sys.executable, "-c", f"from pathlib import Path; Path(r'{ran_path}').write_text('first', encoding='utf-8')"],
    )
    _write_loop(
        tmp_path,
        "second_todo",
        [sys.executable, "-c", f"from pathlib import Path; Path(r'{ran_path}').write_text('second', encoding='utf-8')"],
    )
    _write_loop(
        tmp_path,
        "third_todo",
        [sys.executable, "-c", f"from pathlib import Path; Path(r'{ran_path}').write_text(Path(r'{ran_path}').read_text(encoding='utf-8') + ',third', encoding='utf-8')"],
    )

    assert main(["run", "--all", "--exclude", "first_done", "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)

    assert batch["planned_loops"] == ["second_todo", "third_todo"]
    assert [run["loop"] for run in batch["runs"]] == ["second_todo", "third_todo"]
    assert "smoke" not in batch["planned_loops"]
    assert ran_path.read_text(encoding="utf-8") == "second,third"


def test_report_last_selects_newest_html_report(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    assert main(["run", "smoke"]) == 0
    capsys.readouterr()

    assert main(["report", "--last"]) == 0
    output = capsys.readouterr().out.strip()

    assert output.endswith("index.html")
    assert Path(output).is_file()


def test_report_last_prefers_run_json_time_over_directory_mtime(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()

    older = tmp_path / ".meguri" / "loops" / "checkout" / "20260613_100000"
    newer = tmp_path / ".meguri" / "loops" / "checkout" / "20260613_110000"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    for path, finished_at in [
        (older, "2026-06-13T10:00:00+00:00"),
        (newer, "2026-06-13T11:00:00+00:00"),
    ]:
        (path / "index.html").write_text("<html></html>", encoding="utf-8")
        (path / "run.json").write_text(
            json.dumps({"run_id": path.name, "status": "pass", "finished_at": finished_at}),
            encoding="utf-8",
        )

    os.utime(newer, (1_000_000_000, 1_000_000_000))
    os.utime(older, (2_000_000_000, 2_000_000_000))

    assert main(["report", "--last"]) == 0
    output = capsys.readouterr().out.strip()

    assert output.endswith("20260613_110000/index.html")


def test_report_last_uses_batch_updated_at_for_running_batch(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()

    loop_run = tmp_path / ".meguri" / "loops" / "checkout" / "20260613_110000"
    batch_run = tmp_path / ".meguri" / "batches" / "20260613_100000_000000"
    loop_run.mkdir(parents=True)
    batch_run.mkdir(parents=True)
    (loop_run / "index.html").write_text("<html>loop</html>", encoding="utf-8")
    (loop_run / "run.json").write_text(
        json.dumps({
            "run_id": loop_run.name,
            "status": "pass",
            "finished_at": "2026-06-13T11:00:00+00:00",
        }),
        encoding="utf-8",
    )
    (batch_run / "index.html").write_text("<html>batch</html>", encoding="utf-8")
    (batch_run / "batch.json").write_text(
        json.dumps({
            "batch_id": batch_run.name,
            "status": "running",
            "started_at": "2026-06-13T10:00:00+00:00",
            "updated_at": "2026-06-13T12:00:00+00:00",
            "finished_at": "",
            "runs": [{"loop": "checkout", "status": "pass"}],
        }),
        encoding="utf-8",
    )

    assert main(["report", "--last"]) == 0
    output = capsys.readouterr().out.strip()

    assert output.endswith("batches/20260613_100000_000000/index.html")


def test_report_recent_creates_batch_from_latest_standalone_runs(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()
    runs_root = tmp_path / ".meguri" / "runs"
    for run_id, loop, finished_at, message in [
        ("run_20260613_100000_old", "old_loop", "2026-06-13T10:00:00+00:00", "old reason"),
        ("run_20260613_110000_mid", "mid_loop", "2026-06-13T11:00:00+00:00", "video_id is not valid"),
        ("run_20260613_120000_new", "new_loop", "2026-06-13T12:00:00+00:00", "video_id is not valid"),
    ]:
        run_dir = runs_root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "index.html").write_text(f"<html>{loop}</html>", encoding="utf-8")
        (run_dir / "run.json").write_text(
            json.dumps({
                "run_id": run_id,
                "scenario_name": loop,
                "status": "fail",
                "mode": "execute",
                "finished_at": finished_at,
                "artifact_dir": str(run_dir),
                "metadata": {"loop_id": loop},
                "steps": [
                    {
                        "step_id": "run",
                        "status": "fail",
                        "checks": [{"id": "exit", "status": "fail", "message": message}],
                    }
                ],
            }),
            encoding="utf-8",
        )

    assert main(["report", "--recent", "2"]) == 0
    html_path = Path(capsys.readouterr().out.strip())

    assert html_path.parent.parent == tmp_path / ".meguri" / "batches"
    batch = json.loads(html_path.with_name("batch.json").read_text(encoding="utf-8"))
    assert batch["source"] == "recent_runs"
    assert batch["planned_loops"] == ["mid_loop", "new_loop"]
    assert [run["loop"] for run in batch["runs"]] == ["mid_loop", "new_loop"]
    assert [run["mode"] for run in batch["runs"]] == ["execute", "execute"]
    assert batch["status_counts"] == {"fail": 2}
    assert batch["failed_loops"] == ["mid_loop", "new_loop"]
    assert batch["retry_loops"] == ["mid_loop", "new_loop"]
    assert batch["retry_command"] == "meguri run mid_loop new_loop"
    assert batch["failure_groups"] == [{
        "reason": "video_id is not valid",
        "count": 2,
        "loops": ["mid_loop", "new_loop"],
    }]
    html = html_path.read_text(encoding="utf-8")
    assert "meguri run mid_loop new_loop" in html
    assert "old_loop" not in html


def test_report_runs_creates_batch_from_explicit_run_refs(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()
    runs_root = tmp_path / ".meguri" / "runs"
    for run_id, loop, status, finished_at, message in [
        ("run_20260613_100000_old", "old_loop", "fail", "2026-06-13T10:00:00+00:00", "old reason"),
        ("run_20260613_110000_mid", "mid_loop", "fail", "2026-06-13T11:00:00+00:00", "video_id is not valid"),
        ("run_20260613_120000_new", "new_loop", "pass", "2026-06-13T12:00:00+00:00", ""),
    ]:
        run_dir = runs_root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "index.html").write_text(f"<html>{loop}</html>", encoding="utf-8")
        (run_dir / "run.json").write_text(
            json.dumps({
                "run_id": run_id,
                "scenario_name": loop,
                "status": status,
                "mode": "execute",
                "finished_at": finished_at,
                "artifact_dir": str(run_dir),
                "metadata": {"loop_id": loop},
                "steps": [
                    {
                        "step_id": "run",
                        "status": status,
                        "checks": [{"id": "exit", "status": status, "message": message}] if message else [],
                    }
                ],
            }),
            encoding="utf-8",
        )

    explicit_path = runs_root / "run_20260613_120000_new" / "index.html"
    assert main(["report", "--runs", "run_20260613_110000_mid", str(explicit_path), "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)

    assert batch["source"] == "selected_runs"
    assert batch["selected_refs"] == ["run_20260613_110000_mid", str(explicit_path)]
    assert batch["planned_loops"] == ["mid_loop", "new_loop"]
    assert batch["status"] == "fail"
    assert batch["status_counts"] == {"fail": 1, "pass": 1}
    assert batch["failed_loops"] == ["mid_loop"]
    assert batch["retry_command"] == "meguri run mid_loop"
    assert "old_loop" not in json.dumps(batch)
    html = Path(batch["html_report_path"]).read_text(encoding="utf-8")
    assert "mid_loop" in html
    assert "new_loop" in html
    assert "old_loop" not in html


def test_report_runs_rejects_recent_mix(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()

    assert main(["report", "--recent", "1", "--runs", "run_1"]) == 1
    assert "--recent and --runs cannot be combined" in capsys.readouterr().err


def test_report_recent_extracts_structured_run_metrics(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()
    run_dir = tmp_path / ".meguri" / "runs" / "run_20260613_120000_metrics"
    run_dir.mkdir(parents=True)
    (run_dir / "index.html").write_text("<html>metrics</html>", encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps({
            "run_id": run_dir.name,
            "scenario_name": "metrics_loop",
            "status": "fail",
            "finished_at": "2026-06-13T12:00:00+00:00",
            "artifact_dir": str(run_dir),
            "metadata": {"loop_id": "metrics_loop"},
            "steps": [
                {
                    "step_id": "run",
                    "status": "fail",
                    "stdout": json.dumps({
                        "turn_count": 7,
                        "submitted": True,
                        "closed_status_verified": True,
                        "submit_results": [
                            {"ok": True, "id": "adset_1"},
                            {"ok": False, "error": "video_id is not valid"},
                        ],
                    }),
                    "checks": [],
                }
            ],
        }),
        encoding="utf-8",
    )

    assert main(["report", "--recent", "1"]) == 0
    html_path = Path(capsys.readouterr().out.strip())
    batch = json.loads(html_path.with_name("batch.json").read_text(encoding="utf-8"))

    assert batch["runs"][0]["metrics"] == {
        "closed_status_verified": True,
        "submit_failed_count": 1,
        "submit_success_count": 1,
        "submitted": True,
        "turn_count": 7,
    }
    html = html_path.read_text(encoding="utf-8")
    assert "turns=7" in html
    assert "submit=1/2" in html
    assert "closed=true" in html


def test_report_recent_json_prints_clean_batch_record(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()
    run_dir = tmp_path / ".meguri" / "runs" / "run_20260613_120000_json"
    run_dir.mkdir(parents=True)
    (run_dir / "index.html").write_text("<html>json</html>", encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps({
            "run_id": run_dir.name,
            "scenario_name": "json_loop",
            "status": "pass",
            "finished_at": "2026-06-13T12:00:00+00:00",
            "artifact_dir": str(run_dir),
            "metadata": {"loop_id": "json_loop"},
            "steps": [],
        }),
        encoding="utf-8",
    )

    assert main(["report", "--recent", "1", "--json"]) == 0
    record = json.loads(capsys.readouterr().out)

    assert record["source"] == "recent_runs"
    assert record["status"] == "pass"
    assert record["planned_loops"] == ["json_loop"]
    assert record["runs"][0]["run_id"] == "run_20260613_120000_json"
    assert Path(record["html_report_path"]).is_file()


def test_report_run_json_prints_single_run_summary(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()
    run_dir = tmp_path / ".meguri" / "runs" / "run_20260613_120000_single"
    run_dir.mkdir(parents=True)
    (run_dir / "index.html").write_text("<html>single</html>", encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps({
            "run_id": run_dir.name,
            "scenario_name": "single_loop",
            "status": "fail",
            "mode": "execute",
            "finished_at": "2026-06-13T12:00:00+00:00",
            "artifact_dir": str(run_dir),
            "metadata": {"loop_id": "single_loop"},
            "steps": [
                {
                    "step_id": "run",
                    "status": "fail",
                    "stdout": json.dumps({
                        "turn_count": 7,
                        "submitted": True,
                        "closed_status_verified": True,
                        "submit_results": [{"ok": False, "error": "archived campaign"}],
                    }),
                    "checks": [],
                }
            ],
        }),
        encoding="utf-8",
    )

    assert main(["report", "run_20260613_120000_single", "--json"]) == 0
    record = json.loads(capsys.readouterr().out)

    assert record["kind"] == "run"
    assert record["loop"] == "single_loop"
    assert record["run_id"] == "run_20260613_120000_single"
    assert record["status"] == "fail"
    assert record["mode"] == "execute"
    assert record["failure_reasons"] == ["archived campaign"]
    assert record["metrics"] == {
        "closed_status_verified": True,
        "submit_failed_count": 1,
        "submit_success_count": 0,
        "submitted": True,
        "turn_count": 7,
    }
    assert record["html_report_path"] == str(run_dir / "index.html")


def test_report_last_json_selects_newest_single_run(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    capsys.readouterr()
    for run_id, loop, finished_at in [
        ("run_20260613_100000_old", "old_loop", "2026-06-13T10:00:00+00:00"),
        ("run_20260613_120000_new", "new_loop", "2026-06-13T12:00:00+00:00"),
    ]:
        run_dir = tmp_path / ".meguri" / "runs" / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "index.html").write_text(f"<html>{loop}</html>", encoding="utf-8")
        (run_dir / "run.json").write_text(
            json.dumps({
                "run_id": run_id,
                "scenario_name": loop,
                "status": "pass",
                "finished_at": finished_at,
                "artifact_dir": str(run_dir),
                "metadata": {"loop_id": loop},
                "steps": [],
            }),
            encoding="utf-8",
        )

    assert main(["report", "--last", "--json"]) == 0
    record = json.loads(capsys.readouterr().out)

    assert record["kind"] == "run"
    assert record["loop"] == "new_loop"
    assert record["run_id"] == "run_20260613_120000_new"


def test_validate_accepts_generated_pack_and_rejects_unknown_adapter(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert main(["init", "--install-skills"]) == 0
    capsys.readouterr()

    assert main(["validate"]) == 0
    assert "ok" in capsys.readouterr().out
    assert (tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml").is_file()

    scenario_path = tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml"
    raw = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    raw["adapter"] = "missing_adapter"
    scenario_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    assert main(["validate"]) == 1
    assert "unknown adapter" in capsys.readouterr().out
