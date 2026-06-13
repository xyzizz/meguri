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
        "project_ref": _project_ref(scenario_path),
        "inputs": inputs,
        "environment": {"redacted_env": _redacted_env_names()},
        "replay": {
            "status": "full" if inputs else "none",
            "missing": [] if inputs else ["structured evidence"],
        },
        "replay_source": replay_source,
        "retry_of": retry_of,
    }


def _project_ref(path: Path) -> dict[str, Any]:
    cwd = path.parent
    commit = _git(cwd, ["rev-parse", "--short", "HEAD"])
    dirty = bool(_git(cwd, ["status", "--short"]))
    return {"git_commit": commit or None, "dirty": dirty}


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
