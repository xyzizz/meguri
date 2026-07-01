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
    _validate_templates(templates, require_terms=not offline)
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


def _validate_templates(templates: dict[str, str], *, require_terms: bool) -> None:
    missing = [spec.key for spec in ENTRYPOINT_SPECS if not templates.get(spec.key, "").strip()]
    if missing:
        raise SkillRefreshError(f"missing Meguri skill templates: {', '.join(missing)}")
    if not require_terms:
        return
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


def _codex_skill() -> str:
    return """---
name: meguri
description: Use when the user wants Codex to initialize, design, add, list, delete, run, validate, inspect, or repair Meguri verification loops in this repository. Trigger for $meguri or /meguri, loop design, project verification planning, loop generation, loop deletion, run reports, artifacts, and evidence-driven agent repair.
---

You are using the Meguri init workflow for Codex.

Meguri is an agent-facing verification workflow. Its user-facing unit is a
loop: check evidence, repair when safe, rerun, then pass, block, or ask.
Meguri owns specification files, deterministic validation, loop execution, and
reports. Codex owns project understanding, loop design, and any code/test
authoring.

Use `$meguri` as the user-facing entrypoint in conversation.

Workflow:
1. If the request is empty, starts with `init`, or `.meguri/project.yaml` is
   missing, run `meguri init`.
2. Follow the printed Meguri init specification yourself in this Codex session.
3. Read README, AGENTS.md, project manifests, existing tests, scripts, CI config,
   app entrypoints, and existing Meguri loops before editing.
4. Write `.meguri/project-inspect.json` and `.meguri/project-brief.md` from your
   evidence. If user goals, execution entries, pass criteria, credentials, data
   setup, or forbidden side effects are unclear, ask concrete questions and stop.
5. When the user asks to design or add verification, produce deterministic loops
   and any required test/helper code. Use `meguri add` only after the required
   fields are clear.
6. Prefer deterministic checks over LLM judgment. Never mark a run as passing
   because the model says it passed.
7. When writing verifier/helper scripts, make evidence crash-safe: write
   structured JSON evidence to `MEGURI_EVIDENCE_DIR` in a `finally` path, and
   include partial input/output, errors, traceback, and artifact paths even when
   the target app or model response crashes.
8. Keep loops in `dry_run` unless the user explicitly approves execute mode.
   After that approval, run execute-mode loops with
   `meguri run <loop> --allow-execute`; without that confirmation marker Meguri
   will refuse to run execute loops.
9. Use `meguri loops` to list user-added loops. Use `meguri delete <loop>` to
   delete a named user-added loop.
10. If the user asks to refresh Meguri entrypoints or report indexes after an
   update, run `meguri upgrade --skills --refresh-index`.
11. After edits, run `meguri validate` and then `meguri run <loop> --open`
   when safe. When the user asks to run several loops in order, use
   `meguri run <loop1> <loop2>` so Meguri records one sequential batch instead
   of starting loops manually or concurrently. When the user asks to run all
   remaining user-added loops, use `meguri run --all --exclude <loop>` after
   confirming the exclusion list. Batch `batch.json` and `index.html` are
   created when the batch starts, refreshed whenever the current loop writes a
   running snapshot, and refreshed again after each loop completes; use them as
   the live progress surface. Shell stdout/stderr output also refreshes the
   current run's HTML/stdout excerpts while the command is still running, and
   silent-step heartbeats refresh `updated_at` even when stdout is quiet. In
   normal text mode, `meguri run` also prints `live_report=...`,
   `live_artifact_dir=...`, `live_updated_at=...`, `live_step=...`,
   `live_stdout_path=...`, `live_stderr_path=...`, and live character counts
   as soon as a running snapshot exists, output advances, or a silent heartbeat
   refreshes the run; `--json` stays clean final JSON only. Read batch
   `current_run` for the live report path and current step. While long loops are still running, use
   `meguri report --running --json` to find active run/batch report paths and
   current steps instead of guessing from the filesystem. If the batch is
   interrupted, read the blocked batch record's `interrupted` metadata and
   `remaining_loops` before deciding whether to resume, repair, or ask.
12. Inspect the latest `.meguri/loops/<loop_id>/<run_id>/timeline.ndjson`,
   `run.json`, `report.md`, `index.html`, stdout, stderr, evidence, and
   linked artifacts before proposing fixes. For a single completed loop, use
   `meguri report <run_id> --json` or `meguri report --last --json` to get the
   structured run summary, metrics, failure reasons, `evidence_files`,
   `evidence_warnings`, `replay_status`, and `replay_missing` before drilling
   into raw artifacts. If an older single-run `index.html` or `report.md`
   predates the current Meguri renderer, use `meguri report <run_id> --refresh`
   to rebuild both from `run.json` before opening or quoting them. For multi-loop runs, inspect
   `.meguri/batches/<batch_id>/batch.json` and its `index.html` first, use
   `status_counts`, `failed_loops`, per-loop `mode`, per-loop `metrics`,
   `attention_flags`, `created_resources`, `failed_items`, `validation_issues`,
   `repair_hints`, `failure_groups`, and per-loop summaries to prioritize
   shared repairs, identify bad source objects, identify schema/output-shape
   failures, identify incomplete agent chains, and audit partial execute-mode
   side effects, then drill into each linked loop report. If
   earlier runs were started separately and you know the loop names, use
   `meguri report --loops <loop> ...` to group the newest run for each named
   loop before summarizing. If you only know the count, use
   `meguri report --recent <N>` to group the latest standalone reports into a
   recoverable batch report. If you have exact run ids or report paths, use
   `meguri report --runs <run_id-or-path> ...` so unrelated reports are not
   included. Use `meguri report --loops <loop> ... --json`,
   `meguri report --recent <N> --json`, or
   `meguri report --runs <run_id-or-path> ... --json` when you need clean
   structured data for a written summary. After making a repair, use the batch
   `retry_loops` list to understand which failed, blocked, or recovered running
   loops need another pass, then rerun only the named loop(s) intentionally.
13. Stop and ask before enabling submit, deploy, payment, production writes,
    external sends, or data migrations.
"""


def _codex_slash_prompt() -> str:
    return """---
description: Meguri verification loop workflow for the current project
argument-hint: init|add|loops|delete|run|validate|report|upgrade [args]
---

Use Meguri for this request: $ARGUMENTS

Meguri is a specification and harness layer. Use this active Codex session for
project understanding, loop design, and any code/test authoring.

If the request is empty or starts with `init`, run `meguri init`, follow the
printed specification yourself, and write
`.meguri/project-inspect.json` plus `.meguri/project-brief.md`.

If the request asks to add/design a loop, first inspect existing docs,
manifests, tests, scripts, CI, and entrypoints. Ask concrete questions when the
goal, execution entry, pass criteria, credentials, data setup, or forbidden side
effects are unclear. Then write deterministic loops and any needed test/helper
code. Verifier/helper scripts must write structured evidence to
`MEGURI_EVIDENCE_DIR` even on exceptions, including partial transcript, errors,
traceback, and artifact paths; do not rely only on stdout.

If the request asks to list or delete loops, list only user-added loops by
default and delete only a named user-added loop unless the user explicitly asks
to include or remove system loops.

If the request asks to refresh Meguri after an update, run
`meguri upgrade --skills --refresh-index`.

Always prefer deterministic evidence over LLM self-evaluation. Keep loops in
`dry_run` unless the user explicitly approves execute mode. After that approval,
run execute-mode loops with `meguri run <loop> --allow-execute`; without that
confirmation marker Meguri refuses execute loops. Before reporting completion,
run `meguri validate` and the relevant `meguri run <loop> --open` when safe.
"""


def _claude_skill() -> str:
    return """---
name: meguri
description: Use when the user wants Claude Code to initialize, design, add, list, delete, run, validate, inspect, or repair Meguri verification loops in this repository. Trigger for /meguri, loop design, project verification planning, loop generation, loop deletion, run reports, artifacts, and evidence-driven agent repair.
argument-hint: init|add|loops|delete|run|validate|report|upgrade [args]
disable-model-invocation: true
---

You are using the Meguri init workflow for Claude Code.

Meguri is an agent-facing verification workflow. Its user-facing unit is a
loop: check evidence, repair when safe, rerun, then pass, block, or ask.
Meguri owns specification files, deterministic validation, loop execution, and
reports. Claude Code owns project understanding, loop design, and any code/test
authoring.

Use `/meguri` as the user-facing entrypoint in conversation.

Requested Meguri workflow:
$ARGUMENTS

Workflow:
1. If the request is empty, starts with `init`, or `.meguri/project.yaml` is
   missing, run `meguri init`.
2. Follow the printed Meguri init specification yourself in this Claude Code
   session.
3. Read README, CLAUDE.md, project manifests, existing tests, scripts, CI config,
   app entrypoints, and existing Meguri loops before editing.
4. Write `.meguri/project-inspect.json` and `.meguri/project-brief.md` from your
   evidence. If user goals, execution entries, pass criteria, credentials, data
   setup, or forbidden side effects are unclear, ask concrete questions and stop.
5. When the user asks to design or add verification, produce deterministic loops
   and any required test/helper code. Use `meguri add` only after the required
   fields are clear.
6. Prefer deterministic checks over LLM judgment. Never mark a run as passing
   because the model says it passed.
7. When writing verifier/helper scripts, make evidence crash-safe: write
   structured JSON evidence to `MEGURI_EVIDENCE_DIR` in a `finally` path, and
   include partial input/output, errors, traceback, and artifact paths even when
   the target app or model response crashes.
8. Keep loops in `dry_run` unless the user explicitly approves execute mode.
   After that approval, run execute-mode loops with
   `meguri run <loop> --allow-execute`; without that confirmation marker Meguri
   will refuse to run execute loops.
9. Use `meguri loops` to list user-added loops. Use `meguri delete <loop>` to
   delete a named user-added loop.
10. If the user asks to refresh Meguri entrypoints or report indexes after an
   update, run `meguri upgrade --skills --refresh-index`.
11. After edits, run `meguri validate` and then `meguri run <loop> --open`
   when safe. When the user asks to run several loops in order, use
   `meguri run <loop1> <loop2>` so Meguri records one sequential batch instead
   of starting loops manually or concurrently. When the user asks to run all
   remaining user-added loops, use `meguri run --all --exclude <loop>` after
   confirming the exclusion list. Batch `batch.json` and `index.html` are
   created when the batch starts, refreshed whenever the current loop writes a
   running snapshot, and refreshed again after each loop completes; use them as
   the live progress surface. Shell stdout/stderr output also refreshes the
   current run's HTML/stdout excerpts while the command is still running, and
   silent-step heartbeats refresh `updated_at` even when stdout is quiet. In
   normal text mode, `meguri run` also prints `live_report=...`,
   `live_artifact_dir=...`, `live_updated_at=...`, `live_step=...`,
   `live_stdout_path=...`, `live_stderr_path=...`, and live character counts
   as soon as a running snapshot exists, output advances, or a silent heartbeat
   refreshes the run; `--json` stays clean final JSON only. Read batch
   `current_run` for the live report path and current step. While long loops are still running, use
   `meguri report --running --json` to find active run/batch report paths and
   current steps instead of guessing from the filesystem. If the batch is
   interrupted, read the blocked batch record's `interrupted` metadata and
   `remaining_loops` before deciding whether to resume, repair, or ask.
12. Inspect the latest `.meguri/loops/<loop_id>/<run_id>/timeline.ndjson`,
   `run.json`, `report.md`, `index.html`, stdout, stderr, evidence, and
   linked artifacts before proposing fixes. For a single completed loop, use
   `meguri report <run_id> --json` or `meguri report --last --json` to get the
   structured run summary, metrics, failure reasons, `evidence_files`,
   `evidence_warnings`, `replay_status`, and `replay_missing` before drilling
   into raw artifacts. If an older single-run `index.html` or `report.md`
   predates the current Meguri renderer, use `meguri report <run_id> --refresh`
   to rebuild both from `run.json` before opening or quoting them. For multi-loop runs, inspect
   `.meguri/batches/<batch_id>/batch.json` and its `index.html` first, use
   `status_counts`, `failed_loops`, per-loop `mode`, per-loop `metrics`,
   `attention_flags`, `created_resources`, `failed_items`, `validation_issues`,
   `repair_hints`, `failure_groups`, and per-loop summaries to prioritize
   shared repairs, identify bad source objects, identify schema/output-shape
   failures, identify incomplete agent chains, and audit partial execute-mode
   side effects, then drill into each linked loop report. If
   earlier runs were started separately and you know the loop names, use
   `meguri report --loops <loop> ...` to group the newest run for each named
   loop before summarizing. If you only know the count, use
   `meguri report --recent <N>` to group the latest standalone reports into a
   recoverable batch report. If you have exact run ids or report paths, use
   `meguri report --runs <run_id-or-path> ...` so unrelated reports are not
   included. Use `meguri report --loops <loop> ... --json`,
   `meguri report --recent <N> --json`, or
   `meguri report --runs <run_id-or-path> ... --json` when you need clean
   structured data for a written summary. After making a repair, use the batch
   `retry_loops` list to understand which failed, blocked, or recovered running
   loops need another pass, then rerun only the named loop(s) intentionally.
13. Stop and ask before enabling submit, deploy, payment, production writes,
    external sends, or data migrations.
"""


def _claude_command() -> str:
    return """---
description: Meguri verification loop workflow for the current project
argument-hint: init|add|loops|delete|run|validate|report|upgrade [args]
---

Use the Meguri loop workflow in this Claude Code session.

Requested Meguri workflow:
$ARGUMENTS

If the request is empty or starts with `init`, run `meguri init`, follow the
printed specification, and write
`.meguri/project-inspect.json` plus `.meguri/project-brief.md`.

For add, loops, delete, run, validate, report, or upgrade requests, follow the
project-local Meguri pack, prefer deterministic evidence, keep loops in
`dry_run` unless explicitly approved, make helper scripts write crash-safe
evidence to `MEGURI_EVIDENCE_DIR`, and ask before submit, deploy, payment,
production writes, external sends, or data migrations.
"""
