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
    _validate_templates(templates, require_terms_per_template=not offline)
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


def _validate_templates(templates: dict[str, str], *, require_terms_per_template: bool) -> None:
    missing = [spec.key for spec in ENTRYPOINT_SPECS if not templates.get(spec.key, "").strip()]
    if missing:
        raise SkillRefreshError(f"missing Meguri skill templates: {', '.join(missing)}")
    required = ("/meguri", "meguri init", "meguri run", "meguri report")
    if require_terms_per_template:
        for spec in ENTRYPOINT_SPECS:
            text = templates[spec.key]
            missing_terms = [term for term in required if term not in text]
            if missing_terms:
                raise SkillRefreshError(
                    f"Meguri skill template {spec.remote_name} is missing required terms: "
                    + ", ".join(missing_terms)
                )
        return

    combined = "\n".join(templates[spec.key] for spec in ENTRYPOINT_SPECS)
    missing_terms = [term for term in required if term not in combined]
    if missing_terms:
        raise SkillRefreshError(
            "Meguri skill templates are missing required terms: "
            + ", ".join(missing_terms)
        )


def bundled_templates() -> dict[str, str]:
    return {
        "codex_skill": _codex_skill(),
        "claude_skill": _claude_skill(),
        "claude_command": _claude_command(),
        "codex_prompt": _codex_slash_prompt(),
    }


_SIMPLIFIED_BODY = """Meguri is an agent-facing verification workflow for the current project.
The normal user entrypoint is `/meguri`: interpret the user's natural-language
request, inspect the project yourself, edit Meguri-owned files when needed, and
use the CLI only as the deterministic bottom layer.

Public CLI surface:

- `meguri init`
- `meguri run <loop>`
- `meguri run <loop1> <loop2>`
- `meguri run all`
- `meguri report [run_or_batch_id]`

Natural-language workflow:

1. For setup requests such as "Initialize this project with Meguri", run
   `meguri init`, follow the printed inspection instructions in this same agent
   session, and write `.meguri/project-inspect.json` plus
   `.meguri/project-brief.md` from repository evidence.
2. For requests such as "Add a verification loop for <goal>", read the project
   docs, manifests, tests, scripts, CI config, app entrypoints, and existing
   `.meguri/loops/*/_loop.yaml` files. If the goal, execution entry, pass
   criteria, credentials, data setup, or forbidden side effects are unclear,
   ask concrete questions before editing.
3. Add or change user loops by editing
   `.meguri/loops/<loop_id>/_loop.yaml` and any project-local helper scripts.
   Remove a user loop by deleting that loop directory only after the user has
   named it clearly.
4. For run requests, use `meguri run <loop>` for one loop,
   `meguri run <loop1> <loop2>` for an explicit sequence, or `meguri run all`
   for all user loops.
5. For report requests, use `meguri report [run_or_batch_id]`. Use report
   `--json` when structured data is needed and report `--open` when the user
   asks to open a report.

Safety rules:

- Keep loops in `dry_run` unless the user explicitly approves execute mode.
- Execute-mode runs require the `--allow-execute` confirmation marker.
- Never treat LLM self-evaluation as passing evidence.
- Passing evidence must be deterministic: commands, structured output, logs,
  artifacts, screenshots, or files.
- Helper and verifier scripts must write crash-safe structured evidence to
  `MEGURI_EVIDENCE_DIR`, including partial input/output, errors, traceback, and
  artifact paths even when the target app, command, or model response crashes.
- Ask before dangerous side effects, including submit, deploy, payment,
  production writes, external sends, or data migrations.
"""


def _codex_skill() -> str:
    return f"""---
name: meguri
description: Use when the user wants Codex to work through the /meguri natural-language verification workflow using only meguri init, meguri run, and meguri report as the CLI bottom layer.
---

{_SIMPLIFIED_BODY}"""


def _codex_slash_prompt() -> str:
    return f"""---
description: Meguri verification loop workflow for the current project
argument-hint: init|run|report [args]
---

Use `/meguri` for this request in the current Codex session: $ARGUMENTS

{_SIMPLIFIED_BODY}"""


def _claude_skill() -> str:
    return f"""---
name: meguri
description: Use when the user wants Claude Code to work through the /meguri natural-language verification workflow using only meguri init, meguri run, and meguri report as the CLI bottom layer.
argument-hint: init|run|report [args]
disable-model-invocation: true
---

Requested Meguri workflow:
$ARGUMENTS

{_SIMPLIFIED_BODY}"""


def _claude_command() -> str:
    return f"""---
description: Meguri verification loop workflow for the current project
argument-hint: init|run|report [args]
---

Use `/meguri` for this request in the current Claude Code session.

Requested Meguri workflow:
$ARGUMENTS

{_SIMPLIFIED_BODY}"""
