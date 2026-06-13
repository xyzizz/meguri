from __future__ import annotations

import json
import os
import sys
from pathlib import Path

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
    assert ".meguri/batches/<batch_id>/batch.json" in codex_skill
    assert "argument-hint: inspect|add|loops|delete|run|validate|report [args]" in codex_prompt
    assert "Use this active Codex session" in codex_prompt
    assert "MEGURI_EVIDENCE_DIR" in codex_prompt
    assert "Meguri inspect workflow" in claude_skill
    assert "evidence crash-safe" in claude_skill
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
            f"from pathlib import Path; Path(r'{marker_path}').write_text('ran', encoding='utf-8'); print('second passed')",
        ],
    )

    assert main(["run", "first_fail", "second_pass", "--json"]) == 1
    output = capsys.readouterr().out
    batch = json.loads(output)

    assert batch["status"] == "fail"
    assert [run["loop"] for run in batch["runs"]] == ["first_fail", "second_pass"]
    assert [run["status"] for run in batch["runs"]] == ["fail", "pass"]
    assert batch["runs"][0]["summary"] == "video_id is not valid; archived campaign"
    assert batch["runs"][0]["failure_reasons"] == ["video_id is not valid", "archived campaign"]
    batch_dir = Path(batch["batch_dir"])
    assert batch_dir.parent == tmp_path / ".meguri" / "batches"
    assert batch["html_report_path"] == str(batch_dir / "index.html")
    assert (batch_dir / "batch.json").is_file()
    assert (batch_dir / "index.html").is_file()
    batch_record = json.loads((batch_dir / "batch.json").read_text(encoding="utf-8"))
    assert batch_record["status"] == "fail"
    assert [run["loop"] for run in batch_record["runs"]] == ["first_fail", "second_pass"]
    html = (batch_dir / "index.html").read_text(encoding="utf-8")
    assert "first_fail" in html
    assert "video_id is not valid" in html
    assert "second_pass" in html
    assert marker_path.read_text(encoding="utf-8") == "ran"
    assert Path(batch["runs"][0]["html_report_path"]).is_file()
    assert Path(batch["runs"][1]["html_report_path"]).is_file()

    assert main(["report", "--last"]) == 0
    assert capsys.readouterr().out.strip() == batch["html_report_path"]


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
