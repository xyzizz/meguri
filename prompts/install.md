# Meguri Prompt Install

Copy this into Codex or Claude Code while the current working directory is the
target project:

```text
Install Meguri in this current project and continue in this same AI session.

Use the active Codex / Claude Code session to finish setup and inspection.

From the current project root, run:
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash -s -- --init --install-skills

After installation:
1. Start the Meguri inspect workflow in this same AI session.
2. Follow the printed Meguri inspect specification.
3. Create `.meguri/project-inspect.json` and `.meguri/project-brief.md` from project evidence.
4. If the project goal, execution entry, pass criteria, credentials, data setup, or forbidden side effects are unclear, ask me concrete questions before writing scenarios or tests.
5. If enough information is available, design the first deterministic dry-run verification scenario, validate the Meguri pack, then run the safe scenario.
6. Do not submit, deploy, pay, write to production, send external messages, or run migrations unless I explicitly approve.
```

Future use after installation:

```text
Claude Code: /meguri inspect
Codex: /skills, then choose meguri
Codex: $meguri inspect
Codex prompt after restart: /prompts:meguri inspect
```

If the newly installed entrypoint does not appear, restart Codex / Claude Code
or open a new session in the same project.
