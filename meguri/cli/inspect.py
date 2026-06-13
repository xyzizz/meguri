from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

from meguri.project.pack import ProjectPack, find_project_pack


AgentName = Literal["auto", "codex", "claude", "prompt"]


def handle_inspect(args: Any) -> int:
    try:
        pack = find_project_pack(Path.cwd())
    except FileNotFoundError:
        print("Cannot inspect this project yet: no .meguri/ pack found.", file=sys.stderr)
        print("Run meguri init --install-skills first, then retry meguri inspect.", file=sys.stderr)
        return 2

    prompt = build_inspect_prompt(pack)
    prompt_path = pack.pack_root / "prompts" / "inspect.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")

    agent = _resolve_agent(args.agent)
    if agent == "prompt":
        print(prompt)
        print(f"\n# Prompt written to {prompt_path.relative_to(pack.project_root)}", file=sys.stderr)
        return 0

    command = _agent_command(agent, pack.project_root, prompt, args)
    print(f"meguri: wrote {prompt_path.relative_to(pack.project_root)}", file=sys.stderr)
    print(f"meguri: invoking {agent} model for project inspection", file=sys.stderr)
    result = subprocess.run(command, cwd=pack.project_root, check=False)  # noqa: S603
    if result.returncode != 0:
        print(f"meguri: {agent} inspect failed with exit code {result.returncode}", file=sys.stderr)
    return result.returncode


def build_inspect_prompt(pack: ProjectPack) -> str:
    project_root = pack.project_root
    pack_root = pack.pack_root
    return f"""You are running Meguri inspect for this repository.

Meguri is an agent-facing verification harness. Meguri itself only owns the
specification, file layout, deterministic validation, run execution, and reports.
Project understanding, test-flow design, and any code/test authoring must be done
by the AI agent in this session.

Repository root:
{project_root}

Meguri pack:
{pack_root}

Your task:
1. Inspect the existing project by reading relevant local files:
   - README or project docs
   - AGENTS.md, CLAUDE.md, or other local agent instructions
   - package.json, pyproject.toml, go.mod, Cargo.toml, or equivalent manifests
   - tests, scripts, CI config, app entrypoints, and existing verification helpers
2. Infer the current test surface and verification gaps from evidence in the repo.
3. Do not treat your own opinion as a pass/fail signal. Meguri scenarios must use
   deterministic commands, logs, structured output, artifacts, screenshots, or files.
4. Do not perform submit, deploy, payment, production write, external send, or data
   migration actions. If a workflow requires them, mark it as blocked or ask.
5. During inspect, write only under `.meguri/`. Do not edit source code, tests, or
   scenarios yet unless the user explicitly asked for implementation beyond inspect.

Write these files:

`.meguri/project-inspect.json`
```json
{{
  "version": 1,
  "status": "ready | needs_confirmation | blocked",
  "project": {{
    "name": "string",
    "type": "string",
    "main_languages": ["string"],
    "frameworks": ["string"],
    "package_managers": ["string"]
  }},
  "evidence": {{
    "docs": ["relative/path"],
    "manifests": ["relative/path"],
    "tests": ["relative/path"],
    "scripts": ["relative/path or script name"],
    "ci": ["relative/path"],
    "entrypoints": ["relative/path"]
  }},
  "candidate_test_commands": [
    {{
      "name": "string",
      "command": ["string"],
      "why": "deterministic reason"
    }}
  ],
  "recommended_scenarios": [
    {{
      "name": "snake_case",
      "user_goal": "string",
      "execution_entry": "command or adapter entry",
      "pass_criteria": "deterministic evidence required",
      "mode": "dry_run",
      "forbidden_side_effects": [
        "submit",
        "deploy",
        "payment",
        "production write",
        "external send"
      ],
      "missing_information": ["string"]
    }}
  ],
  "questions": ["concrete question for the user when required"],
  "risk_notes": ["string"],
  "next_actions": ["string"]
}}
```

`.meguri/project-brief.md`
- A concise, audit-friendly brief for a human and future agents.
- Include detected project shape, evidence read, recommended scenarios, missing
  information, risk boundaries, and the next Meguri commands to run.

After writing the files:
1. If `questions` is non-empty, stop and ask the user those questions.
2. If status is `ready`, suggest the smallest next implementation step.
3. Do not run `meguri add`, write scenarios, or edit tests during inspect unless
   the user explicitly asked you to continue beyond inspection.
"""


def _resolve_agent(requested: AgentName) -> Literal["codex", "claude", "prompt"]:
    if requested == "prompt":
        return "prompt"
    if requested == "codex":
        if shutil.which("codex"):
            return "codex"
        print("meguri: codex CLI not found; printing prompt instead", file=sys.stderr)
        return "prompt"
    if requested == "claude":
        if shutil.which("claude"):
            return "claude"
        print("meguri: claude CLI not found; printing prompt instead", file=sys.stderr)
        return "prompt"
    if shutil.which("codex"):
        return "codex"
    if shutil.which("claude"):
        return "claude"
    print("meguri: no codex or claude CLI found; printing prompt instead", file=sys.stderr)
    return "prompt"


def _agent_command(agent: Literal["codex", "claude"], project_root: Path, prompt: str, args: Any) -> list[str]:
    if agent == "codex":
        command = [
            "codex",
            "exec",
            "--sandbox",
            args.sandbox,
            "-C",
            str(project_root),
        ]
        if args.skip_git_repo_check:
            command.append("--skip-git-repo-check")
        command.append(prompt)
        return command
    return [
        "claude",
        "-p",
        "--permission-mode",
        args.claude_permission_mode,
        prompt,
    ]
