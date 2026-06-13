# Evidence Timeline Report Design

## Context

Meguri already writes `run.json`, `report.md`, and `index.html` for each loop
run. The current report is useful for command-level results, but it is too thin
for AI workflow verification. In real usage, a run may include user messages,
model replies, tool calls, checks, repairs, and reruns. Users need to inspect
that chain in chronological order and verify that the result was produced by a
real workflow rather than a vague summary.

This design adds structured evidence files and an attempt-based timeline view to
the generated HTML report. The feature stays local-first and self-contained.

## Goals

- Show the full AI verification event flow in time order.
- Group events by attempt so failure, repair, and rerun chains are clear.
- Let users click each timeline event and inspect input, output, checks, and
  linked artifacts.
- Redact sensitive content by default while preserving local artifact access.
- Provide loop replay: one captured run can be replayed to reproduce the issue or
  retried after a fix.
- Keep existing Meguri loops and reports working when no structured evidence is
  present.

## Non-Goals

- Do not make the HTML page execute local commands.
- Do not require all project scripts to stream JSON through stdout.
- Do not replace existing `run.json`, `report.md`, or step/check reporting.
- Do not build live report updates in this phase.

## Evidence File Protocol

Verification scripts write structured evidence files. Meguri reads those files
after a run step completes and before rendering the final report.

Supported input locations:

```text
.meguri/runs/<run_id>/evidence/*.json
.meguri/evidence/*.json
```

The run-local evidence directory has priority. Project-level evidence is allowed
for scripts that cannot easily know the active `run_id`; Meguri copies those
files into the current run directory before linking them from the report.
Project-level evidence is eligible only when it matches the current `loop_id`
and was modified after the current run started, or when it explicitly declares
the current `run_id`. This avoids carrying stale evidence from an earlier run
into the new report.

Evidence file shape:

```json
{
  "version": 1,
  "run_id": "run_20260613_152717_168e0b82",
  "loop_id": "agent_multiturn_no_submit",
  "attempts": [
    {
      "id": "attempt_1",
      "title": "Real agent multi-turn verification",
      "status": "pass",
      "events": [
        {
          "id": "turn_1_user",
          "type": "user_input",
          "time": "2026-06-13T15:27:18+08:00",
          "title": "User turn 1",
          "status": "pass",
          "input": "Copy campaign 123 to staging account 456",
          "output": null,
          "checks": [],
          "artifacts": []
        },
        {
          "id": "turn_1_model",
          "type": "model_output",
          "time": "2026-06-13T15:27:24+08:00",
          "title": "Model reply 1",
          "status": "pass",
          "input": "Copy campaign 123 to staging account 456",
          "output": "I found the source campaign and will prepare a safe preview.",
          "checks": [
            {
              "id": "no_submit_commit",
              "status": "pass",
              "message": "submit_commit was not called"
            }
          ],
          "artifacts": [
            {
              "label": "Raw response",
              "path": "evidence/raw_turn_1.json"
            }
          ]
        }
      ]
    }
  ]
}
```

Initial event types:

```text
user_input
model_output
tool_call
check
repair
rerun
artifact
note
```

Unknown event types are accepted and rendered as `note`-style neutral events,
with a warning in the report metadata.

## Data Model Changes

Add evidence-specific dataclasses or typed dictionaries under `meguri/core`:

- `EvidenceBundle`: source file, loop id, attempts.
- `EvidenceAttempt`: id, title, status, ordered events.
- `EvidenceEvent`: id, type, time, title, status, input, output, checks,
  artifacts, metadata.
- `ReplayBundle`: loop id, scenario path, command, project ref, inputs, and
  redacted environment summary.

`RunReport` gains:

```python
evidence: list[EvidenceBundle]
evidence_warnings: list[str]
replay: dict[str, Any] | None
```

Existing consumers of `RunReport.to_dict()` remain compatible because these are
additive fields.

## Runner Behavior

During `run_scenario`, Meguri should:

1. Create the run artifact directory as it does today.
2. Execute each step through the configured adapter.
3. Persist stdout, stderr, and result artifacts as it does today.
4. Scan evidence inputs after each step and again before final report rendering.
5. Copy project-level evidence files into `.meguri/runs/<run_id>/evidence/`.
6. Ignore project-level evidence that does not match the current loop or run
   window, and record a warning when skipped files look related.
7. Parse valid evidence files into `RunReport.evidence`.
8. Record parse, schema, and missing-artifact problems as warnings rather than
   failing an otherwise valid run.
9. Write `replay.json` into the run directory.
10. Render Markdown and HTML using evidence when available.

The environment should expose the run directory to scripts:

```text
MEGURI_RUN_ID=<run_id>
MEGURI_ARTIFACT_DIR=<absolute run dir>
MEGURI_EVIDENCE_DIR=<absolute run dir>/evidence
```

Scripts can then write evidence directly to the run-local evidence directory.

## HTML Report Design

The report keeps the existing summary header. The main evidence view is
`Attempt Timeline`.

Desktop layout:

```text
Run Summary

Attempt 1: Real agent multi-turn verification        PASS
○──○──○──○──○──○
1  2  3  4  5  6

Attempt 2: Repair and rerun                          PASS
○──○──○──○
1  2  3  4

[timeline area]                         [fixed detail panel]
```

Mobile layout stacks the selected event detail below the timeline.

Timeline behavior:

- Each attempt renders as one horizontal chain of circular event nodes.
- Events are sorted by `time`; events without `time` keep file order.
- The initial selected event is the first failed or blocked event. If none
  exists, select the first event.
- Event nodes use short labels or icons only. Long text appears in the detail
  panel.
- The detail panel shows title, event type, time, status, input, output,
  checks, and artifact links.

Status colors:

```text
pass      green
fail      red
blocked   amber
warning   yellow
neutral   gray
active    outline/highlight
```

If no structured evidence exists, the report falls back to the current
step/check/stdout/stderr view and displays:

```text
No structured evidence file found.
```

If an evidence file cannot be parsed, the HTML shows an evidence parse warning
and still renders the existing step report.

## Redaction

The report applies two redaction layers.

First, evidence can explicitly mark content as redacted:

```json
{
  "output": {
    "text": "Bearer sk-example",
    "redacted": true,
    "redacted_label": "LLM API token"
  }
}
```

The HTML displays:

```text
[redacted: LLM API token]
```

Second, Meguri automatically redacts common secret patterns before rendering
HTML:

- Authorization headers.
- API keys and bearer tokens.
- Cookies.
- `password`, `passwd`, `secret`, `token`, and `api_key` fields.
- DSN password segments.

The generated report shows redacted content by default. Raw local artifacts may
still contain original data if the verification script wrote them, so the report
must label raw artifact links clearly.

## Loop Replay

Each run writes:

```text
.meguri/runs/<run_id>/replay.json
```

Replay bundle shape:

```json
{
  "version": 1,
  "source_run_id": "run_20260613_152717_168e0b82",
  "loop_id": "agent_multiturn_no_submit",
  "scenario_path": ".meguri/scenarios/agent_multiturn_no_submit.yaml",
  "command": ["sh", "-lc", ".venv/bin/python .meguri/scripts/verify.py"],
  "project_ref": {
    "git_commit": "abc1234",
    "dirty": true
  },
  "inputs": [
    {
      "source": "evidence",
      "path": "evidence/agent_multiturn.json"
    }
  ],
  "environment": {
    "python": ".venv/bin/python",
    "redacted_env": ["OPENAI_API_KEY", "DATABASE_URL"]
  },
  "replay": {
    "status": "partial",
    "missing": ["LLM credentials", "staging database"]
  }
}
```

Loop replay is the one-click action behind both reproduction and retry. The HTML
does not run local commands itself; it exposes copy buttons for the active
Codex/Claude Code session to run.

For normal reruns without captured input:

```bash
meguri run agent_multiturn_no_submit
```

For replaying a captured loop run:

```bash
meguri run agent_multiturn_no_submit --replay .meguri/runs/<run_id>/replay.json
```

For retrying after a fix, the copied command keeps the same replay input and
records the previous run as the retry source:

```bash
meguri run agent_multiturn_no_submit --replay .meguri/runs/<run_id>/replay.json --retry-of <run_id>
```

`--replay` loads the replay bundle, exposes it to the loop as
`MEGURI_REPLAY_FILE`, and records the replay source in the new run. Meguri does
not pretend it can recreate missing credentials, external services, or
production data. The loop script is responsible for using the replay bundle to
drive deterministic inputs when possible.

`--retry-of` marks the new run as a post-fix retry of an earlier run. The new
report should link back to the source run, and the source report should be able
to show the retry command and, when available, the follow-up run id. This makes
the loop chain auditable:

```text
original run -> failed/blocked event -> fix -> retry with same replay bundle -> pass/block
```

Replay status:

```text
full       enough command/input/environment metadata exists for a rerun
partial    command/input exists but credentials or external systems are missing
none       no structured evidence or replay entry exists
```

## Markdown Report

`report.md` should stay compact. It includes:

- Run summary.
- Evidence bundle count.
- Attempt summaries.
- Failed or blocked event summaries.
- Replay command and retry command, if available.

It should not inline full conversations by default.

## Validation

`meguri validate` should accept existing packs and add warnings for evidence
features only when relevant:

- Warn when scenario metadata declares evidence support but no evidence schema
  can be parsed after a sample run.
- Validate artifact paths inside evidence files when the files exist.
- Warn on unknown event types, duplicate event IDs in the same attempt, and
  missing attempt IDs.

Validation must not reject old scenarios for lacking evidence.

## Testing

Add focused tests for:

- Parsing a valid evidence file with multiple attempts.
- Preserving event order by time and file order fallback.
- Rendering an HTML timeline when evidence exists.
- Falling back to the legacy step view when evidence is absent.
- Showing evidence parse warnings without failing report generation.
- Redacting explicit redacted objects and common secret patterns.
- Writing `replay.json` with source run id, scenario path, command, project ref,
  inputs, and replay status.
- Rendering copyable replay and post-fix retry commands without embedding
  command execution.

## Open Decisions Closed

- Timeline granularity is complete event flow, not only Meguri steps.
- Evidence is collected from files, not stdout.
- Attempts are grouped, not rendered as one flat global timeline.
- Event details use a fixed right-side panel on desktop.
- Details show input/output, checks, and artifact links.
- Redaction uses both script-provided flags and automatic secret masking.
- One-click reproduction is loop replay: copyable replay and retry commands plus
  a replay bundle, not HTML-side execution.
