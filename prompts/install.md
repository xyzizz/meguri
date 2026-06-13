# Meguri Prompt Install

Copy this into Codex or Claude Code while the current working directory is the
target project:

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

Future use after installation:

```text
Run `meguri inspect` and follow the printed Meguri spec.
```

Claude Code exposes the project skill directly as `/meguri`. Codex installs the
same workflow as a project skill plus a user prompt named `meguri`. In Codex,
use `/skills` to choose `meguri`, type `$meguri inspect`, or restart/open a new
session and use `/prompts:meguri inspect`.
