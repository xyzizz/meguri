from __future__ import annotations

import re
from pathlib import Path

import pytest

from meguri.cli.entrypoints import (
    ENTRYPOINT_SPECS,
    SkillRefreshError,
    bundled_templates,
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
    assert "normal user entrypoint is `/meguri`" in text
    assert "meguri add" not in text
    combined = "\n".join(spec.path_for(project).read_text(encoding="utf-8") for spec in ENTRYPOINT_SPECS)
    assert "/meguri" in combined
    assert "meguri init" in combined
    assert "meguri run" in combined
    assert "meguri report" in combined


def test_refresh_entrypoints_offline_validates_each_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()

    monkeypatch.setattr(
        "meguri.cli.entrypoints.bundled_templates",
        lambda: {
            "codex_skill": "/meguri\nmeguri init\nmeguri run\nmeguri report\n",
            "claude_skill": "/meguri\nmeguri init\nmeguri run\nmeguri report\n",
            "claude_command": "/meguri\nmeguri init\nmeguri run\nmeguri report\n",
            "codex_prompt": "/meguri\nmeguri init\nmeguri run\n",
        },
    )

    with pytest.raises(SkillRefreshError, match=r"codex_prompt\.md.*meguri report"):
        refresh_entrypoints(project, offline=True)

    assert not (project / ".agents").exists()
    assert not (project / ".claude").exists()
    assert not (tmp_path / "home" / ".codex" / "prompts" / "meguri.md").exists()


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


def test_refresh_entrypoints_bad_remote_template_raises_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()

    def fake_fetch(url: str) -> str:
        name = url.rsplit("/", 1)[-1]
        if name == "codex_prompt.md":
            return "remote template for codex_prompt.md\n/meguri\nmeguri init\nmeguri run\n"
        return f"remote template for {name}\n/meguri\nmeguri init\nmeguri run\nmeguri report\n"

    with pytest.raises(SkillRefreshError, match=r"codex_prompt\.md.*meguri report"):
        refresh_entrypoints(project, offline=False, fetch_text=fake_fetch)

    assert not (project / ".agents").exists()
    assert not (project / ".claude").exists()
    assert not (tmp_path / "home" / ".codex" / "prompts" / "meguri.md").exists()


def test_checked_in_templates_match_bundled_entrypoint_fallbacks() -> None:
    bundled = bundled_templates()

    assert set(bundled) == {spec.key for spec in ENTRYPOINT_SPECS}
    for spec in ENTRYPOINT_SPECS:
        path = Path("meguri/templates") / spec.remote_name
        assert path.read_text(encoding="utf-8") == bundled[spec.key], spec.key


def test_user_facing_docs_and_templates_do_not_reference_removed_public_surface() -> None:
    paths = [
        Path("README.md"),
        Path("README.zh-CN.md"),
        Path("PRODUCT.md"),
        Path("prompts/install.md"),
        Path("install.sh"),
        Path("meguri/cli/entrypoints.py"),
        Path("meguri/cli/inspect.py"),
        Path("meguri/cli/add.py"),
        *sorted(Path("meguri/templates").glob("*.md")),
    ]
    removed_surface = re.compile(
        r"meguri (add|loops|delete|validate|upgrade|inspect)"
        r"|/meguri upgrade"
        r"|report --(recent|runs|loops|running|refresh|last)"
        r"|run --(all|exclude|include-system)"
    )

    failures = []
    for path in paths:
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if removed_surface.search(line):
                failures.append(f"{path}:{line_no}: {line}")

    assert failures == []

    install_guidance = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (Path("README.md"), Path("prompts/install.md"), Path("install.sh"))
    )
    assert "official" in install_guidance
    assert "by default" in install_guidance
    assert "meguri init --offline" in install_guidance


def _display(project: Path, path: Path) -> str:
    try:
        return str(path.relative_to(project))
    except ValueError:
        return str(path)
