# Meguri Simplified Workflow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/meguri` the primary user-facing workflow and hard-reduce the public CLI to `init`, `run`, and `report`.

**Architecture:** Keep the runner, evidence, replay, and report rendering capabilities intact. Move skill/prompt entrypoint refresh into a focused module, make `init` call that module before writing project pack files, make `run` own validation and multi-loop batch creation, and make `report` a read-only report resolver. Loop add/list/delete remains possible through the agent workflow by editing `.meguri/loops`, not through public CLI commands.

**Tech Stack:** Python 3.10+, argparse, pathlib, urllib.request, PyYAML, pytest.

---

## File Structure Map

- Create `meguri/cli/entrypoints.py`: owns bundled Meguri entrypoint templates, remote template fetch, validation, and writing `.agents`, `.claude`, and Codex prompt files.
- Create `meguri/templates/codex_skill.md`, `meguri/templates/claude_skill.md`, `meguri/templates/claude_command.md`, and `meguri/templates/codex_prompt.md`: official raw files fetched by `meguri init` from the Meguri repository.
- Modify `meguri/cli/init.py`: call entrypoint refresh first, add offline mode, keep pack/inspect generation, and preserve user loop/run/evidence files.
- Modify `meguri/cli/main.py`: expose only `init`, `run`, and `report`; support `meguri run all`; remove public loop-management and manual batch/report-builder commands.
- Modify `meguri/cli/validate.py`: keep validation as an internal service used by `run`, while removing the public command.
- Modify `meguri/cli/report.py`: make `report` read-only; resolve latest, run id, or batch id; remove manual batch creation and refresh entry points.
- Modify `meguri/cli/upgrade.py`, `meguri/cli/add.py`, `meguri/cli/loops.py`, `meguri/cli/inspect.py`: stop importing these from the public CLI. Leave files in place only if tests or future internal agent workflows still import them.
- Modify `README.md`, `README.zh-CN.md`, `prompts/install.md`: explain `/meguri` first and only document `init`, `run`, and `report` as bottom-layer commands.
- Update tests in `tests/test_cli_commands.py`, `tests/test_runner.py`, and add `tests/test_entrypoints.py`.

## Task 1: Remote Skill Refresh Module

**Files:**
- Create: `meguri/cli/entrypoints.py`
- Modify: `meguri/cli/init.py`
- Test: `tests/test_entrypoints.py`

- [ ] **Step 1: Write failing tests for entrypoint refresh**

Create `tests/test_entrypoints.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from meguri.cli.entrypoints import (
    ENTRYPOINT_SPECS,
    SkillRefreshError,
    refresh_entrypoints,
)


def test_refresh_entrypoints_fetches_remote_templates_and_overwrites_only_entrypoints(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()
    user_loop = project / ".meguri" / "loops" / "checkout" / "_loop.yaml"
    user_loop.parent.mkdir(parents=True)
    user_loop.write_text("user loop\n", encoding="utf-8")
    evidence = project / ".meguri" / "evidence" / "evidence.json"
    evidence.parent.mkdir(parents=True)
    evidence.write_text("{}", encoding="utf-8")

    def fake_fetch(url: str) -> str:
        name = url.rsplit("/", 1)[-1]
        return f"remote template for {name}\n/meguri\nmeguri init\nmeguri run\nmeguri report\n"

    written = refresh_entrypoints(project, offline=False, fetch_text=fake_fetch)

    rel_written = sorted(_display(project, path) for path in written)
    assert rel_written == [
        ".agents/skills/meguri/SKILL.md",
        ".claude/commands/meguri.md",
        ".claude/skills/meguri/SKILL.md",
        str(tmp_path / "home" / ".codex" / "prompts" / "meguri.md"),
    ]
    for spec in ENTRYPOINT_SPECS:
        path = spec.path_for(project)
        assert path.read_text(encoding="utf-8").startswith("remote template")
    assert user_loop.read_text(encoding="utf-8") == "user loop\n"
    assert evidence.read_text(encoding="utf-8") == "{}"


def test_refresh_entrypoints_offline_uses_bundled_templates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()

    def forbidden_fetch(url: str) -> str:
        raise AssertionError(f"offline mode should not fetch {url}")

    written = refresh_entrypoints(project, offline=True, fetch_text=forbidden_fetch)

    assert len(written) == 4
    codex_skill = project / ".agents" / "skills" / "meguri" / "SKILL.md"
    text = codex_skill.read_text(encoding="utf-8")
    assert "/meguri" in text
    assert "meguri init" in text
    assert "meguri run" in text
    assert "meguri report" in text


def test_refresh_entrypoints_remote_failure_raises_before_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    project = tmp_path / "project"
    project.mkdir()

    def failing_fetch(url: str) -> str:
        raise OSError("network down")

    with pytest.raises(SkillRefreshError, match="network down"):
        refresh_entrypoints(project, offline=False, fetch_text=failing_fetch)

    assert not (project / ".agents").exists()
    assert not (project / ".claude").exists()
    assert not (tmp_path / "home" / ".codex" / "prompts" / "meguri.md").exists()


def _display(project: Path, path: Path) -> str:
    try:
        return str(path.relative_to(project))
    except ValueError:
        return str(path)
```

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```bash
pytest tests/test_entrypoints.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'meguri.cli.entrypoints'`.

- [ ] **Step 3: Implement `meguri/cli/entrypoints.py`**

Create `meguri/cli/entrypoints.py` with this structure:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.error import URLError
from urllib.request import urlopen


REMOTE_TEMPLATE_BASE = "https://raw.githubusercontent.com/xyzizz/meguri/main/meguri/templates"


class SkillRefreshError(RuntimeError):
    pass


@dataclass(frozen=True)
class EntryPointSpec:
    key: str
    remote_name: str
    relative_path: tuple[str, ...] | None = None
    home_path: tuple[str, ...] | None = None

    def path_for(self, project_root: Path) -> Path:
        if self.relative_path is not None:
            return project_root.joinpath(*self.relative_path)
        if self.home_path is not None:
            return Path.home().joinpath(*self.home_path)
        raise ValueError(f"entrypoint spec has no path: {self.key}")

    @property
    def url(self) -> str:
        return f"{REMOTE_TEMPLATE_BASE}/{self.remote_name}"


ENTRYPOINT_SPECS = (
    EntryPointSpec(
        key="codex_skill",
        remote_name="codex_skill.md",
        relative_path=(".agents", "skills", "meguri", "SKILL.md"),
    ),
    EntryPointSpec(
        key="claude_skill",
        remote_name="claude_skill.md",
        relative_path=(".claude", "skills", "meguri", "SKILL.md"),
    ),
    EntryPointSpec(
        key="claude_command",
        remote_name="claude_command.md",
        relative_path=(".claude", "commands", "meguri.md"),
    ),
    EntryPointSpec(
        key="codex_prompt",
        remote_name="codex_prompt.md",
        home_path=(".codex", "prompts", "meguri.md"),
    ),
)


def refresh_entrypoints(
    project_root: Path,
    *,
    offline: bool,
    fetch_text: Callable[[str], str] | None = None,
) -> list[Path]:
    templates = bundled_templates() if offline else remote_templates(fetch_text or _fetch_url_text)
    _validate_templates(templates)
    written: list[Path] = []
    for spec in ENTRYPOINT_SPECS:
        path = spec.path_for(project_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(templates[spec.key], encoding="utf-8")
        written.append(path)
    return written


def remote_templates(fetch_text: Callable[[str], str]) -> dict[str, str]:
    templates: dict[str, str] = {}
    for spec in ENTRYPOINT_SPECS:
        try:
            templates[spec.key] = fetch_text(spec.url)
        except Exception as exc:  # noqa: BLE001
            raise SkillRefreshError(f"failed to refresh Meguri skill template {spec.remote_name}: {exc}") from exc
    return templates


def _fetch_url_text(url: str) -> str:
    try:
        with urlopen(url, timeout=20) as response:
            return response.read().decode("utf-8")
    except URLError as exc:
        raise SkillRefreshError(str(exc)) from exc


def _validate_templates(templates: dict[str, str]) -> None:
    missing = [spec.key for spec in ENTRYPOINT_SPECS if not templates.get(spec.key, "").strip()]
    if missing:
        raise SkillRefreshError(f"missing Meguri skill templates: {', '.join(missing)}")
    for spec in ENTRYPOINT_SPECS:
        text = templates[spec.key]
        required = ("/meguri", "meguri init", "meguri run", "meguri report")
        missing_terms = [term for term in required if term not in text]
        if missing_terms:
            raise SkillRefreshError(
                f"Meguri skill template {spec.remote_name} is missing required terms: "
                + ", ".join(missing_terms)
            )


def bundled_templates() -> dict[str, str]:
    return {
        "codex_skill": _codex_skill(),
        "claude_skill": _claude_skill(),
        "claude_command": _claude_command(),
        "codex_prompt": _codex_slash_prompt(),
    }
```

Then move the existing `_codex_skill()`, `_claude_skill()`, `_claude_command()`, and `_codex_slash_prompt()` functions from `meguri/cli/init.py` into this new file. In this task, keep their current content intact; Task 5 rewrites the wording.

- [ ] **Step 4: Update `meguri/cli/init.py` to import the new writer**

At the top of `meguri/cli/init.py`, add:

```python
from meguri.cli.entrypoints import refresh_entrypoints
```

Replace the current `write_skills()` function with:

```python
def write_skills(project_root: Path, *, offline: bool) -> list[Path]:
    return refresh_entrypoints(project_root, offline=offline)
```

Remove the moved `_codex_skill()`, `_claude_skill()`, `_claude_command()`, and `_codex_slash_prompt()` definitions from `meguri/cli/init.py`.

- [ ] **Step 5: Run entrypoint tests and commit**

Run:

```bash
pytest tests/test_entrypoints.py -q
```

Expected: PASS.

Commit:

```bash
git add meguri/cli/entrypoints.py meguri/cli/init.py tests/test_entrypoints.py
git commit -m "Add Meguri entrypoint refresh service"
```

## Task 2: Make `init` Refresh Skills by Default

**Files:**
- Modify: `meguri/cli/main.py`
- Modify: `meguri/cli/init.py`
- Test: `tests/test_cli_commands.py`

- [ ] **Step 1: Write failing init behavior tests**

Add these tests to `tests/test_cli_commands.py` near existing init tests:

```python
def test_init_refreshes_skills_before_writing_pack(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    calls: list[tuple[Path, bool]] = []

    def fake_refresh(project_root: Path, *, offline: bool) -> list[Path]:
        calls.append((project_root, offline))
        path = project_root / ".agents" / "skills" / "meguri" / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("remote /meguri meguri init meguri run meguri report\n", encoding="utf-8")
        return [path]

    monkeypatch.setattr("meguri.cli.init.write_skills", fake_refresh)

    assert main(["init"]) == 0

    assert calls == [(tmp_path, False)]
    assert (tmp_path / ".meguri" / "project.yaml").is_file()
    assert "remote /meguri" in (tmp_path / ".agents" / "skills" / "meguri" / "SKILL.md").read_text(encoding="utf-8")


def test_init_refresh_failure_stops_before_pack_writes(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)

    def failing_refresh(project_root: Path, *, offline: bool) -> list[Path]:
        raise RuntimeError("network down")

    monkeypatch.setattr("meguri.cli.init.write_skills", failing_refresh)

    assert main(["init"]) == 1
    captured = capsys.readouterr()

    assert "Meguri skill refresh failed" in captured.err
    assert "network down" in captured.err
    assert not (tmp_path / ".meguri").exists()


def test_init_offline_uses_bundled_templates(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    calls: list[bool] = []

    def fake_refresh(project_root: Path, *, offline: bool) -> list[Path]:
        calls.append(offline)
        path = project_root / ".agents" / "skills" / "meguri" / "SKILL.md"
        path.parent.mkdir(parents=True)
        path.write_text("offline /meguri meguri init meguri run meguri report\n", encoding="utf-8")
        return [path]

    monkeypatch.setattr("meguri.cli.init.write_skills", fake_refresh)

    assert main(["init", "--offline"]) == 0

    assert calls == [True]
```

- [ ] **Step 2: Run the new init tests and verify they fail**

Run:

```bash
pytest tests/test_cli_commands.py::test_init_refreshes_skills_before_writing_pack tests/test_cli_commands.py::test_init_refresh_failure_stops_before_pack_writes tests/test_cli_commands.py::test_init_offline_uses_bundled_templates -q
```

Expected: FAIL because `--offline` does not exist and `handle_init()` does not call the new writer with `offline`.

- [ ] **Step 3: Update CLI parser for `init`**

In `meguri/cli/main.py`, replace the init parser block with:

```python
    init = sub.add_parser("init", help="Initialize Meguri and refresh Meguri agent entrypoints.")
    init.add_argument("--offline", action="store_true", help="Use bundled entrypoint templates instead of fetching from the official repository.")
    init.add_argument("--force", action="store_true", help="Overwrite generated Meguri system files.")
```

Remove `--install-skills`.

- [ ] **Step 4: Update `handle_init()` failure ordering**

In `meguri/cli/init.py`, replace the start of `handle_init()` with:

```python
def handle_init(args: Any) -> int:
    project_root = Path.cwd().resolve()
    pack_root = pack_root_for(project_root)
    created: list[Path] = []
    skipped: list[Path] = []
    force = bool(getattr(args, "force", False))
    offline = bool(getattr(args, "offline", False))

    try:
        created.extend(write_skills(project_root, offline=offline))
    except Exception as exc:  # noqa: BLE001
        print(f"error: Meguri skill refresh failed: {exc}", file=sys.stderr)
        if not offline:
            print("rerun with --offline to use bundled templates without network access", file=sys.stderr)
        return 1

    created.extend(_write_pack(project_root, pack_root, force=force, skipped=skipped))
    pack = load_project_pack(project_root)
    prompt_path, prompt = write_inspect_spec(pack)
```

Keep the existing output loop after this block.

- [ ] **Step 5: Run init tests and commit**

Run:

```bash
pytest tests/test_cli_commands.py::test_init_refreshes_skills_before_writing_pack tests/test_cli_commands.py::test_init_refresh_failure_stops_before_pack_writes tests/test_cli_commands.py::test_init_offline_uses_bundled_templates -q
```

Expected: PASS.

Commit:

```bash
git add meguri/cli/main.py meguri/cli/init.py tests/test_cli_commands.py
git commit -m "Refresh Meguri entrypoints during init"
```

## Task 3: Reduce Public CLI to `init`, `run`, and `report`

**Files:**
- Modify: `meguri/cli/main.py`
- Modify: `meguri/cli/validate.py`
- Test: `tests/test_cli_commands.py`

- [ ] **Step 1: Write failing public CLI and run-target tests**

Add these tests to `tests/test_cli_commands.py`:

```python
def test_cli_help_only_exposes_three_public_commands(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--help"])
    assert exc.value.code == 0
    output = capsys.readouterr().out

    assert "init" in output
    assert "run" in output
    assert "report" in output
    for removed in (" add", " loops", " delete", " validate", " inspect", " upgrade", " validate-scenario"):
        assert removed not in output


def test_removed_public_commands_are_rejected(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    for command in ("inspect", "add", "loops", "delete", "validate", "validate-scenario", "upgrade"):
        with pytest.raises(SystemExit) as exc:
            main([command])
        assert exc.value.code == 2


def test_run_all_selects_user_loops_only(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    _write_loop(tmp_path, "login", [sys.executable, "-c", "print('login')"])
    _write_loop(tmp_path, "checkout", [sys.executable, "-c", "print('checkout')"])

    assert main(["run", "all"]) == 0
    output = capsys.readouterr().out

    assert "loop=login" in output
    assert "loop=checkout" in output
    assert "loop=smoke" not in output
    assert "batch_report=" in output


def test_run_without_target_requires_loop_or_all(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()

    assert main(["run"]) == 2
    assert "provide a loop name or all" in capsys.readouterr().err


def test_run_rejects_removed_selection_flags(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0

    for args in (["run", "--all"], ["run", "all", "--exclude", "checkout"], ["run", "all", "--include-system"]):
        with pytest.raises(SystemExit) as exc:
            main(args)
        assert exc.value.code == 2
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
pytest tests/test_cli_commands.py::test_cli_help_only_exposes_three_public_commands tests/test_cli_commands.py::test_removed_public_commands_are_rejected tests/test_cli_commands.py::test_run_all_selects_user_loops_only tests/test_cli_commands.py::test_run_without_target_requires_loop_or_all tests/test_cli_commands.py::test_run_rejects_removed_selection_flags -q
```

Expected: FAIL because old commands and run flags still exist.

- [ ] **Step 3: Remove public parser entries and imports**

In `meguri/cli/main.py`, remove these imports:

```python
from meguri.cli.add import handle_add
from meguri.cli.inspect import handle_inspect
from meguri.cli.loops import handle_delete, handle_loops, read_loops
from meguri.cli.upgrade import handle_upgrade
from meguri.cli.validate import handle_validate
```

Replace them with:

```python
from meguri.cli.loops import read_loops
from meguri.cli.validate import validate_scenario_files
```

Delete the parser blocks for `inspect`, `add`, `loops`, `delete`, `validate`, `validate-scenario`, and `upgrade`.

Delete the matching `if args.cmd == ...` dispatch blocks.

- [ ] **Step 4: Update run parser**

Replace the run parser setup with:

```python
    run = sub.add_parser("run", help="Run one loop, an explicit loop list, or all user loops.")
    run.add_argument("targets", nargs="*", help="Loop aliases, or the literal 'all'.")
    run.add_argument("--runs-dir")
    run.add_argument("--replay")
    run.add_argument("--retry-of")
    run.add_argument("--allow-execute", action="store_true", help="Confirm execute-mode loops for this run.")
    run.add_argument("--json", action="store_true")
    run.add_argument("--open", action="store_true", help="Open the generated HTML report.")
```

- [ ] **Step 5: Replace `_select_run_targets()`**

Replace `_select_run_targets(args)` in `meguri/cli/main.py` with:

```python
def _select_run_targets(args) -> list[str]:
    targets = [str(value) for value in getattr(args, "targets", [])]
    if not targets:
        raise ValueError("provide a loop name or all")
    if "all" in targets and len(targets) > 1:
        raise ValueError("use either all or explicit loop names, not both")
    if targets == ["all"]:
        pack = find_project_pack(Path.cwd())
        entries = [entry for entry in read_loops(pack) if entry.source == "user"]
        names = [entry.loop_id for entry in entries]
        if not names:
            raise ValueError("no user loops found; ask /meguri to add a loop first")
        return names
    return targets
```

- [ ] **Step 6: Expose internal validation service**

In `meguri/cli/validate.py`, add this function above `handle_validate()`:

```python
def validate_scenario_files(paths: list[Path]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for path in paths:
        _validate_scenario_path(path, errors, warnings)
    return errors, warnings
```

- [ ] **Step 7: Call validation before execute-mode checks**

In `meguri/cli/main.py`, after resolving `scenario_paths` and before `_execute_loop_names()`, insert:

```python
        validation_errors, validation_warnings = validate_scenario_files(scenario_paths)
        for warning in validation_warnings:
            print(f"warning: {warning}", file=sys.stderr)
        if validation_errors:
            for error in validation_errors:
                print(f"error: {error}", file=sys.stderr)
            return 1
```

- [ ] **Step 8: Run targeted tests and commit**

Run:

```bash
pytest tests/test_cli_commands.py::test_cli_help_only_exposes_three_public_commands tests/test_cli_commands.py::test_removed_public_commands_are_rejected tests/test_cli_commands.py::test_run_all_selects_user_loops_only tests/test_cli_commands.py::test_run_without_target_requires_loop_or_all tests/test_cli_commands.py::test_run_rejects_removed_selection_flags -q
```

Expected: PASS.

Commit:

```bash
git add meguri/cli/main.py meguri/cli/validate.py tests/test_cli_commands.py
git commit -m "Reduce public CLI commands"
```

## Task 4: Make `report` Read-Only

**Files:**
- Modify: `meguri/cli/main.py`
- Modify: `meguri/cli/report.py`
- Test: `tests/test_cli_commands.py`

- [ ] **Step 1: Write failing report simplification tests**

Add these tests to `tests/test_cli_commands.py`:

```python
def test_report_defaults_to_latest_existing_report(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0
    capsys.readouterr()
    _write_loop(tmp_path, "login", [sys.executable, "-c", "print('login')"])
    assert main(["run", "login"]) == 0
    run_output = capsys.readouterr().out
    html_path = next(line.split("=", 1)[1] for line in run_output.splitlines() if line.startswith("html_report="))

    assert main(["report"]) == 0

    assert capsys.readouterr().out.strip() == html_path


def test_report_rejects_manual_batch_and_refresh_flags(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["init", "--offline"]) == 0

    for args in (
        ["report", "--recent", "2"],
        ["report", "--runs", "a", "b"],
        ["report", "--loops", "login"],
        ["report", "--running"],
        ["report", "--refresh"],
        ["report", "--last"],
    ):
        with pytest.raises(SystemExit) as exc:
            main(args)
        assert exc.value.code == 2
```

- [ ] **Step 2: Run report tests and verify they fail**

Run:

```bash
pytest tests/test_cli_commands.py::test_report_defaults_to_latest_existing_report tests/test_cli_commands.py::test_report_rejects_manual_batch_and_refresh_flags -q
```

Expected: FAIL because the old report flags are still accepted.

- [ ] **Step 3: Update report parser**

In `meguri/cli/main.py`, replace the report parser block with:

```python
    report = sub.add_parser("report", help="Show or open an existing Meguri report.")
    report.add_argument("run_id", nargs="?")
    report.add_argument("--json", action="store_true", help="Print clean JSON for the resolved report.")
    report.add_argument("--open", action="store_true", help="Open the report.")
```

- [ ] **Step 4: Simplify `handle_report()`**

In `meguri/cli/report.py`, replace `handle_report(args)` with:

```python
def handle_report(args: Any) -> int:
    try:
        pack = find_project_pack(Path.cwd())
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    try:
        html_path = latest_report(pack) if not args.run_id else report_for_run(pack, args.run_id)
        json_record = report_record_for_html(html_path) if getattr(args, "json", False) else None
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if getattr(args, "json", False):
        print(json.dumps(json_record, ensure_ascii=False, indent=2, default=str))
    else:
        print(html_path)
    if args.open and not open_path(html_path):
        print(f"could not open report automatically: {html_path}", file=sys.stderr)
    return 0
```

Leave `latest_report()`, `report_for_run()`, and `report_record_for_html()` intact. Remove or leave unused the manual batch helpers in this task; if removing them creates a large diff, keep them private and unreferenced until a later cleanup.

- [ ] **Step 5: Run report tests and commit**

Run:

```bash
pytest tests/test_cli_commands.py::test_report_defaults_to_latest_existing_report tests/test_cli_commands.py::test_report_rejects_manual_batch_and_refresh_flags -q
```

Expected: PASS.

Commit:

```bash
git add meguri/cli/main.py meguri/cli/report.py tests/test_cli_commands.py
git commit -m "Make report command read-only"
```

## Task 5: Simplify Generated Agent Entrypoints and Docs

**Files:**
- Modify: `meguri/cli/entrypoints.py`
- Modify: `meguri/cli/init.py`
- Create: `meguri/templates/codex_skill.md`
- Create: `meguri/templates/claude_skill.md`
- Create: `meguri/templates/claude_command.md`
- Create: `meguri/templates/codex_prompt.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `prompts/install.md`
- Test: `tests/test_cli_commands.py`

- [ ] **Step 1: Write failing generated-text tests**

Update `test_init_creates_project_pack_and_skills` in `tests/test_cli_commands.py` so it asserts the simplified surface:

```python
    assert "/meguri" in codex_skill
    assert "meguri init" in codex_skill
    assert "meguri run" in codex_skill
    assert "meguri report" in codex_skill
    for removed in (
        "meguri add",
        "meguri loops",
        "meguri delete",
        "meguri validate",
        "meguri upgrade",
        "meguri report --recent",
        "meguri report --runs",
        "meguri report --loops",
        "meguri run --all",
        "meguri run --exclude",
    ):
        assert removed not in codex_skill
        assert removed not in claude_skill
        assert removed not in codex_prompt
```

Keep existing assertions for `MEGURI_EVIDENCE_DIR`, `--allow-execute`, and crash-safe evidence.

- [ ] **Step 2: Run the generated-text test and verify it fails**

Run:

```bash
pytest tests/test_cli_commands.py::test_init_creates_project_pack_and_skills -q
```

Expected: FAIL because current templates still list old commands.

- [ ] **Step 3: Replace bundled skill wording**

In `meguri/cli/entrypoints.py`, rewrite `_codex_skill()` and `_claude_skill()` to describe the natural-language workflow. Use this shared body for both functions:

```python
def _agent_skill_body() -> str:
    return """---
name: meguri
description: Use when the user invokes /meguri or asks to initialize Meguri, add or remove verification loops, run Meguri loops, inspect reports, or refresh Meguri agent entrypoints.
---

You are using the Meguri workflow.

Meguri is an agent-facing verification workbench. The user should mostly use
natural language through `/meguri`; the CLI is the stable execution layer you
call after understanding the project.

Public CLI surface:
- `meguri init`: refresh Meguri agent entrypoints from the official repository,
  initialize or refresh the project pack, and print the inspect workflow.
- `meguri run <loop>`: validate and run one loop.
- `meguri run <loop1> <loop2>`: validate and run an explicit loop list, writing
  an automatic batch report.
- `meguri run all`: validate and run all user loops, excluding system smoke.
- `meguri report [run_or_batch_id]`: print the latest or specified report path.

Natural-language workflow:
1. For initialization, run `meguri init` and then follow the printed inspect
   workflow in this same agent session.
2. For adding a loop, read the repository first. Only write
   `.meguri/loops/<loop_id>/_loop.yaml` after the user goal, safe execution
   entry, and deterministic pass criteria are clear.
3. For deleting a loop, remove only the intended user loop directory under
   `.meguri/loops/`.
4. For running verification, prefer `meguri run <loop>`, `meguri run <loop1>
   <loop2>`, or `meguri run all`.
5. For reports, use `meguri report` or `meguri report <run_or_batch_id>`.

Rules:
- Keep new loops in `dry_run` unless the user explicitly approves execute mode.
- Execute-mode loops must be run with `--allow-execute`.
- Never treat an LLM self-evaluation as passing evidence.
- Passing evidence must come from deterministic commands, structured output,
  logs, artifacts, screenshots, or files.
- Helper/verifier scripts must write crash-safe structured evidence to
  `MEGURI_EVIDENCE_DIR`, including partial input/output, errors, tracebacks,
  and artifact paths when failures occur.
- Ask before enabling submit, deploy, payment, production writes, external
  sends, or data migrations.
"""
```

Then make both functions return it:

```python
def _codex_skill() -> str:
    return _agent_skill_body()


def _claude_skill() -> str:
    return _agent_skill_body()
```

- [ ] **Step 4: Replace command and prompt wording**

In `meguri/cli/entrypoints.py`, rewrite `_claude_command()`:

```python
def _claude_command() -> str:
    return """---
description: Meguri verification workflow
argument-hint: init|run|report [args]
---

Use the Meguri workflow in this repository.

The normal user entrypoint is `/meguri`.

If the user asks to initialize or refresh Meguri, run:

```bash
meguri init
```

If the user asks to run verification, use:

```bash
meguri run <loop>
meguri run <loop1> <loop2>
meguri run all
```

If the user asks for reports, use:

```bash
meguri report
meguri report <run_or_batch_id>
```

When adding or changing loops, inspect the project first and write loop files
under `.meguri/loops/<loop_id>/_loop.yaml`. Keep evidence deterministic and use
`MEGURI_EVIDENCE_DIR` for crash-safe structured artifacts.
"""
```

Rewrite `_codex_slash_prompt()`:

```python
def _codex_slash_prompt() -> str:
    return """---
description: Meguri verification workflow
argument-hint: init|run|report [args]
---

Use this active Codex session to operate Meguri.

The normal user entrypoint is `/meguri`.

Prefer natural-language workflow:
- initialize or refresh this project with `meguri init`
- add or remove loops by inspecting the project and editing `.meguri/loops`
- run verification with `meguri run <loop>`, `meguri run <loop1> <loop2>`, or `meguri run all`
- open reports with `meguri report`

Do not treat LLM self-evaluation as passing evidence. Use deterministic
commands, structured output, logs, artifacts, screenshots, or files. Helper
scripts should write crash-safe structured evidence to `MEGURI_EVIDENCE_DIR`.
"""
```

- [ ] **Step 5: Create official remote template files**

Create these files with the same simplified content returned by the bundled template functions:

```text
meguri/templates/codex_skill.md
meguri/templates/claude_skill.md
meguri/templates/claude_command.md
meguri/templates/codex_prompt.md
```

Use the `_agent_skill_body()` content for both `codex_skill.md` and `claude_skill.md`. Use `_claude_command()` content for `claude_command.md`. Use `_codex_slash_prompt()` content for `codex_prompt.md`.

After creating them, run:

```bash
rg "/meguri|meguri init|meguri run|meguri report" meguri/templates
```

Expected: each of the four template files contains `/meguri`, `meguri init`, `meguri run`, and `meguri report`.

- [ ] **Step 6: Shorten `.meguri/README.md` generated by init**

In `meguri/cli/init.py`, replace `_pack_readme(project_name)` with a shorter README that lists only `/meguri`, `init`, `run`, and `report`. Preserve the evidence and execute-mode safety rules.

Use this opening:

```python
def _pack_readme(project_name: str) -> str:
    return f"""# Meguri Pack

This directory contains the Meguri project pack for `{project_name}`.

Meguri's normal user entrypoint is `/meguri`. The user can ask the active
Codex or Claude Code agent to initialize the project, add verification loops,
run verification, and open reports in natural language.

The public CLI surface is intentionally small:

```bash
meguri init
meguri run <loop>
meguri run <loop1> <loop2>
meguri run all
meguri report [run_or_batch_id]
```

Loops live under `.meguri/loops/<loop_id>/_loop.yaml`. Run records live under
`.meguri/loops/<loop_id>/<run_id>/`. Multi-loop runs write automatic batch
records under `.meguri/batches/<batch_id>/`.

Keep loops deterministic. Do not treat an LLM's self-evaluation as a passing
check. If you write helper or verifier scripts, write structured JSON evidence
to `MEGURI_EVIDENCE_DIR` in a `finally` path so failures still include partial
input/output, errors, traceback, and artifact paths.

Keep loops in `dry_run` unless the user explicitly approves execute mode. After
approval, execute-mode loops must be run with `meguri run <loop> --allow-execute`.
"""
```

- [ ] **Step 7: Update top-level docs**

Edit `README.md`, `README.zh-CN.md`, and `prompts/install.md` so the quick start says:

```text
Open Codex or Claude Code in the target project and invoke `/meguri`.

Common requests:
- Initialize this project with Meguri.
- Add a verification loop for <goal>.
- Run all verification.
- Open the latest report.
```

Document only the bottom-layer commands:

```bash
meguri init
meguri run <loop>
meguri run <loop1> <loop2>
meguri run all
meguri report [run_or_batch_id]
```

Remove references to `meguri add`, `meguri loops`, `meguri delete`, `meguri validate`, `meguri upgrade`, `meguri report --recent`, `meguri report --runs`, `meguri report --loops`, `meguri report --running`, `meguri report --refresh`, `meguri run --all`, `meguri run --exclude`, and `meguri run --include-system`.

- [ ] **Step 8: Run generated-text tests and commit**

Run:

```bash
pytest tests/test_cli_commands.py::test_init_creates_project_pack_and_skills -q
```

Expected: PASS.

Commit:

```bash
git add meguri/cli/entrypoints.py meguri/cli/init.py meguri/templates README.md README.zh-CN.md prompts/install.md tests/test_cli_commands.py
git commit -m "Simplify Meguri user-facing workflow docs"
```

## Task 6: Full Regression and Dead Public Surface Sweep

**Files:**
- Modify: `tests/test_cli_commands.py`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `prompts/install.md`
- Modify: `meguri/cli/entrypoints.py`
- Modify: `meguri/templates/codex_skill.md`
- Modify: `meguri/templates/claude_skill.md`
- Modify: `meguri/templates/claude_command.md`
- Modify: `meguri/templates/codex_prompt.md`

- [ ] **Step 1: Run the full test suite**

Run:

```bash
pytest -q
```

Expected: Some old tests fail because they still exercise removed public commands and removed report-builder flags.

- [ ] **Step 2: Remove or rewrite obsolete tests**

In `tests/test_cli_commands.py`, remove tests whose only purpose is to assert old public behavior for:

```text
meguri add
meguri loops
meguri delete
meguri validate
meguri inspect
meguri upgrade
meguri run --all
meguri run --exclude
meguri run --include-system
meguri report --recent
meguri report --runs
meguri report --loops
meguri report --running
meguri report --refresh
meguri report --last
```

Preserve tests for underlying behavior when it still exists through the new path:

- Multi-loop run creates batch report through `meguri run <loop1> <loop2>`.
- `meguri run all` creates batch report for user loops.
- `meguri report` resolves latest existing single run or batch.
- `meguri report <batch_id>` resolves existing batch.
- Execute mode still requires `--allow-execute`.
- Live run snapshots still print and write report files.

- [ ] **Step 3: Sweep stale public command wording**

Run:

```bash
rg "meguri (add|loops|delete|validate|upgrade|inspect)|report --(recent|runs|loops|running|refresh|last)|run --(all|exclude|include-system)" README.md README.zh-CN.md prompts/install.md meguri/cli meguri/templates tests -n
```

Expected: matches remain only in `tests/test_cli_commands.py` tests that assert rejection of removed commands. Edit every stale match in README files, prompt files, `meguri/cli/entrypoints.py`, and `meguri/templates/*.md`.

- [ ] **Step 4: Run full tests again**

Run:

```bash
pytest -q
```

Expected: PASS.

- [ ] **Step 5: Run CLI smoke checks**

Run:

```bash
python -m meguri.cli.main --help
python -m meguri.cli.main init --help
python -m meguri.cli.main run --help
python -m meguri.cli.main report --help
```

Expected:

- Top-level help lists `init`, `run`, and `report`.
- `init --help` includes `--offline` and `--force`.
- `run --help` does not include `--all`, `--exclude`, or `--include-system`.
- `report --help` does not include `--recent`, `--runs`, `--loops`, `--running`, `--refresh`, or `--last`.

- [ ] **Step 6: Commit final cleanup**

Commit:

```bash
git add README.md README.zh-CN.md prompts/install.md meguri tests
git commit -m "Finish Meguri simplified workflow migration"
```

## Self-Review

Spec coverage:

- Natural-language `/meguri` primary workflow: Task 5 updates generated entrypoints and docs.
- Three public CLI commands: Task 3 removes old parser entries and tests top-level help.
- `init` default remote refresh and failure behavior: Tasks 1 and 2 add refresh service and init failure ordering.
- `init --offline`: Task 2 adds parser and behavior.
- `run all` user loops only: Task 3 implements target selection and tests it.
- Auto validate before run: Task 3 exposes validation service and calls it before execution.
- Multi-loop automatic batch report: Task 3 preserves existing multi-loop run path and tests it through `run all`.
- Read-only report command: Task 4 removes manual report-builder flags.
- Generated prompt/doc simplification: Task 5 covers bundled templates, official remote template files, pack README, README files, and install prompt.
- Full regression and stale wording sweep: Task 6 covers suite and search.

Placeholder scan:

- The plan contains no blocked filler tokens or unspecified code paths.
- Large existing template strings are moved in Task 1 and rewritten explicitly in Task 5.

Type consistency:

- `refresh_entrypoints(project_root, *, offline, fetch_text=None)` is used consistently in tests and `write_skills()`.
- `write_skills(project_root, *, offline)` is the only init-facing wrapper.
- `validate_scenario_files(paths)` returns `(errors, warnings)` and is consumed before execute-mode checks.
