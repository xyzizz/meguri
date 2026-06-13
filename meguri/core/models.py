from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4


Status = Literal["pass", "fail", "warning", "blocked"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CheckResult:
    id: str
    status: Status
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status in {"pass", "warning"}


@dataclass
class Artifact:
    name: str
    path: str
    kind: str = "file"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    step_id: str
    status: Status
    started_at: str
    finished_at: str
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in {"pass", "warning"} and all(c.ok for c in self.checks)


@dataclass
class RunContext:
    run_id: str
    project_path: Path
    artifact_dir: Path
    mode: Literal["dry_run", "execute"] = "dry_run"
    env: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Scenario:
    name: str
    adapter: str
    project_path: Path
    mode: Literal["dry_run", "execute"]
    steps: list[dict[str, Any]]
    checks: list[dict[str, Any]] = field(default_factory=list)
    budgets: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunReport:
    run_id: str
    scenario_name: str
    status: Status
    started_at: str
    finished_at: str
    project_path: str
    artifact_dir: str
    steps: list[StepResult]
    checks: list[CheckResult]
    html_report_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_run_id(prefix: str = "run") -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
