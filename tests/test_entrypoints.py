from __future__ import annotations

from pathlib import Path

import pytest

from meguri.cli.entrypoints import (
    ENTRYPOINT_SPECS,
    SkillRefreshError,
    refresh_entrypoints,
)


def test_refresh_entrypoints_fetches_remote_templates_and_overwrites_only_entrypoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    user_loop = project / ".meguri" / "loops" / "checkout" / "_loop.yaml"
    user_loop.parent.mkdir(parents=True)
    user_loop.write_text("user loop\n", encoding="utf-8")
    evidence = project / ".meguri" / "evidence" / "evidence.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("{}", encoding="utf-8")

    def fake_fetch(url: str) -> str:
        name = url.rsplit("/", 1)[-1]
        return f"remote template for {name}\n/meguri\nmeguri init\nmeguri run\nmeguri report\n"

    written = refresh_entrypoints(project, offline=False, fetch_text=fake_fetch)

    rel_written = sorted(_display(project, path) for path in written)
    assert rel_written == [
        ".agents/skills/meguri/SKILL.md",
        ".claude/commands/meguri.md",
        ".claude/skills/meguri/SKILL.md",
        str(tmp_path / "home" / ".codex" / "prompts" / "meguri.md"),
    ]
    for spec in ENTRYPOINT_SPECS:
        path = spec.path_for(project)
        assert path.read_text(encoding="utf-8").startswith("remote template")
    assert user_loop.read_text(encoding="utf-8") == "user loop\n"
    assert evidence.read_text(encoding="utf-8") == "{}"


def test_refresh_entrypoints_offline_uses_bundled_templates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()

    def forbidden_fetch(url: str) -> str:
        raise AssertionError(f"offline mode should not fetch {url}")

    written = refresh_entrypoints(project, offline=True, fetch_text=forbidden_fetch)

    assert len(written) == 4
    codex_skill = project / ".agents" / "skills" / "meguri" / "SKILL.md"
    text = codex_skill.read_text(encoding="utf-8")
    assert "Trigger for $meguri, loop design" in text
    assert "Trigger for $meguri or /meguri" not in text
    combined = "\n".join(spec.path_for(project).read_text(encoding="utf-8") for spec in ENTRYPOINT_SPECS)
    assert "/meguri" in combined
    assert "meguri init" in combined
    assert "meguri run" in combined
    assert "meguri report" in combined


def test_refresh_entrypoints_remote_failure_raises_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()

    def failing_fetch(url: str) -> str:
        raise OSError("network down")

    with pytest.raises(SkillRefreshError, match="network down"):
        refresh_entrypoints(project, offline=False, fetch_text=failing_fetch)

    assert not (project / ".agents").exists()
    assert not (project / ".claude").exists()
    assert not (tmp_path / "home" / ".codex" / "prompts" / "meguri.md").exists()


def _display(project: Path, path: Path) -> str:
    try:
        return str(path.relative_to(project))
    except ValueError:
        return str(path)
