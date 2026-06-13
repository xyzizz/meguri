# Meguri

Languages: English | [简体中文](README.zh-CN.md)

Agent-facing verification harness for Codex and Claude Code.

Meguri is a project-local loop workflow for the active Codex / Claude Code
session. It gives the AI a stable way to inspect a project, design deterministic
verification loops, run them safely, repair when appropriate, rerun, and leave an
auditable report.

Meguri does not understand your project by itself. The AI in the current terminal
session does that work; Meguri provides the structure, safety rules, validation,
execution, and records.

## Quick Start

Open Codex or Claude Code in the target project, then paste:

```text
Install Meguri in this project and enable the Codex / Claude Code slash entrypoint.

Run:
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash -s -- --init --install-skills

After installation, run:
/meguri inspect
```

A fuller copyable install prompt lives in
[`prompts/install.md`](prompts/install.md).

After setup, use Meguri from the AI terminal:

```text
Claude Code: type `/`, search `meguri`, choose `/meguri`
Codex: restart/open a new session, type `/`, search `meguri`, choose `prompts:meguri`
Codex alternatives: `/skills` -> `meguri`, or `$meguri inspect`
```

If the newly installed entrypoint does not appear, restart Codex / Claude Code
or open a new session in the same project.

## What It Creates

The installer creates the project workflow files:

```text
.meguri/
  project.yaml
  scenarios/smoke.yaml
  README.md
.agents/skills/meguri/SKILL.md
.claude/skills/meguri/SKILL.md
.claude/commands/meguri.md
~/.codex/prompts/meguri.md
```

Meguri writes run records inside the target project:

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

## Loop

A loop is Meguri's user-facing unit. It is not just a test flow; it is the full
completion chain:

```text
goal -> safe execution -> deterministic checks -> evidence -> repair when safe -> rerun -> pass / blocked / ask
```

Loops are currently stored as `.meguri/scenarios/*.yaml` for runner
compatibility.

## AI Workflows

Ask Codex / Claude Code to use Meguri for:

| Workflow | What the active AI does |
| --- | --- |
| Inspect | Reads the project and creates the inspection artifacts. |
| Add loop | Designs a deterministic loop only after the goal, safe execution entry, and pass criteria are clear. |
| Validate | Checks the project pack, loops, adapter references, skill files, and run configuration. |
| Run | Executes the selected loop and writes `run.json`, `report.md`, and `index.html`. |
| Report | Opens or summarizes the newest local HTML report. |

```text
Examples:
/meguri inspect
$meguri inspect
Use Meguri to add a loop for checkout.
Use Meguri to validate and run the smoke loop.
Use Meguri to open the latest report.
```

Adding a loop is intentionally conservative. If the request is ambiguous
or missing a safe execution entry or deterministic pass criteria, Meguri asks
for clarification and writes nothing.

## Workflow Rules

- Let Codex / Claude Code inspect the repo, read existing tests/scripts/docs, and
  write project-specific loops or helper tests.
- Keep new loops in `dry_run` unless the user explicitly approves execute
  mode.
- Never treat an LLM self-evaluation as a passing check. Passing evidence should
  come from commands, structured output, logs, artifacts, screenshots, or files.
- Ask before enabling submit, deploy, payment, production writes, external sends,
  or data migrations.
- After changes, validate the Meguri pack and run the relevant safe loop.

## Development

From this repository:

```bash
python3 -m pip install -e '.[dev]'
pytest -q
```
