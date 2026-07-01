from __future__ import annotations

from pathlib import Path
from typing import Any

from meguri.project.pack import ProjectPack


def handle_inspect(args: Any) -> int:
    from meguri.cli.init import handle_init

    return handle_init(args)


def write_inspect_spec(pack: ProjectPack) -> tuple[Path, str]:
    prompt = build_inspect_prompt(pack)
    prompt_path = pack.pack_root / "generated" / "inspect.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path, prompt


def build_inspect_prompt(pack: ProjectPack) -> str:
    project_root = pack.project_root
    pack_root = pack.pack_root
    return f"""You are the current Codex / Claude Code agent. You are running Meguri init for this repository.

Meguri is a specification and harness layer. Its user-facing unit is a loop:
check evidence, repair when safe, rerun, then pass, block, or ask. Meguri owns
the local specification, file layout, deterministic validation, loop execution,
and reports. Use the active AI session for project understanding, loop design,
and any code/test authoring.

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
3. Do not treat your own opinion as a pass/fail signal. Meguri loops must use
   deterministic commands, logs, structured output, artifacts, screenshots, or files.
4. When a recommended loop needs helper/verifier code, specify that the helper
   must write structured JSON evidence to `MEGURI_EVIDENCE_DIR` in a `finally`
   path. Evidence must survive target app crashes, parser/schema failures, and
   model response errors by including partial input/output, errors, traceback,
   and artifact paths.
5. Do not perform submit, deploy, payment, production write, external send, or data
   migration actions. If a workflow requires them, mark it as blocked or ask.
6. During inspect, write only under `.meguri/`. Do not edit source code, tests, or
   loops yet unless the user explicitly asked for implementation beyond inspect.

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
  "recommended_loops": [
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
  "evidence_contract": [
    "helper scripts must write crash-safe structured evidence to MEGURI_EVIDENCE_DIR"
  ],
  "next_actions": ["string"]
}}
```

`.meguri/project-brief.md`
- A concise, audit-friendly brief for a human and future agents.
- Include detected project shape, evidence read, recommended loops, missing
  information, risk boundaries, evidence contract, and the next Meguri actions.

After writing the files:
1. If `questions` is non-empty, stop and ask the user those questions.
2. If status is `ready`, suggest the smallest next implementation step.
3. Do not write loops or edit tests during inspect unless the user explicitly
   asked you to continue beyond inspection.
"""
