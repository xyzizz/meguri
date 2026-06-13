from __future__ import annotations

from pathlib import Path
import json

from meguri.project.pack import load_project_pack, resolve_scenario
from meguri.reports.indexes import render_loop_index, render_project_index


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


def test_render_loop_and_project_indexes_link_to_run_reports(tmp_path: Path) -> None:
    loop_dir = tmp_path / ".meguri" / "loops" / "checkout"
    run_dir = loop_dir / "20260613_152717"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps({
            "run_id": "20260613_152717",
            "status": "pass",
            "finished_at": "2026-06-13T15:27:20+00:00",
            "artifact_dir": str(run_dir),
            "replay": {"replay": {"status": "full"}},
        }),
        encoding="utf-8",
    )
    (run_dir / "index.html").write_text("<html>detail</html>", encoding="utf-8")

    loop_html = render_loop_index(loop_dir)
    project_html = render_project_index(tmp_path / ".meguri")

    assert "20260613_152717" in loop_html
    assert "20260613_152717/index.html" in loop_html
    assert "checkout" in project_html
    assert "loops/checkout/index.html" in project_html
