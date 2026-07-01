# Meguri Prompt Install

Copy this into Codex or Claude Code while the current working directory is the
target project:

```text
Install Meguri in this project and enable the Codex / Claude Code slash entrypoint.

From the current project root, run:
curl -fsSL https://raw.githubusercontent.com/xyzizz/meguri/main/install.sh | bash

After installation, invoke /meguri and ask:
Initialize this project with Meguri.
```

If `meguri` does not appear in the slash menu yet, restart Codex / Claude Code
or open a new session in this project, then type `/` and search `meguri`.

`meguri init` initializes the project pack. `meguri refresh` updates
Meguri-owned agent entrypoints from the official repository. If network access
is unavailable, run `meguri refresh --offline` to use the bundled templates.

Common `/meguri` requests:

```text
Initialize this project with Meguri.
Update Meguri.
Add a verification loop for <goal>.
Run all verification.
Open the latest report.
```

The public CLI bottom layer is:

```text
meguri init
meguri refresh
meguri run <loop>
meguri run <loop1> <loop2>
meguri run all
meguri report [run_or_batch_id]
```
