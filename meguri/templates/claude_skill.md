---
name: meguri
description: Use when the user wants Claude Code to work through the /meguri natural-language verification workflow using only meguri init, meguri refresh, meguri run, and meguri report as the CLI bottom layer.
argument-hint: init|refresh|run|report [args]
disable-model-invocation: true
---

Requested Meguri workflow:
$ARGUMENTS

Meguri is an agent-facing verification workflow for the current project.
The normal user entrypoint is `/meguri`: interpret the user's natural-language
request, inspect the project yourself, edit Meguri-owned files when needed, and
use the CLI only as the deterministic bottom layer.

Public CLI surface:

- `meguri init`
- `meguri refresh`
- `meguri run <loop>`
- `meguri run <loop1> <loop2>`
- `meguri run all`
- `meguri report [run_or_batch_id]`

Natural-language workflow:

1. For setup requests such as "Initialize this project with Meguri", run
   `meguri init`, follow the printed inspection instructions in this same agent
   session, and write `.meguri/project-inspect.json` plus
   `.meguri/project-brief.md` from repository evidence.
2. For update requests such as "Update Meguri", run `meguri refresh` to update
   Meguri-owned agent entrypoints from the official repository. Use
   `meguri refresh --offline` only when network access is unavailable.
3. For requests such as "Add a verification loop for <goal>", read the project
   docs, manifests, tests, scripts, CI config, app entrypoints, and existing
   `.meguri/loops/*/_loop.yaml` files. If the goal, execution entry, pass
   criteria, credentials, data setup, or forbidden side effects are unclear,
   ask concrete questions before editing.
4. Add or change user loops by editing
   `.meguri/loops/<loop_id>/_loop.yaml` and any project-local helper scripts.
   Remove a user loop by deleting that loop directory only after the user has
   named it clearly.
5. For run requests, use `meguri run <loop>` for one loop,
   `meguri run <loop1> <loop2>` for an explicit sequence, or `meguri run all`
   for all user loops.
6. For report requests, use `meguri report [run_or_batch_id]`. Use report
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
