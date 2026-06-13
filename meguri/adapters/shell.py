from __future__ import annotations

import os
import subprocess
from typing import Any

from meguri.core.models import RunContext, StepResult, utc_now


class ShellAdapter:
    name = "shell"

    def setup(self, ctx: RunContext) -> None:
        ctx.project_path.mkdir(parents=True, exist_ok=True)

    def run_step(self, step: dict[str, Any], ctx: RunContext) -> StepResult:
        step_id = str(step["id"])
        command = step.get("command")
        if not isinstance(command, list) or not command:
            now = utc_now()
            return StepResult(
                step_id=step_id,
                status="blocked",
                started_at=now,
                finished_at=now,
                stderr="shell step requires a non-empty command list",
            )
        started = utc_now()
        env = os.environ.copy()
        env.update(ctx.env)
        env.update({str(k): str(v) for k, v in (step.get("env") or {}).items()})
        timeout = float(step.get("timeout_seconds") or 300)
        proc = subprocess.run(
            [str(part) for part in command],
            cwd=str(step.get("workdir") or ctx.project_path),
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return StepResult(
            step_id=step_id,
            status="pass" if proc.returncode == 0 else "fail",
            started_at=started,
            finished_at=utc_now(),
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )

    def collect_artifacts(self, ctx: RunContext) -> list[Any]:
        return []

    def cleanup(self, ctx: RunContext) -> None:
        _ = ctx

