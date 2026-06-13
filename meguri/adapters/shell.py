from __future__ import annotations

import os
import subprocess
import threading
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
        step_dir = ctx.artifact_dir / "steps" / step_id
        step_dir.mkdir(parents=True, exist_ok=True)
        stdout_path = step_dir / "stdout.txt"
        stderr_path = step_dir / "stderr.txt"
        stdout_path.write_text("", encoding="utf-8")
        stderr_path.write_text("", encoding="utf-8")

        proc = subprocess.Popen(
            [str(part) for part in command],
            cwd=str(step.get("workdir") or ctx.project_path),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
        )
        stdout_thread = threading.Thread(target=_tee_stream, args=(proc.stdout, stdout_path), daemon=True)
        stderr_thread = threading.Thread(target=_tee_stream, args=(proc.stderr, stderr_path), daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        timed_out = False
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            proc.wait()
            with stderr_path.open("a", encoding="utf-8") as stream:
                stream.write(f"\nmeguri: command timed out after {timeout:g} seconds\n")
        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)
        stdout = stdout_path.read_text(encoding="utf-8")
        stderr = stderr_path.read_text(encoding="utf-8")
        return StepResult(
            step_id=step_id,
            status="pass" if proc.returncode == 0 and not timed_out else "fail",
            started_at=started,
            finished_at=utc_now(),
            exit_code=proc.returncode,
            stdout=stdout,
            stderr=stderr,
            data={
                "command": [str(part) for part in command],
                "live_stdout": str(stdout_path),
                "live_stderr": str(stderr_path),
                "timed_out": timed_out,
            },
        )

    def collect_artifacts(self, ctx: RunContext) -> list[Any]:
        return []

    def cleanup(self, ctx: RunContext) -> None:
        _ = ctx


def _tee_stream(stream: Any, path) -> None:
    if stream is None:
        return
    with path.open("a", encoding="utf-8") as output:
        for line in iter(stream.readline, ""):
            output.write(line)
            output.flush()
