from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest
import yaml

from meguri.cli.main import main


@pytest.fixture(autouse=True)
def _isolate_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


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


def _assert_argparse_rejects(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(argv)
    assert excinfo.value.code == 2


def test_init_creates_project_pack_and_skills(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    assert main(["init", "--offline"]) == 0

    assert (tmp_path / ".meguri" / "project.yaml").is_file()
    assert (tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml").is_file()
    assert (tmp_path / ".meguri" / "scenarios" / "smoke.yaml").is_file()
    assert (tmp_path / ".meguri" / "README.md").is_file()
    assert (tmp_path / ".meguri" / "generated" / "inspect.md").is_file()
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
    generated_readme = (tmp_path / ".meguri" / "README.md").read_text(encoding="utf-8")
    generated_texts = {
        "codex_skill": codex_skill,
        "claude_skill": claude_skill,
        "claude_command": claude_command,
        "codex_prompt": codex_prompt,
        "generated_readme": generated_readme,
    }
    for key, text in generated_texts.items():
        assert "/meguri" in text, key
        assert "meguri init" in text, key
        assert "meguri run" in text, key
        assert "meguri report" in text, key
    for text in (codex_skill, claude_skill, codex_prompt):
        assert "meguri run <loop>" in text
        assert "meguri run <loop1> <loop2>" in text
        assert "meguri run all" in text
        assert "meguri report [run_or_batch_id]" in text
        assert ".meguri/loops/<loop_id>/_loop.yaml" in text
        assert "MEGURI_EVIDENCE_DIR" in text
        assert "--allow-execute" in text
        assert "crash-safe structured evidence" in text
        assert "Never treat LLM self-evaluation as passing evidence" in text
    for text in (codex_skill, claude_skill):
        assert "description: Use when the user wants" in text
        assert "Public CLI surface" in text
    assert "argument-hint: init|run|report [args]" in codex_prompt
    assert "argument-hint: init|run|report [args]" in claude_skill
    assert "Meguri verification loop workflow" in claude_command
    assert "argument-hint: init|run|report [args]" in claude_command
    assert "MEGURI_EVIDENCE_DIR" in claude_command
    assert "crash-safe structured evidence" in claude_command
    removed_strings = (
        "meguri add",
        "meguri loops",
        "meguri delete",
        "meguri validate",
        "meguri upgrade",
        "meguri report --recent",
        "meguri report --runs",
        "meguri report --loops",
        "meguri report --running",
        "meguri report --refresh",
        "meguri report --last",
        "meguri run --all",
        "meguri run --exclude",
        "meguri run --include-system",
    )
    for key, text in {
        "codex_skill": codex_skill,
        "claude_skill": claude_skill,
        "claude_command": claude_command,
        "codex_prompt": codex_prompt,
        "generated_readme": generated_readme,
    }.items():
        for removed in removed_strings:
            assert removed not in text, (key, removed)


def test_init_refreshes_skills_before_writing_pack(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    calls: list[tuple[Path, bool]] = []

    def fake_refresh(project_root: Path, *, offline: bool) -> list[Path]:
        calls.append((project_root, offline))
        path = project_root / ".agents" / "skills" / "meguri" / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("remote /meguri meguri init meguri run meguri report\n", encoding="utf-8")
        return [path]

    monkeypatch.setattr("meguri.cli.init.write_skills", fake_refresh)

    assert main(["init"]) == 0

    assert calls == [(tmp_path, False)]
    assert (tmp_path / ".meguri" / "project.yaml").is_file()
    assert "remote /meguri" in (tmp_path / ".agents" / "skills" / "meguri" / "SKILL.md").read_text(encoding="utf-8")


def test_init_refresh_failure_stops_before_pack_writes(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    def failing_refresh(project_root: Path, *, offline: bool) -> list[Path]:
        raise RuntimeError("network down")

    monkeypatch.setattr("meguri.cli.init.write_skills", failing_refresh)

    assert main(["init"]) == 1
    captured = capsys.readouterr()

    assert "Meguri skill refresh failed" in captured.err
    assert "network down" in captured.err
    assert not (tmp_path / ".meguri").exists()


def test_init_offline_uses_bundled_templates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    calls: list[bool] = []

    def fake_refresh(project_root: Path, *, offline: bool) -> list[Path]:
        calls.append(offline)
        path = project_root / ".agents" / "skills" / "meguri" / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("offline /meguri meguri init meguri run meguri report\n", encoding="utf-8")
        return [path]

    monkeypatch.setattr("meguri.cli.init.write_skills", fake_refresh)

    assert main(["init", "--offline"]) == 0

    assert calls == [True]


def test_help_exposes_only_init_run_and_report(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0

    output = capsys.readouterr().out

    assert "{init,run,report}" in output
    for command in ("init", "run", "report"):
        assert command in output
    for removed in ("inspect", "add", "loops", "delete", "validate", "validate-scenario", "upgrade"):
        assert removed not in output


def test_removed_public_commands_are_rejected_by_argparse() -> None:
    for command in ("inspect", "add", "loops", "delete", "validate", "validate-scenario", "upgrade"):
        _assert_argparse_rejects([command])


def test_run_without_target_returns_usage_error(capsys) -> None:
    assert main(["run"]) == 2

    assert "provide a loop name or all" in capsys.readouterr().err


def test_removed_run_selection_flags_are_rejected_by_argparse() -> None:
    for argv in (
        ["run", "--all"],
        ["run", "all", "--exclude", "checkout"],
        ["run", "all", "--include-system"],
    ):
        _assert_argparse_rejects(argv)


def test_init_preserves_existing_files_without_force(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    project_yaml = tmp_path / ".meguri" / "project.yaml"
    project_yaml.parent.mkdir(parents=True)
    project_yaml.write_text("custom: true\n", encoding="utf-8")

    assert main(["init", "--offline"]) == 0

    assert project_yaml.read_text(encoding="utf-8") == "custom: true\n"


def test_init_preserves_existing_loops_and_project_prompts_but_refreshes_entrypoints(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    smoke_loop = tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml"
    user_prompt = tmp_path / ".meguri" / "prompts" / "inspect.md"
    codex_prompt = tmp_path / "home" / ".codex" / "prompts" / "meguri.md"
    smoke_loop.parent.mkdir(parents=True)
    user_prompt.parent.mkdir(parents=True)
    codex_prompt.parent.mkdir(parents=True)
    smoke_loop.write_text("custom loop\n", encoding="utf-8")
    user_prompt.write_text("custom project prompt\n", encoding="utf-8")
    codex_prompt.write_text("custom slash prompt\n", encoding="utf-8")

    assert main(["init", "--offline"]) == 0
    output = capsys.readouterr().out

    assert smoke_loop.read_text(encoding="utf-8") == "custom loop\n"
    assert user_prompt.read_text(encoding="utf-8") == "custom project prompt\n"
    codex_prompt_text = codex_prompt.read_text(encoding="utf-8")
    assert "custom slash prompt" not in codex_prompt_text
    assert "Use `/meguri` for this request in the current Codex session" in codex_prompt_text
    generated_prompt = tmp_path / ".meguri" / "generated" / "inspect.md"
    assert generated_prompt.is_file()
    assert ".meguri/project-inspect.json" in generated_prompt.read_text(encoding="utf-8")
    assert "You are the current Codex / Claude Code agent" in output


def test_run_alias_writes_project_local_html_report(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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
    assert main(["init", "--offline"]) == 0
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


def test_run_prints_live_report_path_before_final_output(tmp_path: Path, monkeypatch, capsys) -> None:
    from meguri.core.models import RunReport, utc_now

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    _write_loop(tmp_path, "long_running", [sys.executable, "-c", "print('done')"])

    def fake_run_scenario(scenario_path, **kwargs):
        on_snapshot = kwargs["on_snapshot"]
        assert on_snapshot is not None
        loop_id = scenario_path.parent.name
        run_dir = tmp_path / ".meguri" / "loops" / loop_id / "20260613_121314"
        run_dir.mkdir(parents=True)
        (run_dir / "index.html").write_text("<html>live</html>", encoding="utf-8")
        now = utc_now()
        on_snapshot(RunReport(
            run_id=run_dir.name,
            scenario_name=loop_id,
            status="running",
            started_at=now,
            finished_at="",
            project_path=str(tmp_path),
            artifact_dir=str(run_dir),
            steps=[],
            checks=[],
            html_report_path=str(run_dir / "index.html"),
            metadata={"loop_id": loop_id},
            updated_at=now,
            mode="dry_run",
        ))
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
            mode="dry_run",
        )

    monkeypatch.setattr("meguri.cli.main.run_scenario", fake_run_scenario)

    assert main(["run", "long_running"]) == 0
    output = capsys.readouterr().out

    assert "live_loop=long_running" in output
    assert "live_run_id=20260613_121314" in output
    assert "live_step=-" in output
    assert f"live_report={tmp_path / '.meguri' / 'loops' / 'long_running' / '20260613_121314' / 'index.html'}" in output
    assert output.index("live_report=") < output.index("\nrun_id=20260613_121314")


def test_run_prints_live_output_progress_for_same_running_step(tmp_path: Path, monkeypatch, capsys) -> None:
    from meguri.core.models import Artifact, RunReport, StepResult

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    _write_loop(tmp_path, "long_output", [sys.executable, "-c", "print('done')"])

    def fake_run_scenario(scenario_path, **kwargs):
        on_snapshot = kwargs["on_snapshot"]
        assert on_snapshot is not None
        loop_id = scenario_path.parent.name
        run_dir = tmp_path / ".meguri" / "loops" / loop_id / "20260613_121314"
        stdout_path = run_dir / "steps" / "agent" / "stdout.txt"
        stderr_path = run_dir / "steps" / "agent" / "stderr.txt"
        stdout_path.parent.mkdir(parents=True)
        stdout_path.write_text("partial output\n", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")
        (run_dir / "index.html").write_text("<html>live</html>", encoding="utf-8")
        running_step = StepResult(
            step_id="agent",
            status="running",
            started_at="2026-06-13T12:13:14+00:00",
            finished_at="2026-06-13T12:13:14+00:00",
            stdout="partial output\n",
            data={"live_stdout_chars": len("partial output\n"), "live_stderr_chars": 0},
            artifacts=[
                Artifact(
                    name="steps/agent/stdout.txt",
                    path=str(stdout_path),
                    kind="stdout",
                    metadata={"live": True},
                ),
                Artifact(
                    name="steps/agent/stderr.txt",
                    path=str(stderr_path),
                    kind="stderr",
                    metadata={"live": True},
                ),
            ],
        )
        base = {
            "run_id": run_dir.name,
            "scenario_name": loop_id,
            "status": "running",
            "started_at": "2026-06-13T12:13:14+00:00",
            "finished_at": "",
            "project_path": str(tmp_path),
            "artifact_dir": str(run_dir),
            "steps": [running_step],
            "checks": [],
            "html_report_path": str(run_dir / "index.html"),
            "metadata": {"loop_id": loop_id},
            "mode": "dry_run",
        }
        on_snapshot(RunReport(updated_at="2026-06-13T12:13:14+00:00", **base))
        running_step.stdout += "more output\n"
        running_step.data["live_stdout_chars"] = len(running_step.stdout)
        stdout_path.write_text(running_step.stdout, encoding="utf-8")
        on_snapshot(RunReport(updated_at="2026-06-13T12:13:15+00:00", **base))
        return RunReport(status="pass", finished_at="2026-06-13T12:13:16+00:00", updated_at="2026-06-13T12:13:16+00:00", **{k: v for k, v in base.items() if k not in {"status", "finished_at"}})

    monkeypatch.setattr("meguri.cli.main.run_scenario", fake_run_scenario)

    assert main(["run", "long_output"]) == 0
    output = capsys.readouterr().out
    expected_stdout_chars = len("partial output\nmore output\n")

    assert output.count("live_step=agent") == 2
    assert "live_updated_at=2026-06-13T12:13:15+00:00" in output
    assert "live_stdout=steps/agent/stdout.txt" in output
    assert f"live_stdout_path={tmp_path / '.meguri' / 'loops' / 'long_output' / '20260613_121314' / 'steps' / 'agent' / 'stdout.txt'}" in output
    assert f"live_stdout_chars={expected_stdout_chars}" in output


def test_run_execute_loop_requires_explicit_approval(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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


def test_batch_retry_loops_do_not_emit_retry_command(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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
    assert "retry_command" not in batch
    html = Path(batch["html_report_path"]).read_text(encoding="utf-8")
    assert "<th>Mode</th>" in html
    assert "<td>execute</td>" in html
    assert "Retry Failed or Unfinished Loops" not in html
    assert "meguri run first_execute_fail second_execute_fail --allow-execute" not in html


def test_run_multiple_loops_continues_in_order_after_failure(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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
    assert "retry_command" not in batch_record
    html = (batch_dir / "index.html").read_text(encoding="utf-8")
    assert "first_fail" in html
    assert "Status Summary" in html
    assert "fail: 2" in html
    assert "pass: 1" in html
    assert "video_id is not valid" in html
    assert "2 loops" in html
    assert "Retry Failed or Unfinished Loops" not in html
    assert "meguri run first_fail third_fail" not in html
    assert "second_pass" in html
    assert marker_path.read_text(encoding="utf-8") == "ran"
    assert Path(batch["runs"][0]["html_report_path"]).is_file()
    assert Path(batch["runs"][1]["html_report_path"]).is_file()

    assert main(["report"]) == 0
    assert capsys.readouterr().out.strip() == batch["html_report_path"]


def test_run_multiple_loops_records_created_resources_in_batch(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    _write_loop(
        tmp_path,
        "first_partial_write",
        [
            sys.executable,
            "-c",
            (
                "import json, sys; print(json.dumps({"
                "'submitted': True, "
                "'submit_results': [{"
                "'ok': True, "
                "'resource_type': 'campaign', "
                "'campaign_id': '120250081240970683'"
                "}, {"
                "'ok': False, "
                "'error': 'location conflict'"
                "}]})); sys.exit(1)"
            ),
        ],
    )
    _write_loop(tmp_path, "second_pass", [sys.executable, "-c", "print('ok')"])

    assert main(["run", "first_partial_write", "second_pass", "--json"]) == 1
    batch = json.loads(capsys.readouterr().out)

    assert batch["created_resource_count"] == 1
    assert batch["created_resources"] == [
        {
            "loop": "first_partial_write",
            "run_id": batch["runs"][0]["run_id"],
            "type": "campaign",
            "id": "120250081240970683",
            "source": "submit_results",
        }
    ]
    assert batch["runs"][0]["created_resource_count"] == 1
    html = Path(batch["html_report_path"]).read_text(encoding="utf-8")
    assert "Created Resources" in html
    assert "120250081240970683" in html


def test_run_multiple_loops_records_attention_flags_in_batch(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    _write_loop(
        tmp_path,
        "preview_only",
        [
            sys.executable,
            "-c",
            (
                "import json, sys; print(json.dumps({"
                "'final_submit': True, "
                "'submitted': False, "
                "'turn_count': 1, "
                "'expected_turn_count': 7, "
                "'crash_tracebacks': ['Traceback: AgentResponseParseError']"
                "})); sys.exit(1)"
            ),
        ],
    )
    _write_loop(tmp_path, "second_pass", [sys.executable, "-c", "print('ok')"])

    assert main(["run", "preview_only", "second_pass", "--json"]) == 1
    batch = json.loads(capsys.readouterr().out)

    assert batch["attention_count"] == 3
    assert [flag["code"] for flag in batch["attention_flags"]] == [
        "short_run",
        "not_submitted",
        "crash_traceback",
    ]
    assert batch["runs"][0]["attention_count"] == 3
    html = Path(batch["html_report_path"]).read_text(encoding="utf-8")
    assert "Attention Flags" in html
    assert "preview_only" in html
    assert "short_run" in html


def test_run_multiple_loops_updates_batch_record_after_each_loop(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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


def test_run_batch_refreshes_record_when_current_loop_step_advances(tmp_path: Path, monkeypatch, capsys) -> None:
    from meguri.core.models import RunReport, StepResult, utc_now

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    _write_loop(tmp_path, "first_running", [sys.executable, "-c", "print('first')"])
    _write_loop(tmp_path, "second_later", [sys.executable, "-c", "print('second')"])
    observed: dict[str, object] = {}

    def fake_run_scenario(scenario_path, **kwargs):
        loop_id = scenario_path.parent.name
        on_snapshot = kwargs["on_snapshot"]
        run_dir = tmp_path / ".meguri" / "loops" / loop_id / "20260613_121314"
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "index.html").write_text(f"<html>{loop_id}</html>", encoding="utf-8")
        now = utc_now()
        running_report = RunReport(
            run_id=run_dir.name,
            scenario_name=loop_id,
            status="running",
            started_at=now,
            finished_at="",
            project_path=str(tmp_path),
            artifact_dir=str(run_dir),
            steps=[
                StepResult(
                    step_id="open_checkout",
                    status="running",
                    started_at=now,
                    finished_at=now,
                )
            ],
            checks=[],
            html_report_path=str(run_dir / "index.html"),
            metadata={"loop_id": loop_id},
            updated_at=now,
            mode="dry_run",
        )
        if loop_id == "first_running":
            on_snapshot(running_report)
            [batch_dir] = list((tmp_path / ".meguri" / "batches").iterdir())
            observed["record"] = json.loads((batch_dir / "batch.json").read_text(encoding="utf-8"))
            observed["html"] = (batch_dir / "index.html").read_text(encoding="utf-8")
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
            mode="dry_run",
        )

    monkeypatch.setattr("meguri.cli.main.run_scenario", fake_run_scenario)

    assert main(["run", "first_running", "second_later", "--json"]) == 0
    record = observed["record"]

    assert record["status"] == "running"
    assert record["current_loop"] == "first_running"
    assert record["current_run"]["loop"] == "first_running"
    assert record["current_run"]["run_id"] == "20260613_121314"
    assert record["current_run"]["status"] == "running"
    assert record["current_run"]["current_step"] == "open_checkout"
    assert record["current_run"]["html_report_path"].endswith("first_running/20260613_121314/index.html")
    assert "Current Run" in observed["html"]
    assert "open_checkout" in observed["html"]


def test_run_multiple_loops_blocks_batch_when_interrupted(tmp_path: Path, monkeypatch, capsys) -> None:
    from meguri.core.models import RunReport, utc_now

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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


def test_run_all_selects_user_loops_not_system_smoke_and_creates_batch_report(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    ran_path = tmp_path / "ran.txt"
    _write_loop(
        tmp_path,
        "first_todo",
        [sys.executable, "-c", f"from pathlib import Path; Path(r'{ran_path}').write_text('first', encoding='utf-8')"],
    )
    _write_loop(
        tmp_path,
        "second_todo",
        [sys.executable, "-c", f"from pathlib import Path; Path(r'{ran_path}').write_text(Path(r'{ran_path}').read_text(encoding='utf-8') + ',third', encoding='utf-8')"],
    )

    assert main(["run", "all", "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)

    assert batch["planned_loops"] == ["first_todo", "second_todo"]
    assert [run["loop"] for run in batch["runs"]] == ["first_todo", "second_todo"]
    assert "smoke" not in batch["planned_loops"]
    assert batch["batch_dir"]
    assert Path(batch["batch_dir"]).parent == tmp_path / ".meguri" / "batches"
    assert Path(batch["html_report_path"]).is_file()
    assert Path(batch["batch_dir"]).joinpath("batch.json").is_file()
    assert ran_path.read_text(encoding="utf-8") == "first,third"


def test_report_defaults_to_latest_existing_report(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    _write_loop(tmp_path, "user_check", [sys.executable, "-c", "print('user ok')"])

    assert main(["run", "user_check"]) == 0
    run_output = capsys.readouterr().out.splitlines()
    html_report = next(line.removeprefix("html_report=") for line in run_output if line.startswith("html_report="))

    assert main(["report"]) == 0
    output = capsys.readouterr().out.strip()

    assert output == html_report
    assert Path(output).is_file()


def test_report_rejects_manual_batch_and_refresh_flags(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0

    for argv in [
        ["report", "--recent", "2"],
        ["report", "--runs", "a", "b"],
        ["report", "--loops", "login"],
        ["report", "--running"],
        ["report", "--refresh"],
        ["report", "--last"],
    ]:
        _assert_argparse_rejects(argv)


def test_report_selects_newest_html_report(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    assert main(["run", "smoke"]) == 0
    capsys.readouterr()

    assert main(["report"]) == 0
    output = capsys.readouterr().out.strip()

    assert output.endswith("index.html")
    assert Path(output).is_file()


def test_report_prefers_run_json_time_over_directory_mtime(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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

    assert main(["report"]) == 0
    output = capsys.readouterr().out.strip()

    assert output.endswith("20260613_110000/index.html")


def test_report_uses_batch_updated_at_for_latest_batch(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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

    assert main(["report"]) == 0
    output = capsys.readouterr().out.strip()

    assert output.endswith("batches/20260613_100000_000000/index.html")


def test_report_resolves_existing_batch_from_multi_loop_run(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    _write_loop(tmp_path, "first_todo", [sys.executable, "-c", "print('first')"])
    _write_loop(tmp_path, "second_todo", [sys.executable, "-c", "print('second')"])

    assert main(["run", "first_todo", "second_todo", "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)

    assert main(["report", batch["batch_id"]]) == 0
    output = capsys.readouterr().out.strip()

    assert output == batch["html_report_path"]
    assert Path(output).is_file()


def test_report_run_json_prints_single_run_summary(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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
            "project_path": str(tmp_path),
            "artifact_dir": str(run_dir),
            "metadata": {"loop_id": "single_loop"},
            "evidence_warnings": ["schema_warning: rendered as note"],
            "replay": {
                "source_run_id": run_dir.name,
                "loop_id": "single_loop",
                "inputs": [
                    {"source": "evidence", "path": "evidence/session/evidence.json"},
                    {"source": "config", "path": "ignored.yaml"},
                ],
                "replay": {"status": "full", "missing": []},
            },
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
    assert record["evidence_files"] == ["evidence/session/evidence.json"]
    assert record["evidence_count"] == 1
    assert record["evidence_warnings"] == ["schema_warning: rendered as note"]
    assert record["replay_status"] == "full"
    assert "replay_command" not in record
    assert record["metrics"] == {
        "closed_status_verified": True,
        "submit_failed_count": 1,
        "submit_success_count": 0,
        "submitted": True,
        "turn_count": 7,
    }
    assert record["html_report_path"] == str(run_dir / "index.html")


def test_report_json_selects_newest_single_run(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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

    assert main(["report", "--json"]) == 0
    record = json.loads(capsys.readouterr().out)

    assert record["kind"] == "run"
    assert record["loop"] == "new_loop"
    assert record["run_id"] == "run_20260613_120000_new"


def test_run_validates_scenario_before_execution(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()

    assert (tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml").is_file()

    scenario_path = tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml"
    raw = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    raw["adapter"] = "missing_adapter"
    scenario_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    assert main(["run", "smoke"]) == 1
    captured = capsys.readouterr()

    assert "unknown adapter" in captured.err
    assert not list((tmp_path / ".meguri" / "loops" / "smoke").glob("20*/run.json"))
