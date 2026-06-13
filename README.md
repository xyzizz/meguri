# Meguri

Agent-facing verification harness for Codex and Claude Code.

Meguri is not a standalone project-understanding engine. It provides the local
specification, file layout, deterministic validation, run execution, and reports
that keep Codex / Claude Code grounded while the AI designs project-specific
test workflows.

## Quick Start

In a Codex terminal, install Meguri and initialize the current target project:

```bash
cd /path/to/target-project
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash -s -- --init --install-skills
meguri inspect
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
```

`meguri inspect` asks the AI agent to create:

```text
.meguri/
  prompts/inspect.md
  project-inspect.json
  project-brief.md
```

`meguri inspect` calls the installed AI agent CLI. By default it prefers
`codex exec`, then `claude -p`, and falls back to printing the prompt if neither
agent is available.

Inside an active Codex conversation, use:

```text
$meguri 为当前项目设计测试流程。先 inspect，信息不够先问我，最后写入场景并验证。
```

Inside Claude Code, use:

```text
/meguri 为当前项目设计测试流程。先 inspect，信息不够先问我，最后写入场景并验证。
```

Skills run `meguri inspect --agent prompt` so the current agent follows the same
Meguri specification without recursively launching another agent.

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
meguri inspect [--agent auto|codex|claude|prompt]
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
