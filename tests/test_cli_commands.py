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
    assert "Meguri init workflow" in codex_skill
    assert "loop design" in codex_skill
    assert "evidence crash-safe" in codex_skill
    assert ".meguri/loops/<loop_id>/<run_id>/timeline.ndjson" in codex_skill
    assert "`run.json`, `report.md`, `index.html`" in codex_skill
    assert "meguri run <loop1> <loop2>" in codex_skill
    assert "live_report=..." in codex_skill
    assert "live_stdout_path=..." in codex_skill
    assert "live character counts" in codex_skill
    assert "silent-step heartbeats" in codex_skill
    assert "meguri run --all --exclude <loop>" in codex_skill
    assert "meguri run <loop> --allow-execute" in codex_skill
    assert "meguri report --running --json" in codex_skill
    assert "meguri upgrade --skills --refresh-index" in codex_skill
    assert ".meguri/batches/<batch_id>/batch.json" in codex_skill
    assert "live progress surface" in codex_skill
    assert "Shell stdout/stderr output also refreshes" in codex_skill
    assert "meguri report <run_id> --json" in codex_skill
    assert "meguri report <run_id> --refresh" in codex_skill
    assert "meguri report --last --json" in codex_skill
    assert "`evidence_files`" in codex_skill
    assert "`replay_command`" not in codex_skill
    assert "meguri report --recent <N>" in codex_skill
    assert "meguri report --recent <N> --json" in codex_skill
    assert "meguri report --runs <run_id-or-path> ..." in codex_skill
    assert "meguri report --loops <loop> ..." in codex_skill
    assert "`status_counts`" in codex_skill
    assert "`failed_loops`" in codex_skill
    assert "`retry_loops`" in codex_skill
    assert "`attention_flags`" in codex_skill
    assert "`created_resources`" in codex_skill
    assert "`failed_items`" in codex_skill
    assert "`validation_issues`" in codex_skill
    assert "`repair_hints`" in codex_skill
    assert "per-loop `mode`" in codex_skill
    assert "per-loop `metrics`" in codex_skill
    assert "Replay command" not in codex_skill
    assert "argument-hint: init|add|loops|delete|run|validate|report|upgrade [args]" in codex_prompt
    assert "Use this active Codex session" in codex_prompt
    assert "meguri upgrade --skills --refresh-index" in codex_prompt
    assert "MEGURI_EVIDENCE_DIR" in codex_prompt
    assert "--allow-execute" in codex_prompt
    assert "Meguri init workflow" in claude_skill
    assert "evidence crash-safe" in claude_skill
    assert "meguri run --all --exclude <loop>" in claude_skill
    assert "live_report=..." in claude_skill
    assert "live_stdout_path=..." in claude_skill
    assert "live character counts" in claude_skill
    assert "silent-step heartbeats" in claude_skill
    assert "meguri run <loop> --allow-execute" in claude_skill
    assert "meguri report --running --json" in claude_skill
    assert "meguri upgrade --skills --refresh-index" in claude_skill
    assert "live progress surface" in claude_skill
    assert "Shell stdout/stderr output also refreshes" in claude_skill
    assert "meguri report <run_id> --json" in claude_skill
    assert "meguri report <run_id> --refresh" in claude_skill
    assert "meguri report --last --json" in claude_skill
    assert "`evidence_files`" in claude_skill
    assert "`replay_command`" not in claude_skill
    assert "meguri report --recent <N>" in claude_skill
    assert "meguri report --recent <N> --json" in claude_skill
    assert "meguri report --runs <run_id-or-path> ..." in claude_skill
    assert "meguri report --loops <loop> ..." in claude_skill
    assert "`status_counts`" in claude_skill
    assert "`failed_loops`" in claude_skill
    assert "`retry_loops`" in claude_skill
    assert "`attention_flags`" in claude_skill
    assert "`created_resources`" in claude_skill
    assert "`failed_items`" in claude_skill
    assert "`validation_issues`" in claude_skill
    assert "`repair_hints`" in claude_skill
    assert "per-loop `mode`" in claude_skill
    assert "per-loop `metrics`" in claude_skill
    assert "Replay command" not in claude_skill
    assert "argument-hint: init|add|loops|delete|run|validate|report|upgrade [args]" in claude_skill
    assert "Meguri verification loop workflow" in claude_command
    assert "MEGURI_EVIDENCE_DIR" in claude_command
    assert "upgrade" in claude_command


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


def test_upgrade_requires_an_action(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()

    assert main(["upgrade"]) == 2

    assert "choose --skills and/or --refresh-index" in capsys.readouterr().err


def test_upgrade_skills_overwrites_project_entrypoints(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()

    skill_paths = [
        tmp_path / ".agents" / "skills" / "meguri" / "SKILL.md",
        tmp_path / ".claude" / "skills" / "meguri" / "SKILL.md",
        tmp_path / ".claude" / "commands" / "meguri.md",
        tmp_path / "home" / ".codex" / "prompts" / "meguri.md",
    ]
    for path in skill_paths:
        path.write_text("stale entrypoint\n", encoding="utf-8")

    assert main(["upgrade", "--skills"]) == 0
    output = capsys.readouterr().out

    for path in skill_paths:
        text = path.read_text(encoding="utf-8")
        assert "stale entrypoint" not in text
    assert "Meguri init workflow" in skill_paths[0].read_text(encoding="utf-8")
    assert "Meguri init workflow" in skill_paths[1].read_text(encoding="utf-8")
    assert "Meguri verification loop workflow" in skill_paths[2].read_text(encoding="utf-8")
    assert "Use this active Codex session" in skill_paths[3].read_text(encoding="utf-8")
    assert "updated .agents/skills/meguri/SKILL.md" in output
    assert "updated .claude/skills/meguri/SKILL.md" in output
    assert "updated .claude/commands/meguri.md" in output


def test_upgrade_refresh_index_regenerates_project_and_loop_indexes(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()

    loop_dir = tmp_path / ".meguri" / "loops" / "checkout"
    run_dir = loop_dir / "20260615_102001"
    run_dir.mkdir(parents=True)
    (run_dir / "index.html").write_text("<html>detail</html>", encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_dir.name,
                "scenario_name": "checkout",
                "status": "fail",
                "started_at": "2026-06-15T10:20:01+00:00",
                "finished_at": "2026-06-15T10:20:02+00:00",
                "updated_at": "2026-06-15T10:20:02+00:00",
                "mode": "dry_run",
                "summary": "checkout assertion failed",
                "metadata": {"loop_id": "checkout"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / ".meguri" / "index.html").write_text("stale project index", encoding="utf-8")
    (loop_dir / "index.html").write_text("stale loop index", encoding="utf-8")

    assert main(["upgrade", "--refresh-index"]) == 0
    output = capsys.readouterr().out

    project_html = (tmp_path / ".meguri" / "index.html").read_text(encoding="utf-8")
    loop_html = (loop_dir / "index.html").read_text(encoding="utf-8")
    assert "Meguri Control Room" in project_html
    assert "checkout" in project_html
    assert "loops/checkout/index.html" in project_html
    assert "Loop Detail" in loop_html
    assert "20260615_102001/index.html" in loop_html
    assert "checkout assertion failed" in loop_html
    assert "stale project index" not in project_html
    assert "stale loop index" not in loop_html
    assert "updated .meguri/index.html" in output
    assert "updated .meguri/loops/checkout/index.html" in output


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
    assert "Use this active Codex session" in codex_prompt_text
    generated_prompt = tmp_path / ".meguri" / "generated" / "inspect.md"
    assert generated_prompt.is_file()
    assert ".meguri/project-inspect.json" in generated_prompt.read_text(encoding="utf-8")
    assert "You are the current Codex / Claude Code agent" in output


def test_add_asks_for_clarification_without_required_information(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()

    assert main(["add", "login"]) == 2
    output = capsys.readouterr().out

    assert "Please clarify" in output
    assert "Provide --command" in output
    assert not (tmp_path / ".meguri" / "scenarios" / "login.yaml").exists()


def test_inspect_compatibility_alias_runs_init_workflow(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr("meguri.cli.init.write_skills", lambda project_root, *, offline: [])

    assert main(["inspect"]) == 0
    output = capsys.readouterr().out

    prompt_path = tmp_path / ".meguri" / "generated" / "inspect.md"
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


def test_add_writes_valid_scenario_when_required_fields_are_supplied(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0

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
    assert main(["init", "--offline"]) == 0
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
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()

    assert main(["delete", "smoke"]) == 1
    output = capsys.readouterr().out
    assert "Refusing to delete system loop" in output
    assert (tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml").exists()


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

    assert main(["report", "--last"]) == 0
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


def test_run_all_user_loops_excludes_named_loop_and_system_smoke(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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
    assert main(["init", "--offline"]) == 0
    assert main(["run", "smoke"]) == 0
    capsys.readouterr()

    assert main(["report", "--last"]) == 0
    output = capsys.readouterr().out.strip()

    assert output.endswith("index.html")
    assert Path(output).is_file()


def test_report_last_prefers_run_json_time_over_directory_mtime(tmp_path: Path, monkeypatch, capsys) -> None:
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

    assert main(["report", "--last"]) == 0
    output = capsys.readouterr().out.strip()

    assert output.endswith("20260613_110000/index.html")


def test_report_last_uses_batch_updated_at_for_running_batch(tmp_path: Path, monkeypatch, capsys) -> None:
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

    assert main(["report", "--last"]) == 0
    output = capsys.readouterr().out.strip()

    assert output.endswith("batches/20260613_100000_000000/index.html")


def test_report_running_json_lists_active_runs_and_batches(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()

    running_loop = tmp_path / ".meguri" / "loops" / "checkout" / "20260613_110000"
    finished_run = tmp_path / ".meguri" / "runs" / "run_20260613_100000_finished"
    running_batch = tmp_path / ".meguri" / "batches" / "20260613_120000_000000"
    running_loop.mkdir(parents=True)
    finished_run.mkdir(parents=True)
    running_batch.mkdir(parents=True)
    (running_loop / "index.html").write_text("<html>loop</html>", encoding="utf-8")
    (running_loop / "run.json").write_text(
        json.dumps({
            "run_id": running_loop.name,
            "scenario_name": "checkout",
            "status": "running",
            "updated_at": "2026-06-13T11:01:00+00:00",
            "artifact_dir": str(running_loop),
            "metadata": {"loop_id": "checkout"},
            "steps": [{"step_id": "open_cart", "status": "running"}],
        }),
        encoding="utf-8",
    )
    (finished_run / "index.html").write_text("<html>done</html>", encoding="utf-8")
    (finished_run / "run.json").write_text(
        json.dumps({
            "run_id": finished_run.name,
            "scenario_name": "finished",
            "status": "pass",
            "finished_at": "2026-06-13T10:00:00+00:00",
            "steps": [],
        }),
        encoding="utf-8",
    )
    (running_batch / "index.html").write_text("<html>batch</html>", encoding="utf-8")
    (running_batch / "batch.json").write_text(
        json.dumps({
            "batch_id": running_batch.name,
            "status": "running",
            "updated_at": "2026-06-13T12:00:00+00:00",
            "current_loop": "checkout",
            "runs": [{"loop": "smoke", "status": "pass"}],
            "remaining_loops": ["checkout"],
        }),
        encoding="utf-8",
    )

    assert main(["report", "--running", "--json"]) == 0
    record = json.loads(capsys.readouterr().out)

    assert record["kind"] == "running_reports"
    assert record["count"] == 2
    assert record["runs"][0]["kind"] == "run"
    assert record["runs"][0]["loop"] == "checkout"
    assert record["runs"][0]["run_id"] == "20260613_110000"
    assert record["runs"][0]["current_step"] == "open_cart"
    assert record["batches"][0]["kind"] == "batch"
    assert record["batches"][0]["batch_id"] == "20260613_120000_000000"
    assert record["batches"][0]["current_loop"] == "checkout"
    assert str(finished_run) not in json.dumps(record)


def test_report_recent_creates_batch_from_latest_standalone_runs(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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
    assert "retry_command" not in batch
    assert batch["failure_groups"] == [{
        "reason": "video_id is not valid",
        "count": 2,
        "loops": ["mid_loop", "new_loop"],
    }]
    html = html_path.read_text(encoding="utf-8")
    assert "meguri run mid_loop new_loop --allow-execute" not in html
    assert "old_loop" not in html


def test_report_recent_retries_running_standalone_runs(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    runs_root = tmp_path / ".meguri" / "runs"
    for run_id, loop, status, timestamp, message in [
        ("run_20260613_110000_fail", "failed_loop", "fail", "2026-06-13T11:00:00+00:00", "archived campaign"),
        ("run_20260613_120000_running", "running_loop", "running", "2026-06-13T12:00:00+00:00", ""),
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
                "started_at": "2026-06-13T10:59:00+00:00",
                "updated_at": timestamp,
                "finished_at": timestamp if status != "running" else "",
                "artifact_dir": str(run_dir),
                "metadata": {"loop_id": loop},
                "steps": [
                    {
                        "step_id": "run",
                        "status": status,
                        "checks": [{"id": "exit", "status": "fail", "message": message}] if message else [],
                    }
                ],
            }),
            encoding="utf-8",
        )

    assert main(["report", "--recent", "2", "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)

    assert batch["status"] == "fail"
    assert batch["status_counts"] == {"fail": 1, "running": 1}
    assert batch["failed_loops"] == ["failed_loop"]
    assert batch["retry_loops"] == ["failed_loop", "running_loop"]
    assert "retry_command" not in batch
    html = Path(batch["html_report_path"]).read_text(encoding="utf-8")
    assert "Retry Failed or Unfinished Loops" not in html


def test_report_runs_creates_batch_from_explicit_run_refs(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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
    assert "retry_command" not in batch
    assert "old_loop" not in json.dumps(batch)
    html = Path(batch["html_report_path"]).read_text(encoding="utf-8")
    assert "mid_loop" in html
    assert "new_loop" in html
    assert "old_loop" not in html


def test_report_loops_groups_latest_run_for_each_named_loop(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    runs_root = tmp_path / ".meguri" / "runs"
    for run_id, loop, status, finished_at, message in [
        ("run_20260613_100000_loop_a_old", "loop_a", "fail", "2026-06-13T10:00:00+00:00", "old reason"),
        ("run_20260613_110000_loop_b", "loop_b", "pass", "2026-06-13T11:00:00+00:00", ""),
        ("run_20260613_120000_loop_a_new", "loop_a", "fail", "2026-06-13T12:00:00+00:00", "latest reason"),
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

    assert main(["report", "--loops", "loop_a", "loop_b", "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)

    assert batch["source"] == "latest_loops"
    assert batch["selected_loops"] == ["loop_a", "loop_b"]
    assert batch["planned_loops"] == ["loop_a", "loop_b"]
    assert [run["run_id"] for run in batch["runs"]] == [
        "run_20260613_120000_loop_a_new",
        "run_20260613_110000_loop_b",
    ]
    assert batch["status"] == "fail"
    assert batch["status_counts"] == {"fail": 1, "pass": 1}
    assert batch["failed_loops"] == ["loop_a"]
    assert "retry_command" not in batch
    assert "old reason" not in json.dumps(batch)
    html = Path(batch["html_report_path"]).read_text(encoding="utf-8")
    assert "loop_a" in html
    assert "loop_b" in html
    assert "old reason" not in html


def test_report_loops_uses_loop_directory_when_run_metadata_is_missing(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    run_dir = tmp_path / ".meguri" / "loops" / "checkout" / "20260613_120000"
    run_dir.mkdir(parents=True)
    (run_dir / "index.html").write_text("<html>checkout</html>", encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps({
            "run_id": run_dir.name,
            "status": "pass",
            "finished_at": "2026-06-13T12:00:00+00:00",
            "artifact_dir": str(run_dir),
            "steps": [],
        }),
        encoding="utf-8",
    )

    assert main(["report", "--loops", "checkout", "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)

    assert batch["source"] == "latest_loops"
    assert batch["planned_loops"] == ["checkout"]
    assert batch["runs"][0]["loop"] == "checkout"
    assert batch["runs"][0]["run_id"] == "20260613_120000"


def test_report_runs_rejects_recent_mix(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()

    assert main(["report", "--recent", "1", "--runs", "run_1"]) == 1
    assert "--recent cannot be combined with --runs or --loops" in capsys.readouterr().err

    assert main(["report", "--runs", "run_1", "--loops", "loop_a"]) == 1
    assert "--runs cannot be combined with run id or --loops" in capsys.readouterr().err


def test_report_recent_extracts_structured_run_metrics(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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


def test_report_recent_extracts_created_resources_for_partial_execute_writes(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    run_dir = tmp_path / ".meguri" / "runs" / "run_20260613_120000_side_effects"
    run_dir.mkdir(parents=True)
    (run_dir / "index.html").write_text("<html>side effects</html>", encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps({
            "run_id": run_dir.name,
            "scenario_name": "reference_campaign_new_campaign",
            "status": "fail",
            "mode": "execute",
            "finished_at": "2026-06-13T12:00:00+00:00",
            "artifact_dir": str(run_dir),
            "metadata": {"loop_id": "reference_campaign_new_campaign"},
            "steps": [
                {
                    "step_id": "run",
                    "status": "fail",
                    "stdout": json.dumps({
                        "submitted": True,
                        "submit_results": [
                            {
                                "ok": True,
                                "resource_type": "campaign",
                                "campaign_id": "120250081016770683",
                            },
                            {
                                "ok": False,
                                "resource_type": "adset",
                                "error": "location conflict",
                            },
                        ],
                    }),
                    "checks": [{"id": "submit", "status": "fail", "message": "location conflict"}],
                }
            ],
        }),
        encoding="utf-8",
    )

    assert main(["report", "--recent", "1", "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)

    assert batch["created_resource_count"] == 1
    assert batch["created_resources"] == [
        {
            "loop": "reference_campaign_new_campaign",
            "run_id": "run_20260613_120000_side_effects",
            "type": "campaign",
            "id": "120250081016770683",
            "source": "submit_results",
        }
    ]
    assert batch["runs"][0]["created_resource_count"] == 1
    assert batch["runs"][0]["created_resources"][0]["id"] == "120250081016770683"
    html = Path(batch["html_report_path"]).read_text(encoding="utf-8")
    assert "Created Resources" in html
    assert "120250081016770683" in html


def test_report_recent_extracts_nested_business_failure_reasons(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    run_dir = tmp_path / ".meguri" / "runs" / "run_20260613_120000_nested_failure"
    run_dir.mkdir(parents=True)
    (run_dir / "index.html").write_text("<html>failure</html>", encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps({
            "run_id": run_dir.name,
            "scenario_name": "reference_campaign_new_campaign",
            "status": "fail",
            "mode": "execute",
            "finished_at": "2026-06-13T12:00:00+00:00",
            "artifact_dir": str(run_dir),
            "metadata": {"loop_id": "reference_campaign_new_campaign"},
            "steps": [
                {
                    "step_id": "run",
                    "status": "fail",
                    "stdout": json.dumps({
                        "submitted": True,
                        "turns": [
                            {
                                "id": "submit",
                                "events": [
                                    {
                                        "tool_result": {
                                            "items": [
                                                {
                                                    "id": "120250081016770683",
                                                    "name": "copy_facebook_campaign_to_account",
                                                    "status": "success",
                                                },
                                                {
                                                    "name": "copy_facebook_adset_to_campaign",
                                                    "status": "error",
                                                    "error": "please remove conflicting locations",
                                                },
                                            ]
                                        }
                                    }
                                ],
                            }
                        ],
                    }),
                    "checks": [
                        {
                            "id": "submit",
                            "status": "fail",
                            "message": "submit: submitted failed item count=1, expected 0",
                        }
                    ],
                }
            ],
        }),
        encoding="utf-8",
    )

    assert main(["report", "--recent", "1", "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)

    assert batch["runs"][0]["failure_reasons"] == ["please remove conflicting locations"]
    assert batch["failure_groups"] == [
        {
            "reason": "please remove conflicting locations",
            "count": 1,
            "loops": ["reference_campaign_new_campaign"],
        }
    ]


def test_report_recent_extracts_attention_flags_for_incomplete_agent_chain(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    run_dir = tmp_path / ".meguri" / "runs" / "run_20260613_120000_incomplete"
    run_dir.mkdir(parents=True)
    (run_dir / "index.html").write_text("<html>incomplete</html>", encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps({
            "run_id": run_dir.name,
            "scenario_name": "agent_chain_preview_only",
            "status": "fail",
            "mode": "execute",
            "finished_at": "2026-06-13T12:00:00+00:00",
            "artifact_dir": str(run_dir),
            "metadata": {"loop_id": "agent_chain_preview_only"},
            "steps": [
                {
                    "step_id": "run",
                    "status": "fail",
                    "stdout": json.dumps({
                        "passed": False,
                        "final_submit": True,
                        "submitted": False,
                        "turn_count": 1,
                        "expected_turn_count": 7,
                        "errors": ["confirm_1: exception ValidationError: bad AgentResponse"],
                        "crash_tracebacks": ["Traceback...\nAgentResponseParseError: missing reply and plan"],
                    }),
                    "checks": [
                        {"id": "turn_count", "status": "fail", "message": "$.turn_count=1"},
                        {"id": "submitted", "status": "fail", "message": "$.submitted=False"},
                    ],
                }
            ],
        }),
        encoding="utf-8",
    )

    assert main(["report", "--recent", "1", "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)
    run = batch["runs"][0]

    assert batch["attention_count"] == 3
    assert [flag["code"] for flag in batch["attention_flags"]] == [
        "short_run",
        "not_submitted",
        "crash_traceback",
    ]
    assert run["attention_count"] == 3
    assert run["attention_flags"][0]["message"] == "turn_count 1 below expected 7"
    assert run["metrics"]["expected_turn_count"] == 7
    html = Path(batch["html_report_path"]).read_text(encoding="utf-8")
    assert "Attention Flags" in html
    assert "short_run" in html
    assert "turns=1/7" in html


def test_report_recent_surfaces_repair_hints_for_failed_batch(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    runs_root = tmp_path / ".meguri" / "runs"
    cases = [
        (
            "run_20260613_120000_video",
            "material_reference",
            {
                "submitted": True,
                "turn_count": 7,
                "expected_turn_count": 7,
                "submit_results": [{"ok": False, "error": "Param video_id is not a valid video_id ID"}],
            },
        ),
        (
            "run_20260613_121000_preview",
            "preview_only",
            {
                "final_submit": True,
                "submitted": False,
                "turn_count": 1,
                "expected_turn_count": 7,
            },
        ),
        (
            "run_20260613_122000_partial",
            "reference_campaign",
            {
                "submitted": True,
                "submit_results": [
                    {"ok": True, "resource_type": "campaign", "campaign_id": "120250081016770683"},
                    {"ok": False, "error": "please remove conflicting locations"},
                ],
            },
        ),
    ]
    for run_id, loop, stdout_payload in cases:
        run_dir = runs_root / run_id
        run_dir.mkdir(parents=True)
        (run_dir / "index.html").write_text(f"<html>{loop}</html>", encoding="utf-8")
        (run_dir / "run.json").write_text(
            json.dumps({
                "run_id": run_id,
                "scenario_name": loop,
                "status": "fail",
                "mode": "execute",
                "finished_at": "2026-06-13T12:00:00+00:00",
                "artifact_dir": str(run_dir),
                "metadata": {"loop_id": loop},
                "steps": [
                    {
                        "step_id": "run",
                        "status": "fail",
                        "stdout": json.dumps(stdout_payload),
                        "checks": [{"id": "exit", "status": "fail", "message": "loop failed"}],
                    }
                ],
            }),
            encoding="utf-8",
        )

    assert main(["report", "--recent", "3", "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)

    assert [hint["code"] for hint in batch["repair_hints"]] == [
        "verify_test_data",
        "complete_agent_chain",
        "audit_execute_side_effects",
    ]
    assert batch["repair_hints"][0]["loops"] == ["material_reference", "reference_campaign"]
    assert batch["repair_hints"][1]["loops"] == ["preview_only"]
    assert batch["repair_hints"][2]["resource_count"] == 1
    html = Path(batch["html_report_path"]).read_text(encoding="utf-8")
    assert "Repair Hints" in html
    assert "verify_test_data" in html
    assert "complete_agent_chain" in html
    assert "audit_execute_side_effects" in html


def test_report_recent_surfaces_failed_items_for_prompt_repair(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    run_dir = tmp_path / ".meguri" / "runs" / "run_20260613_120000_failed_items"
    run_dir.mkdir(parents=True)
    (run_dir / "index.html").write_text("<html>failed items</html>", encoding="utf-8")
    (run_dir / "run.json").write_text(
        json.dumps({
            "run_id": run_dir.name,
            "scenario_name": "ai_source_ad_copy",
            "status": "fail",
            "mode": "execute",
            "finished_at": "2026-06-13T12:00:00+00:00",
            "artifact_dir": str(run_dir),
            "metadata": {"loop_id": "ai_source_ad_copy"},
            "steps": [
                {
                    "step_id": "run",
                    "status": "fail",
                    "stdout": json.dumps({
                        "submitted": True,
                        "turns": [
                            {
                                "id": "submit",
                                "events": [
                                    {
                                        "tool_result": {
                                            "items": [
                                                {
                                                    "id": "120246917768180090",
                                                    "name": "copy_facebook_ad_to_adset",
                                                    "status": "error",
                                                    "error": "image could not be loaded",
                                                    "resource_type": "ad",
                                                }
                                            ]
                                        }
                                    }
                                ],
                            }
                        ],
                    }),
                    "checks": [{"id": "exit", "status": "fail", "message": "image could not be loaded"}],
                }
            ],
        }),
        encoding="utf-8",
    )

    assert main(["report", "--recent", "1", "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)

    assert batch["failed_item_count"] == 1
    assert batch["failed_items"] == [
        {
            "loop": "ai_source_ad_copy",
            "run_id": "run_20260613_120000_failed_items",
            "type": "ad",
            "id": "120246917768180090",
            "name": "copy_facebook_ad_to_adset",
            "error": "image could not be loaded",
            "source": "items",
        }
    ]
    assert batch["runs"][0]["failed_item_count"] == 1
    assert batch["runs"][0]["failed_items"][0]["id"] == "120246917768180090"
    html = Path(batch["html_report_path"]).read_text(encoding="utf-8")
    assert "Failed Items" in html
    assert "120246917768180090" in html
    assert "image could not be loaded" in html


def test_report_recent_surfaces_validation_issues_for_schema_failures(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    run_dir = tmp_path / ".meguri" / "runs" / "run_20260613_120000_validation"
    run_dir.mkdir(parents=True)
    (run_dir / "index.html").write_text("<html>validation</html>", encoding="utf-8")
    stdout_payload = {
        "passed": False,
        "turn_count": 5,
        "expected_turn_count": 7,
        "errors": [
            "confirm_3: exception ValidationError: 11 validation errors for AgentResponse\n"
            "plan.panel.DRAFTING.display.CopyAdConfirm.cards.0.subtitle\n"
            "  Extra inputs are not permitted [type=extra_forbidden, input_value='19 条源广告复制到 2 个目标 Campaign', input_type=str]\n"
            "plan.panel.DRAFTING.display.BatchEditConfirm.display_schema\n"
            "  Input should be 'batch_edit_confirm' [type=literal_error, input_value='copy_ad_confirm', input_type=str]\n"
        ],
        "crash_tracebacks": [
            "AgentResponseParseError: 模型输出中只找到 panel/display/notices/draft 等内部 JSON 片段，没有完整 AgentResponse；顶层必须包含 reply 和 plan。"
        ],
    }
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "run_id": run_dir.name,
                "scenario_name": "wide_3d_copy",
                "status": "fail",
                "mode": "execute",
                "finished_at": "2026-06-13T12:00:00+00:00",
                "artifact_dir": str(run_dir),
                "metadata": {"loop_id": "wide_3d_copy"},
                "steps": [
                    {
                        "step_id": "run",
                        "status": "fail",
                        "stdout": json.dumps(stdout_payload, ensure_ascii=False),
                        "checks": [{"id": "exit", "status": "fail", "message": "schema failed"}],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    assert main(["report", "--recent", "1", "--json"]) == 0
    batch = json.loads(capsys.readouterr().out)

    assert batch["validation_issue_count"] == 2
    assert [hint["code"] for hint in batch["repair_hints"]] == [
        "fix_schema_output",
        "complete_agent_chain",
    ]
    assert batch["repair_hints"][0]["issue_count"] == 2
    assert batch["validation_issues"][0] == {
        "loop": "wide_3d_copy",
        "run_id": "run_20260613_120000_validation",
        "code": "schema_validation",
        "severity": "error",
        "object": "AgentResponse",
        "count": "11",
        "path": "plan.panel.DRAFTING.display.CopyAdConfirm.cards.0.subtitle",
        "types": "extra_forbidden,literal_error",
        "message": "AgentResponse validation failed with 11 errors at plan.panel.DRAFTING.display.CopyAdConfirm.cards.0.subtitle (extra_forbidden,literal_error)",
        "source": "errors",
    }
    assert batch["runs"][0]["validation_issue_count"] == 2
    html = Path(batch["html_report_path"]).read_text(encoding="utf-8")
    assert "Validation Issues" in html
    assert "schema_validation" in html
    assert "plan.panel.DRAFTING.display.CopyAdConfirm.cards.0.subtitle" in html


def test_report_recent_json_prints_clean_batch_record(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
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


def test_report_refresh_rewrites_single_run_html_from_run_json(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    run_dir = tmp_path / ".meguri" / "runs" / "run_20260613_120000_refresh"
    run_dir.mkdir(parents=True)
    html_path = run_dir / "index.html"
    markdown_path = run_dir / "report.md"
    html_path.write_text("<html>stale</html>", encoding="utf-8")
    markdown_path.write_text("# stale", encoding="utf-8")
    run_dir.joinpath("run.json").write_text(
        json.dumps({
            "run_id": run_dir.name,
            "scenario_name": "reference_campaign_new_campaign",
            "status": "fail",
            "started_at": "2026-06-13T11:59:00+00:00",
            "finished_at": "2026-06-13T12:00:00+00:00",
            "project_path": str(tmp_path),
            "artifact_dir": str(run_dir),
            "metadata": {"loop_id": "reference_campaign_new_campaign", "mode": "execute"},
            "steps": [
                {
                    "step_id": "run",
                    "status": "fail",
                    "started_at": "2026-06-13T11:59:00+00:00",
                    "finished_at": "2026-06-13T12:00:00+00:00",
                    "exit_code": 1,
                    "stdout": json.dumps({
                        "submitted": True,
                        "turns": [
                            {
                                "events": [
                                    {
                                        "tool_result": {
                                            "items": [
                                                {
                                                    "id": "120250081240970683",
                                                    "name": "copy_facebook_campaign_to_account",
                                                    "status": "success",
                                                },
                                                {
                                                    "name": "copy_facebook_adset_to_campaign",
                                                    "status": "error",
                                                    "error": "please remove conflicting locations",
                                                },
                                            ]
                                        }
                                    }
                                ]
                            }
                        ],
                    }),
                    "checks": [
                        {
                            "id": "submit",
                            "status": "fail",
                            "message": "submit: submitted failed item count=1, expected 0",
                        }
                    ],
                }
            ],
        }),
        encoding="utf-8",
    )

    assert main(["report", run_dir.name, "--refresh"]) == 0

    assert capsys.readouterr().out.strip() == str(html_path)
    refreshed = html_path.read_text(encoding="utf-8")
    assert "stale" not in refreshed
    assert "Failure Reasons" in refreshed
    assert "<span>Mode</span><strong>execute</strong>" in refreshed
    assert "please remove conflicting locations" in refreshed
    assert "Created Resources" in refreshed
    assert "120250081240970683" in refreshed
    refreshed_markdown = markdown_path.read_text(encoding="utf-8")
    assert "stale" not in refreshed_markdown
    assert "# Meguri Loop Run: reference_campaign_new_campaign" in refreshed_markdown
    assert "- mode: `execute`" in refreshed_markdown
    assert "| `submit` | `fail` | submit: submitted failed item count=1, expected 0 |" in refreshed_markdown


def test_report_last_json_selects_newest_single_run(tmp_path: Path, monkeypatch, capsys) -> None:
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

    assert main(["report", "--last", "--json"]) == 0
    record = json.loads(capsys.readouterr().out)

    assert record["kind"] == "run"
    assert record["loop"] == "new_loop"
    assert record["run_id"] == "run_20260613_120000_new"


def test_validate_accepts_generated_pack_and_rejects_unknown_adapter(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert main(["init", "--offline"]) == 0
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
