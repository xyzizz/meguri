from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from meguri.core.models import utc_now
from meguri.evaluators.deterministic import extract_last_json
from meguri.project.pack import ProjectPack, find_project_pack
from meguri.reports.batch import (
    batch_failed_loops,
    batch_retry_command,
    batch_retry_loops,
    batch_status_counts,
    failure_groups,
    render_batch_html,
)
from meguri.reports.indexes import render_project_index
from meguri.reports.metrics import extract_run_metrics_from_steps


def handle_report(args: Any) -> int:
    try:
        pack = find_project_pack(Path.cwd())
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        if args.recent is not None:
            batch_record = recent_batch_report(pack, args.recent)
            html_path = Path(batch_record["html_report_path"])
        else:
            if getattr(args, "json", False):
                raise FileNotFoundError("--json is only supported with --recent")
            html_path = latest_report(pack) if args.last or not args.run_id else report_for_run(pack, args.run_id)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps(batch_record, ensure_ascii=False, indent=2, default=str))
    else:
        print(html_path)
    if args.open:
        if not open_path(html_path):
            print(f"could not open report automatically: {html_path}", file=sys.stderr)
    return 0


def latest_report(pack: ProjectPack) -> Path:
    candidates = _loop_report_dirs(pack)
    candidates.extend(_batch_report_dirs(pack))
    if pack.runs_dir.is_dir():
        candidates.extend([path for path in pack.runs_dir.iterdir() if (path / "index.html").is_file()])
    if not candidates:
        raise FileNotFoundError(f"no HTML reports found in {pack.pack_root}")
    return max(candidates, key=_report_sort_key) / "index.html"


def recent_batch_report(pack: ProjectPack, limit: int) -> dict[str, Any]:
    if limit <= 0:
        raise FileNotFoundError("--recent must be greater than 0")
    candidates = _loop_report_dirs(pack)
    if pack.runs_dir.is_dir():
        candidates.extend([path for path in pack.runs_dir.iterdir() if (path / "index.html").is_file()])
    selected = sorted(candidates, key=_report_sort_key, reverse=True)[:limit]
    if not selected:
        raise FileNotFoundError(f"no standalone run reports found in {pack.pack_root}")
    selected = sorted(selected, key=_report_sort_key)
    runs = [_run_summary_from_json(path) for path in selected]
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    batch_dir = pack.pack_root / "batches" / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    retry_loops = batch_retry_loops(runs)
    record = {
        "batch_id": batch_id,
        "source": "recent_runs",
        "status": _batch_status(runs),
        "started_at": _first_timestamp(selected) or utc_now(),
        "updated_at": utc_now(),
        "finished_at": _last_timestamp(selected) or "",
        "batch_dir": str(batch_dir),
        "html_report_path": str(batch_dir / "index.html"),
        "planned_loops": [str(run.get("loop") or "") for run in runs],
        "completed_loops": len(runs),
        "total_loops": len(runs),
        "current_loop": "",
        "remaining_loops": [],
        "status_counts": batch_status_counts(runs),
        "failed_loops": batch_failed_loops(runs),
        "retry_loops": retry_loops,
        "retry_command": batch_retry_command(runs),
        "failure_groups": failure_groups(runs),
        "runs": runs,
    }
    batch_dir.joinpath("batch.json").write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    batch_dir.joinpath("index.html").write_text(render_batch_html(record, batch_dir), encoding="utf-8")
    pack.pack_root.joinpath("index.html").write_text(render_project_index(pack.pack_root), encoding="utf-8")
    return record


def report_for_run(pack: ProjectPack, run_id: str) -> Path:
    if "/" in run_id:
        loop_id, child_run_id = run_id.split("/", 1)
        path = pack.loops_dir / loop_id / child_run_id / "index.html"
        if path.is_file():
            return path
        raise FileNotFoundError(f"report not found: {path}")

    matches = [path / "index.html" for path in _loop_report_dirs(pack) if path.name == run_id]
    batch = pack.pack_root / "batches" / run_id / "index.html"
    if batch.is_file():
        matches.append(batch)
    legacy = pack.runs_dir / run_id / "index.html"
    if legacy.is_file():
        matches.append(legacy)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise FileNotFoundError(f"run id is ambiguous; use <loop_id>/{run_id}")
    raise FileNotFoundError(f"report not found for run: {run_id}")


def _loop_report_dirs(pack: ProjectPack) -> list[Path]:
    if not pack.loops_dir.is_dir():
        return []
    candidates = []
    for loop_dir in sorted(path for path in pack.loops_dir.iterdir() if path.is_dir()):
        for run_dir in sorted(path for path in loop_dir.iterdir() if path.is_dir() and not path.name.startswith("_")):
            if (run_dir / "index.html").is_file():
                candidates.append(run_dir)
    return candidates


def _batch_report_dirs(pack: ProjectPack) -> list[Path]:
    batches_dir = pack.pack_root / "batches"
    if not batches_dir.is_dir():
        return []
    return [
        batch_dir
        for batch_dir in sorted(path for path in batches_dir.iterdir() if path.is_dir())
        if (batch_dir / "index.html").is_file()
    ]


def _report_sort_key(path: Path) -> tuple[float, str]:
    recorded = _recorded_report_time(path)
    if recorded is not None:
        return (recorded, path.name)
    return (path.stat().st_mtime, path.name)


def _recorded_report_time(report_dir: Path) -> float | None:
    for name in ("run.json", "batch.json"):
        recorded = _recorded_json_time(report_dir / name)
        if recorded is not None:
            return recorded
    return None


def _first_timestamp(report_dirs: list[Path]) -> str | None:
    for report_dir in report_dirs:
        value = _recorded_json_timestamp(report_dir / "run.json", keys=("started_at", "finished_at"))
        if value:
            return value
    return None


def _last_timestamp(report_dirs: list[Path]) -> str | None:
    for report_dir in reversed(report_dirs):
        value = _recorded_json_timestamp(report_dir / "run.json", keys=("finished_at", "updated_at", "started_at"))
        if value:
            return value
    return None


def _recorded_json_timestamp(path: Path, *, keys: tuple[str, ...]) -> str | None:
    raw = _read_json(path)
    if not isinstance(raw, dict):
        return None
    for key in keys:
        value = raw.get(key)
        if value:
            return str(value)
    return None


def _recorded_json_time(path: Path) -> float | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    for key in ("finished_at", "updated_at", "started_at"):
        value = raw.get(key)
        if not value:
            continue
        parsed = _parse_timestamp(str(value))
        if parsed is not None:
            return parsed
    return None


def _parse_timestamp(value: str) -> float | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _run_summary_from_json(report_dir: Path) -> dict[str, Any]:
    raw = _read_json(report_dir / "run.json")
    raw = raw if isinstance(raw, dict) else {}
    loop = _loop_name_from_raw(raw, report_dir)
    status = str(raw.get("status") or "blocked")
    failure_reasons = _failure_reasons_from_raw(raw)
    summary = {
        "loop": loop,
        "run_id": str(raw.get("run_id") or report_dir.name),
        "status": status,
        "mode": _mode_from_raw(raw),
        "artifact_dir": str(raw.get("artifact_dir") or report_dir),
        "html_report_path": str(report_dir / "index.html"),
        "summary": "; ".join(failure_reasons) if failure_reasons else status,
        "failure_reasons": failure_reasons,
    }
    metrics = extract_run_metrics_from_steps(raw.get("steps") or [])
    if metrics:
        summary["metrics"] = metrics
    return summary


def _loop_name_from_raw(raw: dict[str, Any], report_dir: Path) -> str:
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    return str(metadata.get("loop_id") or raw.get("scenario_name") or raw.get("name") or report_dir.name)


def _mode_from_raw(raw: dict[str, Any]) -> str:
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    return str(raw.get("mode") or metadata.get("mode") or "")


def _failure_reasons_from_raw(raw: dict[str, Any]) -> list[str]:
    if raw.get("status") == "pass":
        return []
    json_reasons: list[str] = []
    fallback_reasons: list[str] = []
    for step in raw.get("steps") or []:
        if not isinstance(step, dict):
            continue
        stdout = step.get("stdout")
        if isinstance(stdout, str) and stdout:
            try:
                json_reasons.extend(_json_failure_reasons(extract_last_json(stdout)))
            except ValueError:
                pass
        for check in step.get("checks") or []:
            if not isinstance(check, dict):
                continue
            if check.get("status") not in {"pass", "warning"} and isinstance(check.get("message"), str):
                fallback_reasons.append(check["message"])
        stderr = step.get("stderr")
        if not fallback_reasons and isinstance(stderr, str) and stderr:
            fallback_reasons.append(_last_nonempty_line(stderr))
    return _dedupe_reasons(json_reasons or fallback_reasons)


def _json_failure_reasons(value: Any) -> list[str]:
    reasons: list[str] = []
    if isinstance(value, dict):
        reasons.extend(_string_list(value.get("failure_reasons")))
        reasons.extend(_string_list(value.get("errors")))
        if isinstance(value.get("error"), str):
            reasons.append(value["error"])
        for key in ("submit_results", "tool_results", "results", "items", "failed_submit_items"):
            reasons.extend(_failed_item_reasons(value.get(key)))
    return reasons


def _failed_item_reasons(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    reasons: list[str] = []
    for item in value:
        if isinstance(item, str):
            reasons.append(item)
            continue
        if not isinstance(item, dict):
            continue
        ok = item.get("ok")
        status = str(item.get("status") or item.get("result") or "").lower()
        failed = ok is False or status in {"fail", "failed", "error", "blocked"}
        if not failed and not item.get("error"):
            continue
        for key in ("error", "message", "reason"):
            if isinstance(item.get(key), str):
                reasons.append(item[key])
        result = item.get("result")
        if isinstance(result, dict):
            for key in ("error", "message", "reason"):
                if isinstance(result.get(key), str):
                    reasons.append(result[key])
    return reasons


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _last_nonempty_line(value: str) -> str:
    for line in reversed(value.splitlines()):
        stripped = line.strip()
        if stripped:
            return stripped
    return value.strip()


def _dedupe_reasons(values: list[str], *, limit: int = 5) -> list[str]:
    reasons: list[str] = []
    seen: set[str] = set()
    for value in values:
        reason = " ".join(str(value).split())
        if not reason or reason in seen:
            continue
        seen.add(reason)
        reasons.append(reason[:500])
        if len(reasons) >= limit:
            break
    return reasons


def _batch_status(runs: list[dict[str, Any]]) -> str:
    statuses = {str(run.get("status") or "") for run in runs}
    if "fail" in statuses:
        return "fail"
    if "blocked" in statuses:
        return "blocked"
    if "warning" in statuses:
        return "warning"
    if "running" in statuses:
        return "running"
    return "pass"


def open_path(path: Path) -> bool:
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", str(path)], check=False)
        elif system == "Windows":
            import os

            os.startfile(path)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", str(path)], check=False)
        return True
    except Exception:
        return False
