from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def build_replay_bundle(
    *,
    source_run_id: str,
    loop_id: str,
    scenario_path: Path,
    command: list[str] | None,
    evidence_files: list[Path],
    project_ref: dict[str, Any] | None = None,
    replay_source: str | None = None,
    retry_of: str | None = None,
) -> dict[str, Any]:
    inputs = [{"source": "evidence", "path": path.as_posix()} for path in evidence_files]
    return {
        "version": 1,
        "source_run_id": source_run_id,
        "loop_id": loop_id,
        "scenario_path": str(scenario_path),
        "command": command or [],
        "project_ref": project_ref or build_project_ref(scenario_path.parent),
        "inputs": inputs,
        "environment": {"redacted_env": _redacted_env_names()},
        "replay": {
            "status": "full" if inputs else "none",
            "missing": [] if inputs else ["structured evidence"],
        },
        "replay_source": replay_source,
        "retry_of": retry_of,
    }


def build_project_ref(cwd: Path) -> dict[str, Any]:
    root = _git(cwd, ["rev-parse", "--show-toplevel"])
    git_cwd = Path(root) if root else cwd
    branch = _git(git_cwd, ["branch", "--show-current"])
    commit = _git(git_cwd, ["rev-parse", "--short", "HEAD"])
    status = _git_status(git_cwd)
    return {
        "git_root": root or None,
        "git_branch": branch or None,
        "git_commit": commit or None,
        "dirty": bool(status),
        "status": status,
    }


def _git_status(cwd: Path) -> list[dict[str, str]]:
    output = _git(cwd, ["status", "--short", "--untracked-files=all"])
    entries = []
    for line in output.splitlines():
        if len(line) < 4:
            continue
        entries.append({"code": line[:2].strip(), "path": line[3:]})
    return entries


def _git(cwd: Path, args: list[str]) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=str(cwd), text=True, capture_output=True, check=False)
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def _redacted_env_names() -> list[str]:
    return ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "DATABASE_URL", "REDIS_URL", "TOKEN", "SECRET"]
