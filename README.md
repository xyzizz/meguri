# Meguri

Agent-facing verification harness for Codex and Claude Code.

Meguri is not a standalone project-understanding engine. It provides the local
specification, file layout, deterministic validation, run execution, and reports
that keep Codex / Claude Code grounded while the AI designs project-specific
test workflows.

## Quick Start

Open Codex or Claude Code in the target project, then paste this prompt:

```text
Install Meguri in this current project and continue in this same AI session.

Use the active Codex / Claude Code session to finish setup and inspection.

From the current project root, run:
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash -s -- --init --install-skills

After installation:
1. Run `meguri inspect`.
2. Follow the printed Meguri inspect specification yourself in this same AI session.
3. Create `.meguri/project-inspect.json` and `.meguri/project-brief.md` from project evidence.
4. If the project goal, execution entry, pass criteria, credentials, data setup, or forbidden side effects are unclear, ask me concrete questions before writing scenarios or tests.
5. If enough information is available, design the first deterministic dry-run verification scenario, run `meguri validate`, then run the safe scenario.
6. Do not submit, deploy, pay, write to production, send external messages, or run migrations unless I explicitly approve.
```

The canonical copyable prompt is versioned at
[`prompts/install.md`](prompts/install.md).

After that first setup, invoke Meguri from the active AI session:

```text
/meguri inspect
```

The shell command inside the prompt installs Meguri and initializes the current
target project:

```bash
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash -s -- --init --install-skills
```

If you only want to install the CLI:

```bash
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash
```

`init --install-skills` creates:

```text
.meguri/
  project.yaml
  scenarios/smoke.yaml
  README.md
.agents/skills/meguri/SKILL.md
.claude/skills/meguri/SKILL.md
~/.codex/prompts/meguri.md
```

`meguri inspect` prints the Meguri inspection specification for the current
Codex / Claude Code agent and writes the same specification to
`.meguri/prompts/inspect.md`. The current AI agent should then create:

```text
.meguri/
  prompts/inspect.md
  project-inspect.json
  project-brief.md
```

Meguri does not launch another model from inside `meguri inspect`.

Inside an active Codex conversation, use:

```text
/meguri inspect
```

Codex's documented reusable workflow surface is skills (`$meguri` or `/skills`)
and custom prompts (`/prompts:meguri`). Meguri installs both the repo skill and a
user prompt named `meguri`; on Codex builds that expose prompt names directly,
`/meguri inspect` works as the short form. If your Codex build shows the prompt
under the prompts namespace, use:

```text
/prompts:meguri inspect
```

Inside Claude Code, use:

```text
/meguri inspect
```

Skills run `meguri inspect` so the current agent follows the same Meguri
specification in the active Codex / Claude Code session.

From this repository, you can still run the bundled dapper examples directly:

```bash
python -m meguri.cli.main validate-scenario examples/dapper_assistant/scenarios/pre_submit_all_flows.yaml
python -m meguri.cli.main run examples/dapper_assistant/scenarios/pre_submit_smoke.yaml --runs-dir /tmp/meguri-runs --json
```

Run the complete dapper pre-submit coverage:

```bash
python -m meguri.cli.main run examples/dapper_assistant/scenarios/pre_submit_all_flows.yaml --runs-dir /tmp/meguri-runs --json
```

`pre_submit_all_flows.yaml` wraps the existing dapper verification scripts:

- `verify_skills_natural_agent_cards.py --json`
- `verify_batch_edit_agent_cards.py --json`
- `verify_copy_campaign_prompt_submit.py --json`

The scenario intentionally does not pass `--execute`, so it validates preview
and confirm nodes without sending final submit.

## Current Shape

- `meguri/core`: run models and artifact persistence.
- `meguri/scenarios`: YAML loading and scenario execution.
- `meguri/adapters`: generic shell adapter and dapper-specific adapter.
- `meguri/evaluators`: deterministic checks for exit codes, stdout JSON paths,
  and forbidden output.
- `meguri/project`: project pack discovery and scenario alias resolution.
- `meguri/reports`: Markdown and self-contained HTML report generation.
- `examples/dapper_assistant`: first project integration.

## Commands

```bash
meguri inspect
meguri init [--install-skills] [--force]
meguri add "flow description" --command "safe command" --pass-criteria "deterministic evidence"
meguri run [scenario-or-path] [--open] [--json]
meguri report [--last|run_id] [--open]
meguri validate [scenario-or-path]
```

By default, runs are stored in the target project:

```text
.meguri/runs/<run_id>/
  run.json
  report.md
  index.html
  steps/<step_id>/stdout.txt
  steps/<step_id>/stderr.txt
  steps/<step_id>/result.json
```

`add` is conservative. If the requested flow is ambiguous or missing a safe
execution entry or deterministic pass criteria, it asks for clarification and
writes nothing.

## Environment Notes

The dapper adapter expects `dapper_assistant/.venv/bin/python` to include the
project's optional Hermes dependencies. If missing, install from the
`dapper_assistant` directory:

```bash
.venv/bin/python -m pip install -e '.[hermes]'
```

If the company LLM proxy cannot be resolved or reached, the dapper steps are
reported as `blocked` rather than ordinary assertion failures.
