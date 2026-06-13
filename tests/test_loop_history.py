from __future__ import annotations

from pathlib import Path

from meguri.project.pack import load_project_pack, resolve_scenario


def test_pack_exposes_loop_definition_and_run_paths(tmp_path: Path) -> None:
    pack = load_project_pack(tmp_path)

    loop_path = pack.loop_definition_path("checkout")
    run_dir = pack.loop_run_dir("checkout", "20260613_152717")

    assert loop_path == tmp_path / ".meguri" / "loops" / "checkout" / "_loop.yaml"
    assert run_dir == tmp_path / ".meguri" / "loops" / "checkout" / "20260613_152717"


def test_resolve_scenario_prefers_loop_folder_definition(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    loop_file = tmp_path / ".meguri" / "loops" / "checkout" / "_loop.yaml"
    loop_file.parent.mkdir(parents=True)
    loop_file.write_text("name: checkout\nadapter: shell\nproject_path: ../../..\nsteps: []\n", encoding="utf-8")

    assert resolve_scenario("checkout") == loop_file.resolve()
