from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from meguri.project.pack import ProjectPack, find_project_pack


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

    print(f"meguri: wrote {prompt_path.relative_to(pack.project_root)}", file=sys.stderr)
    print(prompt)
    return 0


def build_inspect_prompt(pack: ProjectPack) -> str:
    project_root = pack.project_root
    pack_root = pack.pack_root
    return f"""You are the current Codex / Claude Code agent. You are running Meguri inspect for this repository.

Meguri is a specification and harness layer, not a model runner. It must not
launch another AI agent for this task. Meguri owns the local specification, file
layout, deterministic validation, scenario execution, and reports. Project
understanding, test-flow design, and any code/test authoring must be done by you,
the current AI agent in this session.

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
