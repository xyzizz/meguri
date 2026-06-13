from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from meguri.core.models import RunContext, StepResult, utc_now


class DapperAssistantAdapter:
    """Adapter for the sibling dapper_assistant project.

    The adapter intentionally delegates domain verification to existing dapper
    scripts. This keeps Meguri generic and avoids copying fragile ad-flow
    logic into the core runner.
    """

    name = "dapper_assistant"

    def setup(self, ctx: RunContext) -> None:
        required = [
            ctx.project_path / "scripts" / "verify_skills_natural_agent_cards.py",
            ctx.project_path / "scripts" / "verify_batch_edit_agent_cards.py",
            ctx.project_path / "scripts" / "verify_copy_campaign_prompt_submit.py",
        ]
        missing = [str(path) for path in required if not path.is_file()]
        if missing:
            raise FileNotFoundError(f"dapper_assistant adapter missing required scripts: {missing}")

    def run_step(self, step: dict[str, Any], ctx: RunContext) -> StepResult:
        action = str(step.get("action") or "")
        if action != "dapper_pre_submit":
            now = utc_now()
            return StepResult(
                step_id=str(step.get("id", "unknown")),
                status="blocked",
                started_at=now,
                finished_at=now,
                stderr=f"unsupported dapper action: {action}",
            )
        if step.get("preflight_llm_proxy", True):
            blocked = _llm_proxy_preflight(str(step["id"]))
            if blocked is not None:
                return blocked
        command = self._command(step, ctx)
        started = utc_now()
        env = os.environ.copy()
        env.update(ctx.env)
        env.update({
            "HERMES_META_MCP_DISABLED": "1",
            "HERMES_HONCHO_RUNTIME_DISABLED": "1",
            "HERMES_LOG_CALLBACKS": "0",
            "HERMES_LOG_TOOL_TRACE": "1",
            "HERMES_LOG_FULL_RESPONSE": "1",
        })
        env.update({str(k): str(v) for k, v in (step.get("env") or {}).items()})
        timeout = float(step.get("timeout_seconds") or 900)
        proc = subprocess.run(
            command,
            cwd=str(ctx.project_path),
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        status = "pass" if proc.returncode == 0 else "fail"
        combined_output = f"{proc.stdout}\n{proc.stderr}"
        if proc.returncode != 0 and (
            _looks_like_missing_hermes(combined_output) or _looks_like_llm_connection_blocked(combined_output)
        ):
            status = "blocked"
        return StepResult(
            step_id=str(step["id"]),
            status=status,
            started_at=started,
            finished_at=utc_now(),
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            data={"command": command, "suite": step.get("suite")},
        )

    def collect_artifacts(self, ctx: RunContext) -> list[Any]:
        _ = ctx
        return []

    def cleanup(self, ctx: RunContext) -> None:
        _ = ctx

    def _python(self, step: dict[str, Any], ctx: RunContext) -> str:
        configured = str(step.get("python") or ".venv/bin/python")
        path = Path(configured)
        if not path.is_absolute():
            path = ctx.project_path / path
        if path.exists():
            return str(path)
        return sys.executable

    def _command(self, step: dict[str, Any], ctx: RunContext) -> list[str]:
        suite = str(step.get("suite") or "")
        python = self._python(step, ctx)
        extra_args = [str(arg) for arg in (step.get("args") or [])]
        if suite == "natural_copy_nodes":
            return [python, "scripts/verify_skills_natural_agent_cards.py", "--json", *extra_args]
        if suite == "batch_edit_nodes":
            return [python, "scripts/verify_batch_edit_agent_cards.py", "--json", *extra_args]
        if suite == "copy_campaign_prompt_nodes":
            # No --execute: this covers preview + confirm, never final submit.
            return [python, "scripts/verify_copy_campaign_prompt_submit.py", "--json", *extra_args]
        raise ValueError(f"unknown dapper pre-submit suite: {suite}")


def _looks_like_missing_hermes(stderr: str) -> bool:
    return (
        "tools.registry" in stderr
        or "No module named 'tools'" in stderr
        or "Hermes runtime" in stderr
        or "hermes-agent" in stderr
    )


def _looks_like_llm_connection_blocked(text: str) -> bool:
    return "APIConnectionError" in text and "Connection error" in text


def _llm_proxy_preflight(step_id: str) -> StepResult | None:
    started = utc_now()
    host = "llm-proxy.lilithgames.com"
    try:
        with socket.create_connection((host, 443), timeout=5):
            return None
    except OSError as exc:
        return StepResult(
            step_id=step_id,
            status="blocked",
            started_at=started,
            finished_at=utc_now(),
            stderr=f"LLM proxy preflight failed for {host}:443: {type(exc).__name__}: {exc}",
            data={"preflight": "llm_proxy", "host": host, "port": 443},
        )
