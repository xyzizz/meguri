# Meguri

Agent-facing verification harness for Codex and Claude Code.

Meguri is a local-first CLI plus project-local workflow files. It gives the
active Codex / Claude Code session a stable way to inspect a project, design
deterministic verification flows, run them safely, and leave an auditable report.

Meguri does not understand your project by itself. The AI in the current terminal
session does that work; Meguri provides the structure, safety rules, validation,
execution, and records.

## Quick Start

Open Codex or Claude Code in the target project, then paste:

```text
Install Meguri in this project and continue in this same AI session.

Run:
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash -s -- --init --install-skills

After installation, run `meguri inspect`, follow the printed Meguri spec, and
write `.meguri/project-inspect.json` plus `.meguri/project-brief.md`.

If the project goal, execution entry, pass criteria, credentials, data setup, or
forbidden side effects are unclear, ask me concrete questions before writing
scenarios or tests.
```

A fuller copyable install prompt lives in
[`prompts/install.md`](prompts/install.md).

After setup, use Meguri from the active AI session:

```text
/meguri inspect
```

## What It Installs

`meguri init --install-skills` creates:

```text
.meguri/
  project.yaml
  scenarios/smoke.yaml
  README.md
.agents/skills/meguri/SKILL.md
.claude/skills/meguri/SKILL.md
~/.codex/prompts/meguri.md
```

Run records stay inside the target project:

```text
.meguri/runs/<run_id>/
  run.json
  report.md
  index.html
  steps/<step_id>/stdout.txt
  steps/<step_id>/stderr.txt
  steps/<step_id>/result.json
```

The HTML report is self-contained and uses relative links, so the run directory
can be archived or shared.

## Commands

| Command | Purpose |
| --- | --- |
| `meguri init --install-skills` | Create the project pack and Codex / Claude Code entrypoints. |
| `meguri inspect` | Print the inspection spec for the active AI session and save it to `.meguri/prompts/inspect.md`. |
| `meguri add "flow" --command "..." --pass-criteria "..."` | Add a scenario draft when the goal, safe execution entry, and deterministic pass criteria are clear. |
| `meguri validate [scenario]` | Validate the project pack or a scenario alias/path. |
| `meguri run [scenario] --open` | Run a scenario and write `run.json`, `report.md`, and `index.html`. Defaults to `smoke`. |
| `meguri report --last --open` | Open the newest local HTML report. |

`add` is intentionally conservative. If the request is ambiguous or missing a
safe command or deterministic pass criteria, it asks for clarification, writes
nothing, and exits with code `2`.

## Workflow Rules

- Let Codex / Claude Code inspect the repo, read existing tests/scripts/docs, and
  write project-specific scenarios or helper tests.
- Keep new scenarios in `dry_run` unless the user explicitly approves execute
  mode.
- Never treat an LLM self-evaluation as a passing check. Passing evidence should
  come from commands, structured output, logs, artifacts, screenshots, or files.
- Ask before enabling submit, deploy, payment, production writes, external sends,
  or data migrations.
- After changes, run `meguri validate` and the relevant `meguri run <scenario>`
  when safe.

## Install Without Project Setup

To install only the CLI:

```bash
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash
```

Then initialize any target project later:

```bash
meguri init --install-skills
```

## Development

From this repository:

```bash
python3 -m pip install -e '.[dev]'
pytest -q
```
