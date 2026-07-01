from __future__ import annotations

from pathlib import Path


def test_install_script_forces_pipx_pip_backend() -> None:
    script = Path("install.sh").read_text(encoding="utf-8")

    assert "PIPX_DEFAULT_BACKEND=pip" in script
    assert "--backend pip" in script


def test_install_script_accepts_install_skills_without_forwarding_to_init() -> None:
    script = Path("install.sh").read_text(encoding="utf-8")

    assert "--install-skills)" in script
    assert "init_args+=(--install-skills)" not in script
