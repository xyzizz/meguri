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
  index.html
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

The project index lists loops and multi-loop batch records, the loop index
lists historical run records, and each run report is self-contained with
relative links. Multi-loop runs create `.meguri/batches/<batch_id>/batch.json`
and `index.html` when the batch starts, refresh them whenever the current loop
writes a running snapshot, refresh again after each loop completes, and finalize
them at the end. While a loop is still running, the batch record exposes
`current_run` with the live report path and current step. If a multi-loop run is
interrupted, the batch record is finalized as blocked with `interrupted`
metadata and the remaining loop list. The batch report links to every completed
loop report in execution order, extracts structured metrics such as turn count,
submitted, closed-status verification, and submit success/failure counts, and
groups repeated failure reasons across loops when deterministic evidence exposes
them. Batch run summaries include each loop's mode, so execute risk stays visible
in the report. Batch reports also include `status_counts` for the overall
pass/fail/blocked distribution, `failed_loops` for failed or blocked loops,
`retry_loops` plus a project-root retry command for failed, blocked, or
unfinished loops. If the original batch was explicitly approved for execute mode,
the retry command preserves
`--allow-execute`.
`timeline.ndjson` is an append-only event stream written as the loop and each
step progress. `run.json`, `report.md`, and `index.html` are written when a loop
starts, refreshed when each step starts or completes, and shell step
stdout/stderr artifacts are updated while the command is still running. Long
runs can be inspected before the final step finishes. `run.json.updated_at`
changes on every snapshot refresh so a viewer can poll progress safely.
If a run is interrupted, Meguri preserves the last active step as blocked,
appends a `run_interrupted` timeline event, and leaves the report readable.
`run.json` and command
JSON output keep stdout/stderr excerpts plus byte counts; full streams stay in
the step artifacts. If a step's structured stdout declares `evidence_json` or
`evidence_markdown` files under the run directory, Meguri links them as step
artifacts. Replay metadata also captures the pre-run git branch,
commit, dirty flag, and dirty file list so a report can be audited against the
exact project state that produced it. Each run report shows a Replay command
that is runnable from the project root, reuses the run-local `replay.json`, and
marks the retry with `--retry-of`, so repairs can be rerun without
reconstructing the command from memory. Legacy
`.meguri/scenarios/*.yaml` loop files remain runnable for compatibility; their
new records are written under `.meguri/loops/<loop_id>/`. Existing
`.meguri/runs/<run_id>/` reports remain readable.

## Loop

A loop is Meguri's user-facing unit. It is not just a test flow; it is the full
completion chain:

```text
goal -> safe execution -> deterministic checks -> evidence -> repair when safe -> rerun -> pass / blocked / ask
```

New loops live under `.meguri/loops/<loop_id>/_loop.yaml`. Each run creates a
timestamped `.meguri/loops/<loop_id>/<YYYYMMDD_HHMMSS>/` record. Legacy
`.meguri/scenarios/*.yaml` files remain runnable and write new records into the
loop history structure.

## AI Workflows

Ask Codex / Claude Code to use Meguri for:

| Workflow | What the active AI does |
| --- | --- |
| Inspect | Reads the project and creates the inspection artifacts. |
| Add loop | Designs a deterministic loop only after the goal, safe execution entry, and pass criteria are clear. |
| List loops | Shows how many user-added loops exist in the current project. |
| Delete loop | Removes a named user-added loop. |
| Validate | Checks the project pack, loops, adapter references, skill files, and run configuration. |
| Run | Executes one loop, several named loops, or all user-added loops with exclusions; writes running snapshots and keeps shell stdout/stderr artifacts live. Execute-mode loops require explicit approval. |
| Report | Opens reports, lists running reports, prints single-run JSON summaries with evidence/replay pointers, groups recent standalone runs, or groups explicit run ids/paths into a batch report. |

```text
Examples:
/meguri inspect
$meguri inspect
Use Meguri to add a loop for checkout.
Use Meguri to list loops.
Use Meguri to delete the checkout loop.
Use Meguri to validate and run the smoke loop.
Use Meguri to run all loops except checkout.
Use Meguri to list running reports as JSON.
Use Meguri to summarize this run id as JSON.
Use Meguri to summarize the latest 7 run reports.
Use Meguri to summarize the latest 7 run reports as JSON.
Use Meguri to summarize these exact run report paths as JSON.
Use Meguri to open the latest report.
```

Adding a loop is intentionally conservative. If the request is ambiguous
or missing a safe execution entry or deterministic pass criteria, Meguri asks
for clarification and writes nothing.

## Workflow Rules

- Let Codex / Claude Code inspect the repo, read existing tests/scripts/docs, and
  write project-specific loops or helper tests.
- Keep new loops in `dry_run` unless the user explicitly approves execute
  mode. After approval, run execute-mode loops with the `--allow-execute`
  confirmation marker.
- Never treat an LLM self-evaluation as a passing check. Passing evidence should
  come from commands, structured output, logs, artifacts, screenshots, or files.
- When writing helper or verifier scripts, emit structured evidence into
  `MEGURI_EVIDENCE_DIR` even on exceptions, including partial input/output,
  errors, traceback, and artifact links.
- Ask before enabling submit, deploy, payment, production writes, external sends,
  or data migrations.
- After changes, validate the Meguri pack and run the relevant safe loop.

## Development

From this repository:

```bash
python3 -m pip install -e '.[dev]'
pytest -q
```
