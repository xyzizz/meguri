# Meguri Prompt Install

Copy this into Codex or Claude Code while the current working directory is the
target project:

```text
Install Meguri in this project and enable the Codex / Claude Code slash entrypoint.

From the current project root, run:
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash

After installation, run:
/meguri init
```

If `meguri` does not appear in the slash menu yet, restart Codex / Claude Code
or open a new session in this project, then type `/` and search `meguri`.

```text
Claude Code: type `/`, search `meguri`, choose `/meguri`
Codex: restart/open a new session, type `/`, search `meguri`, choose `prompts:meguri`
Codex alternatives: `/skills` -> `meguri`, or `$meguri init`
```

For an existing project update, keep the same installer and then refresh the
generated project entrypoints and indexes from the AI terminal:

```text
Update Meguri in this project.

Run:
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash

After the installer finishes, run:
/meguri upgrade --skills --refresh-index
```
