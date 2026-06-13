from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

from meguri.cli.main import main


def test_init_creates_project_pack_and_skills(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))

    assert main(["init", "--install-skills"]) == 0

    assert (tmp_path / ".meguri" / "project.yaml").is_file()
    assert (tmp_path / ".meguri" / "scenarios" / "smoke.yaml").is_file()
    assert (tmp_path / ".meguri" / "README.md").is_file()
    assert (tmp_path / ".agents" / "skills" / "meguri" / "SKILL.md").is_file()
    assert (tmp_path / ".claude" / "skills" / "meguri" / "SKILL.md").is_file()
    assert (tmp_path / "home" / ".codex" / "prompts" / "meguri.md").is_file()
    codex_skill = (tmp_path / ".agents" / "skills" / "meguri" / "SKILL.md").read_text(encoding="utf-8")
    claude_skill = (tmp_path / ".claude" / "skills" / "meguri" / "SKILL.md").read_text(encoding="utf-8")
    codex_prompt = (tmp_path / "home" / ".codex" / "prompts" / "meguri.md").read_text(encoding="utf-8")
    assert "meguri inspect" in codex_skill
    assert "test-flow design" in codex_skill
    assert "argument-hint: inspect|add|run|validate|report [args]" in codex_prompt
    assert "Use this active Codex session" in codex_prompt
    assert "meguri inspect" in claude_skill
    assert "argument-hint: inspect|add|run|validate|report [args]" in claude_skill


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
    assert "Use the\nactive AI session" in prompt
    assert "understanding, test-flow design" in prompt
    assert ".meguri/project-inspect.json" in prompt
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

    scenario_path = tmp_path / ".meguri" / "scenarios" / "login_flow.yaml"
    raw = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    assert raw["name"] == "login_flow"
    assert raw["adapter"] == "shell"
    assert raw["metadata"]["pass_criteria"] == "command exits with ok"


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
    assert html_path.parent.parent == tmp_path / ".meguri" / "runs"
    html = html_path.read_text(encoding="utf-8")
    assert "smoke" in html
    assert "passed" in html


def test_report_last_selects_newest_html_report(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    assert main(["run", "smoke"]) == 0
    capsys.readouterr()

    assert main(["report", "--last"]) == 0
    output = capsys.readouterr().out.strip()

    assert output.endswith("index.html")
    assert Path(output).is_file()


def test_validate_accepts_generated_pack_and_rejects_unknown_adapter(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    assert main(["init", "--install-skills"]) == 0
    capsys.readouterr()

    assert main(["validate"]) == 0
    assert "ok" in capsys.readouterr().out

    scenario_path = tmp_path / ".meguri" / "scenarios" / "smoke.yaml"
    raw = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
    raw["adapter"] = "missing_adapter"
    scenario_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    assert main(["validate"]) == 1
    assert "unknown adapter" in capsys.readouterr().out
