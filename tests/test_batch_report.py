from __future__ import annotations

from pathlib import Path

from meguri.reports.batch import render_batch_html


def test_batch_html_groups_repeated_loop_attempts(tmp_path: Path) -> None:
    batch_dir = tmp_path / "batch"
    first_report = tmp_path / "loops" / "checkout" / "20260615_101000" / "index.html"
    second_report = tmp_path / "loops" / "checkout" / "20260615_101500" / "index.html"
    first_report.parent.mkdir(parents=True)
    second_report.parent.mkdir(parents=True)
    first_report.write_text("<html>first</html>", encoding="utf-8")
    second_report.write_text("<html>second</html>", encoding="utf-8")
    batch_dir.mkdir()

    html = render_batch_html(
        {
            "batch_id": "20260615_102000_123456",
            "status": "pass",
            "started_at": "2026-06-15T10:20:00+00:00",
            "updated_at": "2026-06-15T10:25:00+00:00",
            "finished_at": "2026-06-15T10:25:00+00:00",
            "completed_loops": 2,
            "total_loops": 2,
            "runs": [
                {
                    "loop": "checkout",
                    "run_id": "20260615_101000",
                    "status": "fail",
                    "mode": "execute",
                    "summary": "submit failed",
                    "html_report_path": str(first_report),
                },
                {
                    "loop": "checkout",
                    "run_id": "20260615_101500",
                    "status": "pass",
                    "mode": "execute",
                    "summary": "pass",
                    "html_report_path": str(second_report),
                },
            ],
        },
        batch_dir,
    )

    assert "Loop Attempts" in html
    assert "Attempt 1" in html
    assert "Attempt 2" in html
    assert "1 / 2" in html
    assert "2 / 2" in html
    assert html.index("20260615_101000") < html.index("20260615_101500")
