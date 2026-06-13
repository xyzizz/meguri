from __future__ import annotations

from typing import Any, Protocol

from meguri.core.models import RunContext, StepResult


class HarnessAdapter(Protocol):
    name: str

    def setup(self, ctx: RunContext) -> None:
        ...

    def run_step(self, step: dict[str, Any], ctx: RunContext) -> StepResult:
        ...

    def collect_artifacts(self, ctx: RunContext) -> list[Any]:
        ...

    def cleanup(self, ctx: RunContext) -> None:
        ...

