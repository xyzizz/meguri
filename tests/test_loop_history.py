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
    batch_dir = tmp_path / ".meguri" / "batches" / "20260613_160000_123456"
    run_dir.mkdir(parents=True)
    batch_dir.mkdir(parents=True)
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
    (batch_dir / "batch.json").write_text(
        json.dumps({
            "batch_id": "20260613_160000_123456",
            "status": "fail",
            "finished_at": "2026-06-13T16:00:00+00:00",
            "runs": [],
        }),
        encoding="utf-8",
    )
    (batch_dir / "index.html").write_text("<html>batch</html>", encoding="utf-8")

    loop_html = render_loop_index(loop_dir)
    project_html = render_project_index(tmp_path / ".meguri")

    assert "20260613_152717" in loop_html
    assert "20260613_152717/index.html" in loop_html
    assert "--glow-primary" in loop_html
    assert "glow-bg" in loop_html
    assert "checkout" in project_html
    assert "loops/checkout/index.html" in project_html
    assert "--glow-primary" in project_html
    assert "glow-bg" in project_html
    assert "Batch Runs" in project_html
    assert "20260613_160000_123456" in project_html
    assert "batches/20260613_160000_123456/index.html" in project_html


def test_project_index_renders_operational_dashboard_summary(tmp_path: Path) -> None:
    pack_root = tmp_path / ".meguri"
    loop_dir = pack_root / "loops" / "checkout_flow"
    first_run = loop_dir / "20260613_152717"
    second_run = loop_dir / "20260613_160000"
    batch_dir = pack_root / "batches" / "20260613_170000_123456"
    first_run.mkdir(parents=True)
    second_run.mkdir(parents=True)
    batch_dir.mkdir(parents=True)
    (first_run / "run.json").write_text(
        json.dumps({
            "run_id": "20260613_152717",
            "status": "pass",
            "mode": "dry_run",
            "started_at": "2026-06-13T15:27:17+00:00",
            "finished_at": "2026-06-13T15:27:20+00:00",
            "html_report_path": str(first_run / "index.html"),
        }),
        encoding="utf-8",
    )
    (second_run / "run.json").write_text(
        json.dumps({
            "run_id": "20260613_160000",
            "status": "fail",
            "mode": "execute",
            "started_at": "2026-06-13T16:00:00+00:00",
            "updated_at": "2026-06-13T16:04:00+00:00",
            "html_report_path": str(second_run / "index.html"),
            "summary": "submit boundary failed",
        }),
        encoding="utf-8",
    )
    (batch_dir / "batch.json").write_text(
        json.dumps({
            "batch_id": "20260613_170000_123456",
            "status": "running",
            "started_at": "2026-06-13T17:00:00+00:00",
            "updated_at": "2026-06-13T17:02:00+00:00",
            "completed_loops": 1,
            "total_loops": 3,
            "current_loop": "checkout_flow",
            "runs": [{"loop": "checkout_flow", "status": "fail"}],
        }),
        encoding="utf-8",
    )

    project_html = render_project_index(pack_root)

    assert "Meguri Control Room" in project_html
    assert "workspace-kpis" in project_html
    assert "Latest activity" in project_html
    assert "status-badge status-fail" in project_html
    assert "status-badge status-running" in project_html
    assert "submit boundary failed" in project_html
    assert "1 / 3" in project_html
    assert "loops/checkout_flow/20260613_160000/index.html" in project_html
    assert "batches/20260613_170000_123456/index.html" in project_html


def test_project_index_separates_report_snapshots_from_run_batches(tmp_path: Path) -> None:
    pack_root = tmp_path / ".meguri"
    run_batch_dir = pack_root / "batches" / "20260613_170000_123456"
    snapshot_dir = pack_root / "batches" / "20260613_171000_123456"
    run_batch_dir.mkdir(parents=True)
    snapshot_dir.mkdir(parents=True)
    (run_batch_dir / "batch.json").write_text(
        json.dumps({
            "batch_id": "20260613_170000_123456",
            "status": "pass",
            "started_at": "2026-06-13T17:00:00+00:00",
            "finished_at": "2026-06-13T17:02:00+00:00",
            "runs": [],
        }),
        encoding="utf-8",
    )
    (snapshot_dir / "batch.json").write_text(
        json.dumps({
            "batch_id": "20260613_171000_123456",
            "source": "latest_loops",
            "status": "blocked",
            "started_at": "2026-06-13T16:00:00+00:00",
            "updated_at": "2026-06-13T17:10:00+00:00",
            "planned_loops": ["checkout_flow"],
            "runs": [{"loop": "checkout_flow", "status": "blocked"}],
        }),
        encoding="utf-8",
    )

    project_html = render_project_index(pack_root)

    batch_section = project_html.split("<h2>Batch Runs</h2>", 1)[1].split("<h2>Report Snapshots</h2>", 1)[0]
    snapshot_section = project_html.split("<h2>Report Snapshots</h2>", 1)[1]
    assert "20260613_170000_123456" in batch_section
    assert "20260613_171000_123456" not in batch_section
    assert "20260613_171000_123456" in snapshot_section
    assert "latest_loops" in snapshot_section


def test_loop_index_renders_run_history_with_replay_state(tmp_path: Path) -> None:
    loop_dir = tmp_path / ".meguri" / "loops" / "checkout_flow"
    run_dir = loop_dir / "20260613_152717"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text(
        json.dumps({
            "run_id": "20260613_152717",
            "status": "blocked",
            "mode": "dry_run",
            "started_at": "2026-06-13T15:27:17+00:00",
            "finished_at": "2026-06-13T15:27:20+00:00",
            "summary": "needs credentials",
            "replay": {"replay": {"status": "partial"}},
        }),
        encoding="utf-8",
    )

    loop_html = render_loop_index(loop_dir)

    assert "Loop Detail" in loop_html
    assert "run-history" in loop_html
    assert "status-badge status-blocked" in loop_html
    assert "needs credentials" in loop_html
    assert "partial" in loop_html
