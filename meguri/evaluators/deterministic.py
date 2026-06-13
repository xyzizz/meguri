from __future__ import annotations

import json
from typing import Any

from meguri.core.models import CheckResult, StepResult


def extract_last_json(text: str) -> Any:
    """Return the last JSON object/array embedded in text.

    Some legacy verification scripts print per-case JSON lines before a final
    summary object. This parser intentionally accepts that shape and returns the
    last valid JSON value.
    """
    decoder = json.JSONDecoder()
    for idx in range(len(text) - 1, -1, -1):
        char = text[idx]
        if char not in "[{":
            continue
        try:
            value, end = decoder.raw_decode(text[idx:])
        except json.JSONDecodeError:
            continue
        if text[idx + end :].strip() == "":
            return value
    raise ValueError("no JSON object or array found")


def get_json_path(data: Any, path: str) -> Any:
    if not path.startswith("$."):
        raise ValueError(f"unsupported JSON path: {path}")
    current = data
    for part in path[2:].split("."):
        if isinstance(current, dict):
            current = current[part]
        elif isinstance(current, list):
            current = current[int(part)]
        else:
            raise KeyError(part)
    return current


def evaluate_step_checks(step: StepResult, checks: list[dict[str, Any]]) -> list[CheckResult]:
    results: list[CheckResult] = []
    cached_stdout_json: Any = None
    stdout_json_loaded = False
    stdout_json_error: ValueError | None = None
    for raw in checks:
        check_id = str(raw.get("id") or raw.get("type") or "check")
        check_type = str(raw.get("type") or "")
        try:
            if check_type == "exit_code":
                expected = int(raw.get("equals", 0))
                actual = step.exit_code
                ok = actual == expected
                results.append(CheckResult(check_id, "pass" if ok else "fail", f"exit_code={actual}", {
                    "expected": expected,
                    "actual": actual,
                }))
            elif check_type == "stdout_json_path":
                if not stdout_json_loaded:
                    stdout_json_loaded = True
                    try:
                        cached_stdout_json = extract_last_json(step.stdout)
                    except ValueError as exc:
                        stdout_json_error = exc
                if stdout_json_error is not None:
                    results.append(CheckResult(
                        check_id,
                        "blocked",
                        f"stdout did not contain JSON ({stdout_json_error}); inspect stdout/stderr artifacts",
                    ))
                    continue
                actual = get_json_path(cached_stdout_json, str(raw["path"]))
                expected = raw.get("equals")
                ok = actual == expected
                results.append(CheckResult(check_id, "pass" if ok else "fail", f"{raw['path']}={actual!r}", {
                    "expected": expected,
                    "actual": actual,
                }))
            elif check_type == "stdout_not_contains":
                needle = str(raw["text"])
                ok = needle not in step.stdout
                results.append(CheckResult(check_id, "pass" if ok else "fail", f"stdout must not contain {needle!r}"))
            elif check_type == "stderr_not_contains":
                needle = str(raw["text"])
                ok = needle not in step.stderr
                results.append(CheckResult(check_id, "pass" if ok else "fail", f"stderr must not contain {needle!r}"))
            else:
                results.append(CheckResult(check_id, "blocked", f"unknown check type: {check_type}"))
        except Exception as exc:  # noqa: BLE001
            results.append(CheckResult(check_id, "fail", f"check raised {type(exc).__name__}: {exc}"))
    return results
