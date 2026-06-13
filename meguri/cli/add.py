from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from meguri.project.pack import find_project_pack, slugify


DEFAULT_FORBIDDEN_SIDE_EFFECTS = [
    "submit",
    "deploy",
    "payment",
    "production write",
    "external send",
]


def handle_add(args: Any) -> int:
    try:
        pack = find_project_pack(Path.cwd())
    except FileNotFoundError:
        print("Cannot add a scenario yet: no .meguri/ pack found.")
        print("Run meguri init first, then retry meguri add.")
        return 2

    questions = _missing_questions(args)
    if questions:
        print("I cannot safely generate this scenario yet. Please clarify:")
        for idx, question in enumerate(questions, start=1):
            print(f"{idx}. {question}")
        return 2

    scenario_id = slugify(args.name or args.description)
    scenario_path = pack.scenarios_dir / f"{scenario_id}.yaml"
    if scenario_path.exists() and not args.force:
        print(f"Scenario already exists: {scenario_path}")
        print("Pass --force to overwrite it.")
        return 1

    forbidden = list(DEFAULT_FORBIDDEN_SIDE_EFFECTS)
    for item in args.forbid or []:
        if item not in forbidden:
            forbidden.append(item)

    data = {
        "name": scenario_id,
        "adapter": "shell",
        "project_path": "../..",
        "mode": args.mode,
        "metadata": {
            "user_goal": args.description,
            "pass_criteria": args.pass_criteria,
            "forbidden_side_effects": forbidden,
        },
        "steps": [
            {
                "id": scenario_id,
                "command": ["sh", "-lc", args.command],
                "timeout_seconds": args.timeout_seconds,
                "checks": [
                    {"id": "exit", "type": "exit_code", "equals": 0},
                    *[
                        {
                            "id": f"forbid_{slugify(item)}",
                            "type": "stdout_not_contains",
                            "text": item,
                        }
                        for item in forbidden
                    ],
                ],
            }
        ],
    }
    scenario_path.parent.mkdir(parents=True, exist_ok=True)
    scenario_path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    print(f"created {scenario_path.relative_to(pack.project_root)}")
    return 0


def _missing_questions(args: Any) -> list[str]:
    questions: list[str] = []
    if not args.description or len(args.description.strip()) < 4:
        questions.append("What workflow or user goal should this scenario verify?")
    if not args.command:
        questions.append("What safe command should execute this scenario? Provide --command.")
    if not args.pass_criteria:
        questions.append("What deterministic evidence proves success? Provide --pass-criteria.")
    if args.mode == "execute" and not args.allow_execute:
        questions.append("This scenario requests execute mode. Confirm with --allow-execute and describe forbidden side effects.")
    return questions
