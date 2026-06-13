from __future__ import annotations

from pathlib import Path

from meguri.adapters.dapper_assistant import (
    DapperAssistantAdapter,
    _looks_like_llm_connection_blocked,
    _looks_like_missing_hermes,
)
from meguri.core.models import RunContext


def _ctx() -> RunContext:
    project = Path(__file__).resolve().parents[2] / "dapper_assistant"
    return RunContext(
        run_id="test",
        project_path=project,
        artifact_dir=Path("/tmp/meguri-test"),
    )


def test_dapper_adapter_builds_natural_command() -> None:
    adapter = DapperAssistantAdapter()
    command = adapter._command({"suite": "natural_copy_nodes", "args": ["--case", "x"]}, _ctx())

    assert command[1:] == ["scripts/verify_skills_natural_agent_cards.py", "--json", "--case", "x"]


def test_dapper_adapter_copy_campaign_does_not_execute() -> None:
    adapter = DapperAssistantAdapter()
    command = adapter._command({"suite": "copy_campaign_prompt_nodes"}, _ctx())

    assert "scripts/verify_copy_campaign_prompt_submit.py" in command
    assert "--execute" not in command


def test_missing_hermes_is_blocked_environment() -> None:
    assert _looks_like_missing_hermes("ModuleNotFoundError: No module named 'tools'")
    assert _looks_like_missing_hermes("需要安装 Hermes runtime")


def test_llm_connection_error_is_blocked_environment() -> None:
    assert _looks_like_llm_connection_blocked("APIConnectionError: Connection error.")
