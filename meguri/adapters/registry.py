from __future__ import annotations

from meguri.adapters.dapper_assistant import DapperAssistantAdapter
from meguri.adapters.shell import ShellAdapter


def get_adapter(name: str):
    adapters = {
        "shell": ShellAdapter(),
        "dapper_assistant": DapperAssistantAdapter(),
    }
    try:
        return adapters[name]
    except KeyError as exc:
        raise ValueError(f"unknown adapter: {name}") from exc

