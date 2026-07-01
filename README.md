# Meguri

Languages: English | [简体中文](README.zh-CN.md)

Agent-facing verification harness for Codex and Claude Code.

Meguri is a project-local loop workflow for the active Codex / Claude Code
session. It gives the AI a stable way to inspect a project, design deterministic
verification loops, run them safely, repair when appropriate, rerun, and leave an
auditable report.

Meguri does not understand your project by itself. The AI in the current
terminal session does that work; Meguri provides the structure, safety rules,
execution, and records.

## Quick Start

Open Codex or Claude Code in the target project, then invoke `/meguri` and ask:

```text
Initialize this project with Meguri.
Update Meguri.
Add a verification loop for <goal>.
Run all verification.
Open the latest report.
```

For a fresh project, you can paste this install prompt into Codex or Claude Code:

```text
Install Meguri in this project and enable the Codex / Claude Code slash entrypoint.

Run:
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash

After installation, invoke /meguri and ask:
Initialize this project with Meguri.
Update Meguri.
```

A fuller copyable install prompt lives in
[`prompts/install.md`](prompts/install.md).

If the newly installed entrypoint does not appear, restart Codex / Claude Code
or open a new session in the same project, then type `/` and search `meguri`.

`meguri init` initializes the project pack. `meguri refresh` updates
Meguri-owned agent entrypoints from the official repository. When network access
is unavailable, run `meguri refresh --offline` to use the bundled templates.

## What It Creates

The installer creates the project workflow files:

```text
.meguri/
  project.yaml
  generated/inspect.md
  loops/smoke/_loop.yaml
  scenarios/smoke.yaml
  README.md
.agents/skills/meguri/SKILL.md
.claude/skills/meguri/SKILL.md
.claude/commands/meguri.md
~/.codex/prompts/meguri.md
```

Meguri writes run records inside the target project:

```text
.meguri/
  batches/<batch_id>/
    batch.json
    index.html
  loops/<loop_id>/
    _loop.yaml
    index.html
    <YYYYMMDD_HHMMSS>/
      timeline.ndjson
      run.json
      report.md
      index.html
      replay.json
      evidence/
      steps/<step_id>/stdout.txt
      steps/<step_id>/stderr.txt
      steps/<step_id>/result.json
```

## Loop

A loop is Meguri's user-facing unit. It is not just a test flow; it is the full
completion chain:

```text
goal -> safe execution -> deterministic checks -> evidence -> repair when safe -> rerun -> pass / blocked / ask
```

New loops live under `.meguri/loops/<loop_id>/_loop.yaml`. Each run creates a
timestamped `.meguri/loops/<loop_id>/<YYYYMMDD_HHMMSS>/` record. Multi-loop
sequential runs create `.meguri/batches/<batch_id>/` records.

Use natural language through `/meguri` to initialize the project, add or remove
loops, run verification, and open reports. The agent edits Meguri-owned loop
files directly when the request is clear, and asks questions when the goal,
safe execution entry, pass criteria, credentials, data setup, or forbidden side
effects are unclear.

## CLI Bottom Layer

The public CLI surface is intentionally small:

```text
meguri init
meguri refresh
meguri run <loop>
meguri run <loop1> <loop2>
meguri run all
meguri report [run_or_batch_id]
```

`init` initializes or repairs the project pack. `refresh` updates Meguri-owned
agent entrypoints from the official repository; `meguri refresh --offline` uses
bundled templates when network access is unavailable. `run` executes one named
loop, an explicit sequence, or all user loops. `report` is read-only and returns
the latest report or the requested run or batch report.

## Workflow Rules

- Let Codex / Claude Code inspect the repo, read existing tests/scripts/docs,
  and write project-specific loops or helper tests.
- Keep new loops in `dry_run` unless the user explicitly approves execute mode.
  After approval, execute-mode runs require the `--allow-execute` confirmation
  marker.
- Never treat an LLM self-evaluation as a passing check. Passing evidence should
  come from commands, structured output, logs, artifacts, screenshots, or files.
- When writing helper or verifier scripts, emit structured evidence into
  `MEGURI_EVIDENCE_DIR` even on exceptions, including partial input/output,
  errors, traceback, and artifact links.
- Ask before enabling submit, deploy, payment, production writes, external
  sends, or data migrations.

## Development

From this repository:

```bash
python3 -m pip install -e '.[dev]'
pytest -q
```
