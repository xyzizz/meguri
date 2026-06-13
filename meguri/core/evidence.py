from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from meguri.core.models import CheckResult, Status


KNOWN_EVENT_TYPES = {"user_input", "model_output", "tool_call", "check", "repair", "rerun", "artifact", "note"}


@dataclass
class EvidenceArtifact:
    label: str
    path: str
    kind: str = "file"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EvidenceEvent:
    id: str
    type: str
    title: str
    status: Status | str = "warning"
    time: str | None = None
    input: Any = None
    output: Any = None
    checks: list[CheckResult] = field(default_factory=list)
    artifacts: list[EvidenceArtifact] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    order: int = 0


@dataclass
class EvidenceAttempt:
    id: str
    title: str
    status: Status | str
    events: list[EvidenceEvent] = field(default_factory=list)


@dataclass
class EvidenceBundle:
    source_file: str
    loop_id: str
    run_id: str | None
    attempts: list[EvidenceAttempt] = field(default_factory=list)


@dataclass
class EvidenceCollection:
    bundles: list[EvidenceBundle] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def collect_evidence(
    *,
    run_evidence_dir: Path,
    project_evidence_dir: Path,
    loop_id: str,
    run_id: str,
    run_started_at: datetime | None,
    run_dir: Path,
) -> EvidenceCollection:
    run_evidence_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    _copy_project_evidence(
        project_evidence_dir=project_evidence_dir,
        run_evidence_dir=run_evidence_dir,
        loop_id=loop_id,
        run_id=run_id,
        run_started_at=run_started_at,
        warnings=warnings,
    )
    bundles: list[EvidenceBundle] = []
    for path in sorted(run_evidence_dir.rglob("*.json")):
        try:
            bundles.append(parse_evidence_file(path, run_dir=run_dir, warnings=warnings))
        except Exception as exc:  # noqa: BLE001
            name = _display_evidence_path(run_evidence_dir, path)
            warnings.append(f"{name}: evidence parse failed: {type(exc).__name__}: {exc}")
    return EvidenceCollection(bundles=bundles, warnings=warnings)


def parse_evidence_file(path: Path, *, run_dir: Path, warnings: list[str] | None = None) -> EvidenceBundle:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("evidence root must be an object")
    attempt_warnings = warnings if warnings is not None else []
    attempts = [
        _parse_attempt(item, run_dir=run_dir, warnings=attempt_warnings)
        for item in list(raw.get("attempts") or [])
    ]
    return EvidenceBundle(
        source_file=str(path),
        loop_id=str(raw.get("loop_id") or ""),
        run_id=str(raw["run_id"]) if raw.get("run_id") is not None else None,
        attempts=attempts,
    )


def redact_value(value: Any) -> str:
    if isinstance(value, dict) and value.get("redacted"):
        label = str(value.get("redacted_label") or "value")
        return f"[redacted: {label}]"
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    patterns = [
        (re.compile(r"Authorization:\s*Bearer\s+\S+", re.IGNORECASE), "Authorization: Bearer [redacted]"),
        (re.compile(r"Bearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE), "Bearer [redacted]"),
        (re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd)(['\"]?\s*[:=]\s*['\"]?)[^\s'\",}]+"), r"\1\2[redacted]"),
        (re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://[^:/\s]+:)[^@\s]+(@)"), r"\1[redacted]\2"),
        (re.compile(r"Cookie:\s*[^\n]+", re.IGNORECASE), "Cookie: [redacted]"),
    ]
    for pattern, replacement in patterns:
        text = pattern.sub(replacement, text)
    return text


def _parse_attempt(raw: Any, *, run_dir: Path, warnings: list[str]) -> EvidenceAttempt:
    if not isinstance(raw, dict):
        raise ValueError("attempt must be an object")
    attempt_id = str(raw.get("id") or "attempt")
    events = [
        _parse_event(item, index, run_dir=run_dir, warnings=warnings)
        for index, item in enumerate(list(raw.get("events") or []))
    ]
    events.sort(key=_event_sort_key)
    return EvidenceAttempt(
        id=attempt_id,
        title=str(raw.get("title") or attempt_id),
        status=str(raw.get("status") or _status_from_events(events)),
        events=events,
    )


def _parse_event(raw: Any, order: int, *, run_dir: Path, warnings: list[str]) -> EvidenceEvent:
    if not isinstance(raw, dict):
        raise ValueError("event must be an object")
    event_id = str(raw.get("id") or f"event_{order + 1}")
    event_type = str(raw.get("type") or "note")
    if event_type not in KNOWN_EVENT_TYPES:
        warnings.append(f"{event_id}: unknown event type {event_type!r}; rendered as note")
        event_type = "note"
    return EvidenceEvent(
        id=event_id,
        type=event_type,
        title=str(raw.get("title") or event_id),
        status=str(raw.get("status") or "warning"),
        time=str(raw["time"]) if raw.get("time") is not None else None,
        input=raw.get("input"),
        output=raw.get("output"),
        checks=[_parse_check(item) for item in list(raw.get("checks") or [])],
        artifacts=[_parse_artifact(item, run_dir=run_dir, warnings=warnings) for item in list(raw.get("artifacts") or [])],
        metadata=dict(raw.get("metadata") or {}),
        order=order,
    )


def _parse_check(raw: Any) -> CheckResult:
    if not isinstance(raw, dict):
        return CheckResult(id="check", status="blocked", message="invalid check entry")
    return CheckResult(
        id=str(raw.get("id") or "check"),
        status=str(raw.get("status") or "blocked"),  # type: ignore[arg-type]
        message=str(raw.get("message") or ""),
        details=dict(raw.get("details") or {}),
    )


def _parse_artifact(raw: Any, *, run_dir: Path, warnings: list[str]) -> EvidenceArtifact:
    if not isinstance(raw, dict):
        return EvidenceArtifact(label="artifact", path=str(raw))
    path = str(raw.get("path") or "")
    if path and not (run_dir / path).exists():
        warnings.append(f"missing evidence artifact: {path}")
    return EvidenceArtifact(
        label=str(raw.get("label") or path or "artifact"),
        path=path,
        kind=str(raw.get("kind") or "file"),
        metadata=dict(raw.get("metadata") or {}),
    )


def _copy_project_evidence(
    *,
    project_evidence_dir: Path,
    run_evidence_dir: Path,
    loop_id: str,
    run_id: str,
    run_started_at: datetime | None,
    warnings: list[str],
) -> None:
    if not project_evidence_dir.is_dir():
        return
    for path in sorted(project_evidence_dir.rglob("*.json")):
        relative_path = path.relative_to(project_evidence_dir)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{relative_path.as_posix()}: project evidence skipped: {type(exc).__name__}: {exc}")
            continue
        if not isinstance(raw, dict) or str(raw.get("loop_id") or "") != loop_id:
            continue
        declares_run = raw.get("run_id") == run_id
        modified_after_start = (
            run_started_at is None
            or datetime.fromtimestamp(path.stat().st_mtime, tz=run_started_at.tzinfo) >= run_started_at
        )
        if declares_run or modified_after_start:
            destination = run_evidence_dir / relative_path
            if path.resolve() == destination.resolve():
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        else:
            warnings.append(f"{relative_path.as_posix()}: skipped stale project evidence for loop {loop_id}")


def _display_evidence_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.name


def _event_sort_key(event: EvidenceEvent) -> tuple[int, str, int]:
    if event.time:
        return (0, event.time, event.order)
    return (1, "", event.order)


def _status_from_events(events: list[EvidenceEvent]) -> str:
    statuses = [str(event.status) for event in events]
    if "fail" in statuses:
        return "fail"
    if "blocked" in statuses:
        return "blocked"
    if "warning" in statuses:
        return "warning"
    return "pass"
