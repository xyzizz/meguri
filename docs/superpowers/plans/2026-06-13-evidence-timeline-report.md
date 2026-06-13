# Evidence Timeline Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build loop-local history folders, structured evidence parsing, attempt timeline HTML reports, loop index pages, and replay/retry commands.

**Architecture:** Keep Meguri local-first. Add focused evidence/replay modules under `meguri/core`, keep path discovery in `meguri/project/pack.py`, keep execution orchestration in `meguri/scenarios/runner.py`, and keep all static HTML generation in `meguri/reports`. Preserve legacy `.meguri/scenarios/*.yaml` and `.meguri/runs/<run_id>/` reads while making `.meguri/loops/<loop_id>/<YYYYMMDD_HHMMSS>/` the new default run location.

**Tech Stack:** Python 3.10+, dataclasses, pathlib, json, html, PyYAML, pytest.

---

## File Structure Map

- Create `meguri/core/evidence.py`: evidence dataclasses, JSON parser, project/run evidence collection, validation warnings, redaction helpers.
- Create `meguri/core/replay.py`: replay bundle builder, git metadata collection, replay status, retry metadata.
- Modify `meguri/core/models.py`: add `evidence`, `evidence_warnings`, `replay`, and `legacy_artifact_dir` fields to `RunReport`; keep additive compatibility.
- Modify `meguri/project/pack.py`: add `loops_dir`, loop definition path helpers, loop-local timestamp run directory helpers, and alias resolution for `.meguri/loops/<loop_id>/_loop.yaml`.
- Modify `meguri/cli/init.py`: create `.meguri/loops/smoke/_loop.yaml` while preserving legacy `.meguri/scenarios/smoke.yaml` compatibility for now.
- Modify `meguri/cli/add.py`: create new user loops at `.meguri/loops/<loop_id>/_loop.yaml`, with `_scripts/` directory reserved.
- Modify `meguri/cli/loops.py`: list/delete loops from both new loop folders and legacy scenarios; prefer new folders.
- Modify `meguri/cli/main.py`: add `run --replay` and `run --retry-of`; route default run output to loop-local timestamp directory.
- Modify `meguri/cli/report.py`: make `report --last` scan loop-local run folders and legacy run folders; allow `report <loop_id>/<run_id>` and unique `<run_id>`.
- Modify `meguri/scenarios/loader.py`: load `_loop.yaml` correctly with project path resolution relative to loop folder.
- Modify `meguri/scenarios/runner.py`: create run dir, set Meguri env vars, collect evidence, write replay bundle, render run detail and indexes.
- Modify `meguri/reports/html.py`: render attempt timeline when evidence exists, fallback to legacy step view, redact display text.
- Create `meguri/reports/indexes.py`: render `.meguri/index.html` and `.meguri/loops/<loop_id>/index.html`.
- Modify `meguri/cli/validate.py`: validate new loop folders and warn on evidence/replay issues without rejecting legacy packs.
- Add tests in `tests/test_evidence.py`, `tests/test_loop_history.py`, and update existing CLI/runner tests.

## Task 1: Evidence Parser and Redaction

**Files:**
- Create: `meguri/core/evidence.py`
- Test: `tests/test_evidence.py`

- [ ] **Step 1: Write failing evidence parser tests**

Create `tests/test_evidence.py`:

```python
from __future__ import annotations

from pathlib import Path

from meguri.core.evidence import collect_evidence, redact_value


def test_collect_evidence_orders_events_by_time_and_preserves_file_order_fallback(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "agent.json").write_text(
        """
{
  "version": 1,
  "run_id": "20260613_152717",
  "loop_id": "agent_loop",
  "attempts": [
    {
      "id": "attempt_1",
      "title": "Attempt 1",
      "status": "fail",
      "events": [
        {"id": "late", "type": "model_output", "time": "2026-06-13T15:27:25+08:00", "title": "Late", "status": "pass", "output": "late"},
        {"id": "early", "type": "user_input", "time": "2026-06-13T15:27:18+08:00", "title": "Early", "status": "pass", "input": "early"},
        {"id": "no_time", "type": "note", "title": "No time", "status": "warning", "output": "kept last"}
      ]
    }
  ]
}
""",
        encoding="utf-8",
    )

    result = collect_evidence(
        run_evidence_dir=evidence_dir,
        project_evidence_dir=tmp_path / "project-evidence",
        loop_id="agent_loop",
        run_id="20260613_152717",
        run_started_at=None,
        run_dir=tmp_path,
    )

    assert result.warnings == []
    assert len(result.bundles) == 1
    events = result.bundles[0].attempts[0].events
    assert [event.id for event in events] == ["early", "late", "no_time"]


def test_collect_evidence_warns_on_parse_error_without_raising(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    evidence_dir.mkdir()
    (evidence_dir / "broken.json").write_text("{", encoding="utf-8")

    result = collect_evidence(
        run_evidence_dir=evidence_dir,
        project_evidence_dir=tmp_path / "project-evidence",
        loop_id="agent_loop",
        run_id="20260613_152717",
        run_started_at=None,
        run_dir=tmp_path,
    )

    assert result.bundles == []
    assert "broken.json" in result.warnings[0]


def test_redact_value_hides_explicit_redacted_object_and_secret_patterns() -> None:
    assert redact_value({"text": "Bearer sk-live-secret", "redacted": True, "redacted_label": "LLM token"}) == "[redacted: LLM token]"
    assert "secret" not in redact_value("Authorization: Bearer sk-live-secret")
    assert "pass" not in redact_value("postgres://user:pass@example.com/db")
```

- [ ] **Step 2: Run evidence tests and verify failure**

Run:

```bash
pytest tests/test_evidence.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'meguri.core.evidence'`.

- [ ] **Step 3: Implement evidence dataclasses, parser, collector, and redaction**

Create `meguri/core/evidence.py`:

```python
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
    for path in sorted(run_evidence_dir.glob("*.json")):
        try:
            bundles.append(parse_evidence_file(path, run_dir=run_dir, warnings=warnings))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{path.name}: evidence parse failed: {type(exc).__name__}: {exc}")
    return EvidenceCollection(bundles=bundles, warnings=warnings)


def parse_evidence_file(path: Path, *, run_dir: Path, warnings: list[str] | None = None) -> EvidenceBundle:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("evidence root must be an object")
    loop_id = str(raw.get("loop_id") or "")
    run_id = str(raw["run_id"]) if raw.get("run_id") is not None else None
    attempts = [_parse_attempt(item, run_dir=run_dir, warnings=warnings or []) for item in list(raw.get("attempts") or [])]
    return EvidenceBundle(source_file=str(path), loop_id=loop_id, run_id=run_id, attempts=attempts)


def _parse_attempt(raw: Any, *, run_dir: Path, warnings: list[str]) -> EvidenceAttempt:
    if not isinstance(raw, dict):
        raise ValueError("attempt must be an object")
    attempt_id = str(raw.get("id") or "attempt")
    events = [_parse_event(item, index, run_dir=run_dir, warnings=warnings) for index, item in enumerate(list(raw.get("events") or []))]
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
    artifacts = [_parse_artifact(item, run_dir=run_dir, warnings=warnings) for item in list(raw.get("artifacts") or [])]
    checks = [_parse_check(item) for item in list(raw.get("checks") or [])]
    return EvidenceEvent(
        id=event_id,
        type=event_type,
        title=str(raw.get("title") or event_id),
        status=str(raw.get("status") or "warning"),
        time=str(raw["time"]) if raw.get("time") is not None else None,
        input=raw.get("input"),
        output=raw.get("output"),
        checks=checks,
        artifacts=artifacts,
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
    for path in sorted(project_evidence_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{path.name}: project evidence skipped: {type(exc).__name__}: {exc}")
            continue
        if not isinstance(raw, dict) or str(raw.get("loop_id") or "") != loop_id:
            continue
        declares_run = raw.get("run_id") == run_id
        modified_after_start = run_started_at is None or datetime.fromtimestamp(path.stat().st_mtime, tz=run_started_at.tzinfo) >= run_started_at
        if declares_run or modified_after_start:
            shutil.copy2(path, run_evidence_dir / path.name)
        else:
            warnings.append(f"{path.name}: skipped stale project evidence for loop {loop_id}")


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


def redact_value(value: Any) -> str:
    if isinstance(value, dict) and value.get("redacted"):
        label = str(value.get("redacted_label") or "value")
        return f"[redacted: {label}]"
    if value is None:
        return ""
    if not isinstance(value, str):
        text = json.dumps(value, ensure_ascii=False, indent=2, default=str)
    else:
        text = value
    patterns = [
        (re.compile(r"Authorization:\\s*Bearer\\s+\\S+", re.IGNORECASE), "Authorization: Bearer [redacted]"),
        (re.compile(r"Bearer\\s+[A-Za-z0-9._\\-]{8,}", re.IGNORECASE), "Bearer [redacted]"),
        (re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd)(['\\\"]?\\s*[:=]\\s*['\\\"]?)[^\\s'\\\",}]+"), r"\\1\\2[redacted]"),
        (re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://[^:/\\s]+:)[^@\\s]+(@)"), r"\\1[redacted]\\2"),
        (re.compile(r"Cookie:\\s*[^\\n]+", re.IGNORECASE), "Cookie: [redacted]"),
    ]
    for pattern, replacement in patterns:
        text = pattern.sub(replacement, text)
    return text
```

- [ ] **Step 4: Run evidence tests and verify pass**

Run:

```bash
pytest tests/test_evidence.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add meguri/core/evidence.py tests/test_evidence.py
git commit -m "Add evidence parsing and redaction"
```

## Task 2: Loop-First Path Helpers

**Files:**
- Modify: `meguri/project/pack.py`
- Test: `tests/test_loop_history.py`

- [ ] **Step 1: Write failing path helper tests**

Create `tests/test_loop_history.py`:

```python
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
    loop_file.write_text("name: checkout\\nadapter: shell\\nproject_path: ../../..\\nsteps: []\\n", encoding="utf-8")

    assert resolve_scenario("checkout") == loop_file.resolve()
```

- [ ] **Step 2: Run path tests and verify failure**

Run:

```bash
pytest tests/test_loop_history.py -q
```

Expected: FAIL because `loop_definition_path` and `loop_run_dir` do not exist.

- [ ] **Step 3: Add loop path helpers and alias resolution**

Modify `meguri/project/pack.py`:

```python
LOOPS_DIR_NAME = "loops"
LOOP_FILE_NAME = "_loop.yaml"
```

Add to `ProjectPack`:

```python
    @property
    def loops_dir(self) -> Path:
        return self.pack_root / LOOPS_DIR_NAME

    def loop_dir(self, loop_id: str) -> Path:
        return self.loops_dir / slugify(loop_id)

    def loop_definition_path(self, loop_id: str) -> Path:
        return self.loop_dir(loop_id) / LOOP_FILE_NAME

    def loop_run_dir(self, loop_id: str, run_id: str) -> Path:
        return self.loop_dir(loop_id) / run_id
```

Update `resolve_scenario` before legacy scenario lookup:

```python
    loop_candidate = pack.loop_definition_path(raw.name)
    if loop_candidate.exists():
        return loop_candidate.resolve()
```

- [ ] **Step 4: Run path tests and existing pack tests**

Run:

```bash
pytest tests/test_loop_history.py tests/test_cli_commands.py::test_run_alias_writes_project_local_html_report -q
```

Expected: `tests/test_loop_history.py` PASS. Existing run test may still PASS with legacy paths until Task 4 changes the default.

- [ ] **Step 5: Commit**

```bash
git add meguri/project/pack.py tests/test_loop_history.py
git commit -m "Add loop-first path helpers"
```

## Task 3: Init, Add, List, and Delete Loop Folders

**Files:**
- Modify: `meguri/cli/init.py`
- Modify: `meguri/cli/add.py`
- Modify: `meguri/cli/loops.py`
- Modify: `tests/test_cli_commands.py`

- [ ] **Step 1: Update failing CLI tests for loop folders**

Update `tests/test_cli_commands.py` expectations:

```python
assert (tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml").is_file()
smoke = yaml.safe_load((tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml").read_text(encoding="utf-8"))
```

Update add test:

```python
scenario_path = tmp_path / ".meguri" / "loops" / "login_flow" / "_loop.yaml"
```

Update delete test:

```python
assert not (tmp_path / ".meguri" / "loops" / "checkout").exists()
```

Keep one compatibility assertion:

```python
assert (tmp_path / ".meguri" / "scenarios" / "smoke.yaml").is_file()
```

- [ ] **Step 2: Run CLI tests and verify failure**

Run:

```bash
pytest tests/test_cli_commands.py::test_init_creates_project_pack_and_skills tests/test_cli_commands.py::test_add_writes_valid_scenario_when_required_fields_are_supplied tests/test_cli_commands.py::test_loops_lists_user_added_loops_and_delete_removes_named_loop -q
```

Expected: FAIL because commands still write only `.meguri/scenarios`.

- [ ] **Step 3: Update init to write new smoke loop plus legacy copy**

Modify `meguri/cli/init.py` so generated files include:

```python
pack.loop_definition_path("smoke"): yaml.safe_dump(smoke_data, sort_keys=False, allow_unicode=True)
pack.scenarios_dir / "smoke.yaml": yaml.safe_dump(smoke_data, sort_keys=False, allow_unicode=True)
pack.loop_dir("smoke") / "_scripts" / ".gitkeep": ""
```

Keep preservation behavior: do not overwrite either file unless `--force`.

- [ ] **Step 4: Update add to write loop folder**

Modify `meguri/cli/add.py`:

```python
loop_dir = pack.loop_dir(loop_id)
scenario_path = loop_dir / "_loop.yaml"
scripts_dir = loop_dir / "_scripts"
```

Create `scripts_dir` and write the YAML to `_loop.yaml`. Do not also create a legacy scenario for user-added loops.

- [ ] **Step 5: Update loops/delete to read both layouts**

Modify `meguri/cli/loops.py`:

```python
def _read_loops(pack: ProjectPack) -> list[LoopEntry]:
    entries = []
    entries.extend(_read_loop_folders(pack.loops_dir))
    legacy = _read_legacy_scenarios(pack.scenarios_dir, existing_ids={entry.loop_id for entry in entries})
    entries.extend(legacy)
    return entries
```

For delete, if the entry is a loop folder, remove only that loop folder after source checks. Legacy scenario delete remains file unlink.

- [ ] **Step 6: Run CLI loop management tests**

Run:

```bash
pytest tests/test_cli_commands.py::test_init_creates_project_pack_and_skills tests/test_cli_commands.py::test_add_writes_valid_scenario_when_required_fields_are_supplied tests/test_cli_commands.py::test_loops_lists_user_added_loops_and_delete_removes_named_loop tests/test_cli_commands.py::test_delete_refuses_system_loop_without_force -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add meguri/cli/init.py meguri/cli/add.py meguri/cli/loops.py tests/test_cli_commands.py
git commit -m "Store loops in loop folders"
```

## Task 4: Loop-Local Run Directories and Replay Bundle

**Files:**
- Create: `meguri/core/replay.py`
- Modify: `meguri/core/models.py`
- Modify: `meguri/adapters/shell.py`
- Modify: `meguri/adapters/dapper_assistant.py`
- Modify: `meguri/scenarios/runner.py`
- Modify: `meguri/cli/main.py`
- Test: `tests/test_runner.py`
- Test: `tests/test_cli_commands.py`

- [ ] **Step 1: Write failing runner tests**

Append to `tests/test_runner.py`:

```python
import json


def test_runner_uses_loop_local_timestamp_directory_and_writes_replay(tmp_path: Path) -> None:
    loop_file = tmp_path / ".meguri" / "loops" / "shell_smoke" / "_loop.yaml"
    loop_file.parent.mkdir(parents=True)
    loop_file.write_text(
        f"""
name: shell_smoke
adapter: shell
project_path: "../../.."
mode: dry_run
metadata:
  kind: loop
  loop_id: shell_smoke
steps:
  - id: emit_env
    command:
      - "{sys.executable}"
      - "-c"
      - "import os; print(os.environ['MEGURI_LOOP_ID']); print(os.environ['MEGURI_RUN_DIR'])"
    checks:
      - id: exit
        type: exit_code
        equals: 0
""",
        encoding="utf-8",
    )

    report = run_scenario(loop_file, runs_dir=None)
    artifact_dir = Path(report.artifact_dir)

    assert artifact_dir.parent == loop_file.parent
    assert artifact_dir.name[:8].isdigit()
    assert (artifact_dir / "replay.json").is_file()
    replay = json.loads((artifact_dir / "replay.json").read_text(encoding="utf-8"))
    assert replay["loop_id"] == "shell_smoke"
    assert replay["scenario_path"] == str(loop_file)
```

- [ ] **Step 2: Run runner test and verify failure**

Run:

```bash
pytest tests/test_runner.py::test_runner_uses_loop_local_timestamp_directory_and_writes_replay -q
```

Expected: FAIL because `run_scenario` requires `runs_dir` and writes legacy run ids.

- [ ] **Step 3: Add replay bundle builder**

Create `meguri/core/replay.py`:

```python
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def build_replay_bundle(
    *,
    source_run_id: str,
    loop_id: str,
    scenario_path: Path,
    command: list[str] | None,
    evidence_files: list[Path],
    replay_source: str | None = None,
    retry_of: str | None = None,
) -> dict[str, Any]:
    return {
        "version": 1,
        "source_run_id": source_run_id,
        "loop_id": loop_id,
        "scenario_path": str(scenario_path),
        "command": command or [],
        "project_ref": _project_ref(scenario_path),
        "inputs": [{"source": "evidence", "path": str(path.as_posix())} for path in evidence_files],
        "environment": {"redacted_env": _redacted_env_names()},
        "replay": {"status": "full" if evidence_files else "none", "missing": [] if evidence_files else ["structured evidence"]},
        "replay_source": replay_source,
        "retry_of": retry_of,
    }


def _project_ref(path: Path) -> dict[str, Any]:
    cwd = path.parent
    commit = _git(cwd, ["rev-parse", "--short", "HEAD"])
    dirty = bool(_git(cwd, ["status", "--short"]))
    return {"git_commit": commit or None, "dirty": dirty}


def _git(cwd: Path, args: list[str]) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=str(cwd), text=True, capture_output=True, check=False)
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _redacted_env_names() -> list[str]:
    return ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DATABASE_URL", "REDIS_URL", "TOKEN", "SECRET"]
```

- [ ] **Step 4: Extend RunReport model**

Modify `meguri/core/models.py`:

```python
    evidence: list[Any] = field(default_factory=list)
    evidence_warnings: list[str] = field(default_factory=list)
    replay: dict[str, Any] | None = None
    legacy_artifact_dir: str = ""
```

- [ ] **Step 5: Set Meguri env vars in adapters**

In both shell and dapper adapters, after `env.update(ctx.env)`, ensure `ctx.env` can carry:

```python
"MEGURI_RUN_ID": ctx.run_id,
"MEGURI_LOOP_ID": str(ctx.metadata.get("loop_id") or ctx.metadata.get("scenario_name") or ""),
"MEGURI_RUN_DIR": str(ctx.artifact_dir),
"MEGURI_ARTIFACT_DIR": str(ctx.artifact_dir),
"MEGURI_EVIDENCE_DIR": str(ctx.artifact_dir / "evidence"),
```

Prefer setting these once in `RunContext.env` from the runner.

- [ ] **Step 6: Update runner signature and directory selection**

Modify `meguri/scenarios/runner.py`:

```python
def run_scenario(
    scenario_path: Path,
    *,
    runs_dir: Path | None = None,
    replay_file: Path | None = None,
    retry_of: str | None = None,
) -> RunReport:
```

Determine loop id:

```python
loop_id = str(scenario.metadata.get("loop_id") or scenario.name)
run_id = timestamp_run_id()
artifact_dir = (runs_dir / run_id) if runs_dir else default_run_dir_for_scenario(scenario_path, loop_id=loop_id, run_id=run_id)
```

Set `ctx.env` with Meguri env vars. After steps, collect evidence, build replay, write `replay.json`, then write reports.

- [ ] **Step 7: Add CLI flags**

Modify `meguri/cli/main.py`:

```python
run.add_argument("--replay")
run.add_argument("--retry-of")
```

Call:

```python
run_report = run_scenario(
    scenario_path,
    runs_dir=runs_dir,
    replay_file=Path(args.replay).expanduser().resolve() if args.replay else None,
    retry_of=args.retry_of,
)
```

- [ ] **Step 8: Run runner and CLI tests**

Run:

```bash
pytest tests/test_runner.py tests/test_cli_commands.py::test_run_alias_writes_project_local_html_report -q
```

Expected: PASS after updating the CLI test to assert:

```python
assert ".meguri/loops/smoke/" in str(html_path)
assert (html_path.parent / "replay.json").is_file()
```

- [ ] **Step 9: Commit**

```bash
git add meguri/core/models.py meguri/core/replay.py meguri/adapters/shell.py meguri/adapters/dapper_assistant.py meguri/scenarios/runner.py meguri/cli/main.py tests/test_runner.py tests/test_cli_commands.py
git commit -m "Write loop-local run records and replay bundles"
```

## Task 5: Attempt Timeline HTML

**Files:**
- Modify: `meguri/reports/html.py`
- Test: `tests/test_evidence.py`

- [ ] **Step 1: Add failing HTML timeline test**

Append to `tests/test_evidence.py`:

```python
from meguri.core.models import RunReport, utc_now
from meguri.reports.html import render_html_report


def test_html_report_renders_evidence_timeline_and_detail_panel(tmp_path: Path) -> None:
    now = utc_now()
    report = RunReport(
        run_id="20260613_152717",
        scenario_name="agent_loop",
        status="pass",
        started_at=now,
        finished_at=now,
        project_path=str(tmp_path),
        artifact_dir=str(tmp_path),
        steps=[],
        checks=[],
        evidence=[
            {
                "loop_id": "agent_loop",
                "attempts": [
                    {
                        "id": "attempt_1",
                        "title": "Attempt 1",
                        "status": "pass",
                        "events": [
                            {
                                "id": "user_1",
                                "type": "user_input",
                                "title": "User input",
                                "status": "pass",
                                "input": "hello",
                                "output": None,
                                "checks": [],
                                "artifacts": [],
                            }
                        ],
                    }
                ],
            }
        ],
    )

    html = render_html_report(report)

    assert "Attempt Timeline" in html
    assert "detail-panel" in html
    assert "User input" in html
    assert "hello" in html
```

- [ ] **Step 2: Run HTML test and verify failure**

Run:

```bash
pytest tests/test_evidence.py::test_html_report_renders_evidence_timeline_and_detail_panel -q
```

Expected: FAIL because current report does not render evidence timeline.

- [ ] **Step 3: Implement evidence-first HTML rendering**

Modify `meguri/reports/html.py`:

- Add `_render_evidence_timeline(report)`.
- Add `_normalise_evidence(report.evidence)` to support dataclasses and dicts.
- Add inline JS that updates the detail panel on click.
- Add `redact_value()` calls before placing input/output.
- Keep existing `_render_step()` fallback.

The detail panel must render:

```html
<aside class="detail-panel" id="detail-panel">
  <h2 id="detail-title">Select an event</h2>
  <dl id="detail-meta"></dl>
  <section><h3>Input</h3><pre id="detail-input"></pre></section>
  <section><h3>Output</h3><pre id="detail-output"></pre></section>
  <section id="detail-checks"></section>
  <section id="detail-artifacts"></section>
</aside>
```

- [ ] **Step 4: Run HTML tests**

Run:

```bash
pytest tests/test_evidence.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add meguri/reports/html.py tests/test_evidence.py
git commit -m "Render evidence timelines in HTML reports"
```

## Task 6: Project and Loop Index Pages

**Files:**
- Create: `meguri/reports/indexes.py`
- Modify: `meguri/scenarios/runner.py`
- Modify: `meguri/cli/report.py`
- Test: `tests/test_loop_history.py`
- Test: `tests/test_cli_commands.py`

- [ ] **Step 1: Add failing index tests**

Append to `tests/test_loop_history.py`:

```python
from meguri.reports.indexes import render_project_index, render_loop_index


def test_render_loop_and_project_indexes_link_to_run_reports(tmp_path: Path) -> None:
    loop_dir = tmp_path / ".meguri" / "loops" / "checkout"
    run_dir = loop_dir / "20260613_152717"
    run_dir.mkdir(parents=True)
    (run_dir / "run.json").write_text('{"run_id":"20260613_152717","status":"pass","finished_at":"2026-06-13T15:27:20+00:00","artifact_dir":"' + str(run_dir) + '"}', encoding="utf-8")
    (run_dir / "index.html").write_text("<html>detail</html>", encoding="utf-8")

    loop_html = render_loop_index(loop_dir)
    project_html = render_project_index(tmp_path / ".meguri")

    assert "20260613_152717" in loop_html
    assert "20260613_152717/index.html" in loop_html
    assert "checkout" in project_html
    assert "loops/checkout/index.html" in project_html
```

- [ ] **Step 2: Run index test and verify failure**

Run:

```bash
pytest tests/test_loop_history.py::test_render_loop_and_project_indexes_link_to_run_reports -q
```

Expected: FAIL because `meguri.reports.indexes` does not exist.

- [ ] **Step 3: Implement index renderers**

Create `meguri/reports/indexes.py`:

```python
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


def render_project_index(pack_root: Path) -> str:
    rows = []
    loops_dir = pack_root / "loops"
    for loop_dir in sorted([path for path in loops_dir.iterdir() if path.is_dir()]) if loops_dir.is_dir() else []:
        runs = _run_records(loop_dir)
        latest = runs[0] if runs else {}
        rows.append(
            "<tr>"
            f"<td><a href=\"loops/{html.escape(loop_dir.name)}/index.html\">{html.escape(loop_dir.name)}</a></td>"
            f"<td>{len(runs)}</td>"
            f"<td>{html.escape(str(latest.get('status') or '-'))}</td>"
            f"<td>{html.escape(str(latest.get('run_id') or '-'))}</td>"
            "</tr>"
        )
    return _page("Meguri Loops", "<table><thead><tr><th>Loop</th><th>Runs</th><th>Latest status</th><th>Latest run</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


def render_loop_index(loop_dir: Path) -> str:
    rows = []
    for record in _run_records(loop_dir):
        run_id = str(record.get("run_id") or "")
        rows.append(
            "<tr>"
            f"<td>{html.escape(run_id)}</td>"
            f"<td>{html.escape(str(record.get('status') or '-'))}</td>"
            f"<td>{html.escape(str((record.get('replay') or {}).get('replay', {}).get('status') or '-'))}</td>"
            f"<td><a href=\"{html.escape(run_id)}/index.html\">Open</a></td>"
            "</tr>"
        )
    return _page(f"Loop {loop_dir.name}", "<table><thead><tr><th>Run time</th><th>Status</th><th>Replay</th><th>Links</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>")


def write_indexes(pack_root: Path, loop_dir: Path) -> None:
    loop_dir.joinpath("index.html").write_text(render_loop_index(loop_dir), encoding="utf-8")
    pack_root.joinpath("index.html").write_text(render_project_index(pack_root), encoding="utf-8")


def _run_records(loop_dir: Path) -> list[dict[str, Any]]:
    records = []
    for child in sorted([path for path in loop_dir.iterdir() if path.is_dir() and not path.name.startswith("_")], reverse=True):
        run_json = child / "run.json"
        if not run_json.is_file():
            continue
        try:
            raw = json.loads(run_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        records.append(raw)
    return records


def _page(title: str, body: str) -> str:
    return f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"><title>{html.escape(title)}</title><style>body{{font:14px/1.5 system-ui,sans-serif;margin:32px;color:#1d2430}}table{{border-collapse:collapse;width:100%}}th,td{{border-bottom:1px solid #ddd;padding:8px;text-align:left}}a{{color:#8a3b12}}</style></head><body><main><h1>{html.escape(title)}</h1>{body}</main></body></html>"
```

- [ ] **Step 4: Call index writer from runner**

After writing run `index.html`, call:

```python
write_indexes(pack.pack_root, artifact_dir.parent)
```

Only do this for loop-local run directories under `.meguri/loops`.

- [ ] **Step 5: Update report command to scan loop history**

Modify `meguri/cli/report.py`:

- `latest_report(pack)` scans `.meguri/loops/*/<timestamp>/index.html`, newest by mtime, then legacy `pack.runs_dir`.
- `report_for_run(pack, run_id)` accepts `loop_id/run_id` or unique run id.

- [ ] **Step 6: Run report and index tests**

Run:

```bash
pytest tests/test_loop_history.py tests/test_cli_commands.py::test_report_last_selects_newest_html_report -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add meguri/reports/indexes.py meguri/scenarios/runner.py meguri/cli/report.py tests/test_loop_history.py tests/test_cli_commands.py
git commit -m "Add loop history index pages"
```

## Task 7: Validate New Layout and Compatibility

**Files:**
- Modify: `meguri/cli/validate.py`
- Modify: `tests/test_cli_commands.py`

- [ ] **Step 1: Add failing validation checks**

Update `test_validate_accepts_generated_pack_and_rejects_unknown_adapter` to mutate new loop file:

```python
scenario_path = tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml"
```

Add assertion that `validate` accepts new layout:

```python
assert (tmp_path / ".meguri" / "loops" / "smoke" / "_loop.yaml").is_file()
```

- [ ] **Step 2: Run validate test and verify failure if needed**

Run:

```bash
pytest tests/test_cli_commands.py::test_validate_accepts_generated_pack_and_rejects_unknown_adapter -q
```

Expected: FAIL until validate scans loop folders.

- [ ] **Step 3: Update validate scanning**

Modify `meguri/cli/validate.py`:

```python
for loop_file in sorted(pack.loops_dir.glob("*/_loop.yaml")):
    _validate_scenario_path(loop_file, errors, warnings)
```

Keep legacy scenario scanning, but avoid duplicate warnings when both legacy and new smoke exist.

Add warning if `.meguri/loops` missing:

```python
warnings.append("loops directory is not present yet; legacy scenarios remain supported")
```

- [ ] **Step 4: Run validation tests**

Run:

```bash
pytest tests/test_cli_commands.py::test_validate_accepts_generated_pack_and_rejects_unknown_adapter -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add meguri/cli/validate.py tests/test_cli_commands.py
git commit -m "Validate loop folder layout"
```

## Task 8: Full Regression and Documentation Touch-Ups

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/superpowers/specs/2026-06-13-evidence-timeline-report-design.md`
- Modify: `docs/superpowers/specs/2026-06-13-evidence-timeline-report-design.zh-CN.md`

- [ ] **Step 1: Update README loop storage notes**

Replace language saying `.meguri/scenarios/*.yaml` is the main loop storage with:

```markdown
New Meguri loops live under `.meguri/loops/<loop_id>/_loop.yaml`.
Each run creates `.meguri/loops/<loop_id>/<YYYYMMDD_HHMMSS>/` with
`run.json`, `report.md`, `index.html`, `replay.json`, and `evidence/`.
Legacy `.meguri/scenarios/*.yaml` files remain readable.
```

Use the equivalent Chinese text in `README.zh-CN.md`.

- [ ] **Step 2: Run full tests**

Run:

```bash
pytest -q
```

Expected: all tests PASS.

- [ ] **Step 3: Run compile check**

Run:

```bash
python3 -m compileall meguri
```

Expected: all files compile successfully.

- [ ] **Step 4: Run shell syntax check**

Run:

```bash
bash -n install.sh
```

Expected: no output and exit code 0.

- [ ] **Step 5: Commit docs and final test updates**

```bash
git add README.md README.zh-CN.md docs/superpowers/specs/2026-06-13-evidence-timeline-report-design.md docs/superpowers/specs/2026-06-13-evidence-timeline-report-design.zh-CN.md
git commit -m "Document loop history report layout"
```

## Self-Review

- Spec coverage: Evidence files, attempt timelines, redaction, loop replay, retry, loop-first file structure, project index, loop index, fallback behavior, validation, and tests all map to tasks.
- Completion-language scan: No task contains unfinished filler language. Each code-changing step names concrete files and code shape.
- Type consistency: `EvidenceBundle`, `EvidenceAttempt`, `EvidenceEvent`, `ReplayBundle`, `RunReport.evidence`, `RunReport.evidence_warnings`, and `RunReport.replay` are used consistently across tasks.
- Scope: This is one cohesive feature. Live report streaming is intentionally out of scope.
