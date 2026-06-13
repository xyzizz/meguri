from __future__ import annotations

import json
import os
import platform
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from meguri.core.models import Artifact, CheckResult, RunReport, StepResult, utc_now
from meguri.project.pack import ProjectPack, find_project_pack
from meguri.reports.batch import (
    batch_attention_flags,
    batch_created_resources,
    batch_failed_items,
    batch_failed_loops,
    batch_repair_hints,
    batch_retry_command,
    batch_retry_loops,
    batch_status_counts,
    batch_validation_issues,
    failure_groups,
    render_batch_html,
)
from meguri.reports.indexes import render_project_index
from meguri.reports.metrics import (
    extract_attention_flags_from_steps,
    extract_created_resources_from_steps,
    extract_failed_items_from_steps,
    extract_failure_reasons_from_steps,
    extract_run_metrics_from_steps,
    extract_validation_issues_from_steps,
)
from meguri.reports.html import render_html_report
from meguri.reports.markdown import render_markdown_report


def handle_report(args: Any) -> int:
    try:
        pack = find_project_pack(Path.cwd())
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    json_record = None
    try:
        if getattr(args, "refresh", False) and (
            getattr(args, "running", False)
            or args.recent is not None
            or getattr(args, "runs", None)
            or getattr(args, "loops", None)
        ):
            raise FileNotFoundError("--refresh can only be used with a single run report")
        if getattr(args, "running", False):
            if args.run_id or args.last or args.recent is not None or getattr(args, "runs", None) or getattr(args, "loops", None):
                raise FileNotFoundError("--running cannot be combined with run id, --last, --recent, --runs, or --loops")
            running_record = running_reports(pack)
            if getattr(args, "json", False):
                print(json.dumps(running_record, ensure_ascii=False, indent=2, default=str))
            else:
                for path in running_record["html_report_paths"]:
                    print(path)
            if args.open and running_record["html_report_paths"]:
                if not open_path(Path(running_record["html_report_paths"][0])):
                    print(f"could not open report automatically: {running_record['html_report_paths'][0]}", file=sys.stderr)
            return 0
        if args.recent is not None:
            if getattr(args, "runs", None) or getattr(args, "loops", None):
                raise FileNotFoundError("--recent cannot be combined with --runs or --loops")
            batch_record = recent_batch_report(pack, args.recent)
            html_path = Path(batch_record["html_report_path"])
            json_record = batch_record
        elif getattr(args, "runs", None):
            if args.run_id or getattr(args, "loops", None):
                raise FileNotFoundError("--runs cannot be combined with run id or --loops")
            batch_record = selected_batch_report(pack, list(args.runs))
            html_path = Path(batch_record["html_report_path"])
            json_record = batch_record
        elif getattr(args, "loops", None):
            if args.run_id:
                raise FileNotFoundError("run id positional cannot be combined with --loops")
            batch_record = latest_loop_batch_report(pack, list(args.loops))
            html_path = Path(batch_record["html_report_path"])
            json_record = batch_record
        else:
            html_path = latest_report(pack) if args.last or not args.run_id else report_for_run(pack, args.run_id)
            if getattr(args, "refresh", False):
                refresh_run_html(html_path.parent)
            if getattr(args, "json", False):
                json_record = report_record_for_html(html_path)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps(json_record, ensure_ascii=False, indent=2, default=str))
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


def running_reports(pack: ProjectPack) -> dict[str, Any]:
    runs = []
    for report_dir in [*_loop_report_dirs(pack), *_legacy_report_dirs(pack)]:
        raw = _read_json(report_dir / "run.json")
        if not isinstance(raw, dict) or raw.get("status") != "running":
            continue
        summary = {"kind": "run", **_run_summary_from_json(report_dir)}
        current_step = _current_step_from_raw(raw)
        if current_step:
            summary["current_step"] = current_step
        if raw.get("updated_at"):
            summary["updated_at"] = str(raw["updated_at"])
        runs.append(summary)
    batches = []
    for report_dir in _batch_report_dirs(pack):
        raw = _read_json(report_dir / "batch.json")
        if not isinstance(raw, dict) or raw.get("status") != "running":
            continue
        batches.append({
            "kind": "batch",
            "batch_id": str(raw.get("batch_id") or report_dir.name),
            "status": "running",
            "current_loop": str(raw.get("current_loop") or ""),
            "remaining_loops": raw.get("remaining_loops") or [],
            "updated_at": str(raw.get("updated_at") or ""),
            "html_report_path": str(report_dir / "index.html"),
        })
    runs.sort(key=lambda item: str(item.get("updated_at") or ""))
    batches.sort(key=lambda item: str(item.get("updated_at") or ""))
    html_paths = [str(item["html_report_path"]) for item in [*runs, *batches]]
    return {
        "kind": "running_reports",
        "count": len(runs) + len(batches),
        "runs": runs,
        "batches": batches,
        "html_report_paths": html_paths,
    }


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
    return _write_selected_batch_report(pack, selected, source="recent_runs")


def selected_batch_report(pack: ProjectPack, refs: list[str]) -> dict[str, Any]:
    if not refs:
        raise FileNotFoundError("--runs requires at least one run id or report path")
    selected = [_report_dir_for_ref(pack, ref) for ref in refs]
    return _write_selected_batch_report(pack, selected, source="selected_runs", selected_refs=refs)


def latest_loop_batch_report(pack: ProjectPack, loops: list[str]) -> dict[str, Any]:
    if not loops:
        raise FileNotFoundError("--loops requires at least one loop name")
    selected = [_latest_report_dir_for_loop(pack, loop) for loop in loops]
    return _write_selected_batch_report(pack, selected, source="latest_loops", selected_loops=loops)


def _write_selected_batch_report(
    pack: ProjectPack,
    selected: list[Path],
    *,
    source: str,
    selected_refs: list[str] | None = None,
    selected_loops: list[str] | None = None,
) -> dict[str, Any]:
    runs = [_run_summary_from_json(path) for path in selected]
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    batch_dir = pack.pack_root / "batches" / batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)
    retry_loops = batch_retry_loops(runs)
    allow_execute_retry = _retry_needs_execute_approval(runs, retry_loops)
    created_resources = batch_created_resources(runs)
    failed_items = batch_failed_items(runs)
    validation_issues = batch_validation_issues(runs)
    attention_flags = batch_attention_flags(runs)
    repair_hints = batch_repair_hints(runs)
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
        "retry_command": batch_retry_command(runs, allow_execute=allow_execute_retry),
        "failure_groups": failure_groups(runs),
        "repair_hints": repair_hints,
        "attention_flags": attention_flags,
        "attention_count": len(attention_flags),
        "created_resources": created_resources,
        "created_resource_count": len(created_resources),
        "failed_items": failed_items,
        "failed_item_count": len(failed_items),
        "validation_issues": validation_issues,
        "validation_issue_count": len(validation_issues),
        "runs": runs,
    }
    record["source"] = source
    if selected_refs is not None:
        record["selected_refs"] = selected_refs
    if selected_loops is not None:
        record["selected_loops"] = selected_loops
    batch_dir.joinpath("batch.json").write_text(json.dumps(record, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    batch_dir.joinpath("index.html").write_text(render_batch_html(record, batch_dir), encoding="utf-8")
    pack.pack_root.joinpath("index.html").write_text(render_project_index(pack.pack_root), encoding="utf-8")
    return record


def _retry_needs_execute_approval(runs: list[dict[str, Any]], retry_loops: list[str]) -> bool:
    retry_set = set(retry_loops)
    return any(
        str(run.get("loop") or "") in retry_set and str(run.get("mode") or "") == "execute"
        for run in runs
    )


def _report_dir_for_ref(pack: ProjectPack, ref: str) -> Path:
    candidate = Path(ref).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    if candidate.is_file():
        if candidate.name in {"index.html", "run.json"} and (candidate.parent / "index.html").is_file():
            return candidate.parent
        raise FileNotFoundError(f"report path must be an index.html or run.json file: {ref}")
    if candidate.is_dir():
        if (candidate / "index.html").is_file():
            return candidate
        raise FileNotFoundError(f"report directory missing index.html: {ref}")
    return report_for_run(pack, ref).parent


def _latest_report_dir_for_loop(pack: ProjectPack, loop: str) -> Path:
    candidates = [
        report_dir for report_dir in [*_loop_report_dirs(pack), *_legacy_report_dirs(pack)]
        if _loop_name_from_raw(_read_json(report_dir / "run.json") or {}, report_dir) == loop
    ]
    if not candidates:
        raise FileNotFoundError(f"no run report found for loop: {loop}")
    return max(candidates, key=_report_sort_key)


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


def report_record_for_html(html_path: Path) -> dict[str, Any]:
    report_dir = html_path.parent
    batch_record = _read_json(report_dir / "batch.json")
    if isinstance(batch_record, dict):
        return {"kind": "batch", **batch_record}
    if (report_dir / "run.json").is_file():
        return {"kind": "run", **_run_summary_from_json(report_dir)}
    raise FileNotFoundError(f"JSON report data not found for: {html_path}")


def refresh_run_html(report_dir: Path) -> Path:
    raw = _read_json(report_dir / "run.json")
    if not isinstance(raw, dict):
        raise FileNotFoundError(f"run.json not found or invalid for report: {report_dir}")
    report = _run_report_from_raw(raw, report_dir)
    html_path = report_dir / "index.html"
    report_dir.joinpath("report.md").write_text(render_markdown_report(report), encoding="utf-8")
    html_path.write_text(render_html_report(report), encoding="utf-8")
    return html_path


def _loop_report_dirs(pack: ProjectPack) -> list[Path]:
    if not pack.loops_dir.is_dir():
        return []
    candidates = []
    for loop_dir in sorted(path for path in pack.loops_dir.iterdir() if path.is_dir()):
        for run_dir in sorted(path for path in loop_dir.iterdir() if path.is_dir() and not path.name.startswith("_")):
            if (run_dir / "index.html").is_file():
                candidates.append(run_dir)
    return candidates


def _legacy_report_dirs(pack: ProjectPack) -> list[Path]:
    if not pack.runs_dir.is_dir():
        return []
    return [
        path
        for path in sorted(child for child in pack.runs_dir.iterdir() if child.is_dir())
        if (path / "index.html").is_file()
    ]


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
    created_resources = extract_created_resources_from_steps(raw.get("steps") or [])
    if created_resources:
        summary["created_resources"] = created_resources
        summary["created_resource_count"] = len(created_resources)
    failed_items = extract_failed_items_from_steps(raw.get("steps") or [])
    if failed_items:
        summary["failed_items"] = failed_items
        summary["failed_item_count"] = len(failed_items)
    validation_issues = extract_validation_issues_from_steps(raw.get("steps") or [])
    if validation_issues:
        summary["validation_issues"] = validation_issues
        summary["validation_issue_count"] = len(validation_issues)
    attention_flags = extract_attention_flags_from_steps(raw.get("steps") or [])
    if attention_flags:
        summary["attention_flags"] = attention_flags
        summary["attention_count"] = len(attention_flags)
    evidence_files = _evidence_files_from_raw(raw)
    if evidence_files:
        summary["evidence_files"] = evidence_files
        summary["evidence_count"] = len(evidence_files)
    if isinstance(raw.get("evidence_warnings"), list):
        warnings = [str(item) for item in raw["evidence_warnings"] if item]
        if warnings:
            summary["evidence_warnings"] = warnings
    replay_status = _replay_status_from_raw(raw)
    if replay_status:
        summary["replay_status"] = replay_status
    replay_missing = _replay_missing_from_raw(raw)
    if replay_missing:
        summary["replay_missing"] = replay_missing
    replay_command = _replay_command_from_raw(raw, report_dir=report_dir, loop=loop)
    if replay_command:
        summary["replay_command"] = replay_command
    return summary


def _run_report_from_raw(raw: dict[str, Any], report_dir: Path) -> RunReport:
    return RunReport(
        run_id=str(raw.get("run_id") or report_dir.name),
        scenario_name=str(raw.get("scenario_name") or raw.get("name") or _loop_name_from_raw(raw, report_dir)),
        status=str(raw.get("status") or "blocked"),
        started_at=str(raw.get("started_at") or ""),
        finished_at=str(raw.get("finished_at") or ""),
        project_path=str(raw.get("project_path") or ""),
        artifact_dir=str(raw.get("artifact_dir") or report_dir),
        steps=_steps_from_raw(raw.get("steps") or [], raw),
        checks=_checks_from_raw(raw.get("checks") or []),
        html_report_path=str(report_dir / "index.html"),
        metadata=raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {},
        evidence=raw.get("evidence") if isinstance(raw.get("evidence"), list) else [],
        evidence_warnings=raw.get("evidence_warnings") if isinstance(raw.get("evidence_warnings"), list) else [],
        replay=raw.get("replay") if isinstance(raw.get("replay"), dict) else None,
        legacy_artifact_dir=str(raw.get("legacy_artifact_dir") or ""),
        updated_at=str(raw.get("updated_at") or ""),
        mode=_mode_from_raw(raw),
    )


def _steps_from_raw(values: Any, raw: dict[str, Any]) -> list[StepResult]:
    if not isinstance(values, list):
        return []
    steps: list[StepResult] = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            continue
        steps.append(StepResult(
            step_id=str(value.get("step_id") or value.get("id") or f"step_{index}"),
            status=str(value.get("status") or "blocked"),
            started_at=str(value.get("started_at") or raw.get("started_at") or ""),
            finished_at=str(value.get("finished_at") or raw.get("finished_at") or ""),
            exit_code=value.get("exit_code") if isinstance(value.get("exit_code"), int) else None,
            stdout=str(value.get("stdout") or ""),
            stderr=str(value.get("stderr") or ""),
            data=value.get("data") if isinstance(value.get("data"), dict) else {},
            artifacts=_artifacts_from_raw(value.get("artifacts") or []),
            checks=_checks_from_raw(value.get("checks") or []),
        ))
    return steps


def _checks_from_raw(values: Any) -> list[CheckResult]:
    if not isinstance(values, list):
        return []
    checks: list[CheckResult] = []
    for index, value in enumerate(values, start=1):
        if not isinstance(value, dict):
            continue
        checks.append(CheckResult(
            id=str(value.get("id") or f"check_{index}"),
            status=str(value.get("status") or "blocked"),
            message=str(value.get("message") or ""),
            details=value.get("details") if isinstance(value.get("details"), dict) else {},
        ))
    return checks


def _artifacts_from_raw(values: Any) -> list[Artifact]:
    if not isinstance(values, list):
        return []
    artifacts: list[Artifact] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        artifacts.append(Artifact(
            name=str(value.get("name") or ""),
            path=str(value.get("path") or ""),
            kind=str(value.get("kind") or "file"),
            metadata=value.get("metadata") if isinstance(value.get("metadata"), dict) else {},
        ))
    return artifacts


def _loop_name_from_raw(raw: dict[str, Any], report_dir: Path) -> str:
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    if metadata.get("loop_id") or raw.get("scenario_name") or raw.get("name"):
        return str(metadata.get("loop_id") or raw.get("scenario_name") or raw.get("name"))
    if report_dir.parent.parent.name == "loops":
        return report_dir.parent.name
    return report_dir.name


def _mode_from_raw(raw: dict[str, Any]) -> str:
    metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
    return str(raw.get("mode") or metadata.get("mode") or "")


def _current_step_from_raw(raw: dict[str, Any]) -> str:
    steps = raw.get("steps")
    if not isinstance(steps, list):
        return ""
    for step in reversed(steps):
        if not isinstance(step, dict):
            continue
        if step.get("status") == "running":
            return str(step.get("step_id") or "")
    return ""


def _evidence_files_from_raw(raw: dict[str, Any]) -> list[str]:
    replay = raw.get("replay") if isinstance(raw.get("replay"), dict) else {}
    inputs = replay.get("inputs") if isinstance(replay.get("inputs"), list) else []
    files = []
    for item in inputs:
        if not isinstance(item, dict):
            continue
        if item.get("source") == "evidence" and item.get("path"):
            files.append(str(item["path"]))
    return files


def _replay_status_from_raw(raw: dict[str, Any]) -> str:
    replay = raw.get("replay") if isinstance(raw.get("replay"), dict) else {}
    details = replay.get("replay") if isinstance(replay.get("replay"), dict) else {}
    return str(details.get("status") or "")


def _replay_missing_from_raw(raw: dict[str, Any]) -> list[str]:
    replay = raw.get("replay") if isinstance(raw.get("replay"), dict) else {}
    details = replay.get("replay") if isinstance(replay.get("replay"), dict) else {}
    missing = details.get("missing")
    if not isinstance(missing, list):
        return []
    return [str(item) for item in missing if item]


def _replay_command_from_raw(raw: dict[str, Any], *, report_dir: Path, loop: str) -> str:
    replay = raw.get("replay") if isinstance(raw.get("replay"), dict) else {}
    if not replay:
        return ""
    replay_path = report_dir / "replay.json"
    project_path = Path(str(raw.get("project_path"))) if raw.get("project_path") else None
    replay_arg = replay_path.as_posix()
    if project_path is not None:
        try:
            replay_arg = Path(os.path.relpath(replay_path, project_path)).as_posix()
        except (OSError, ValueError):
            pass
    source_run_id = str(replay.get("source_run_id") or raw.get("run_id") or report_dir.name)
    return shlex.join(["meguri", "run", loop, "--replay", replay_arg, "--retry-of", source_run_id])


def _failure_reasons_from_raw(raw: dict[str, Any]) -> list[str]:
    if raw.get("status") == "pass":
        return []
    json_reasons = extract_failure_reasons_from_steps(raw.get("steps") or [])
    fallback_reasons: list[str] = []
    for step in raw.get("steps") or []:
        if not isinstance(step, dict):
            continue
        for check in step.get("checks") or []:
            if not isinstance(check, dict):
                continue
            if check.get("status") not in {"pass", "warning"} and isinstance(check.get("message"), str):
                fallback_reasons.append(check["message"])
        stderr = step.get("stderr")
        if not fallback_reasons and isinstance(stderr, str) and stderr:
            fallback_reasons.append(_last_nonempty_line(stderr))
    return _dedupe_reasons(json_reasons or fallback_reasons)


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
