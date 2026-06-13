from __future__ import annotations

from pathlib import Path


def test_install_script_forces_pipx_pip_backend() -> None:
    script = Path("install.sh").read_text(encoding="utf-8")

    assert "PIPX_DEFAULT_BACKEND=pip" in script
    assert "--backend pip" in script
