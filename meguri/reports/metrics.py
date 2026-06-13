from __future__ import annotations

from typing import Any

from meguri.evaluators.deterministic import extract_last_json


def extract_run_metrics_from_steps(steps: list[Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for step in steps:
        stdout = _get_value(step, "stdout")
        if not isinstance(stdout, str) or not stdout:
            continue
        try:
            value = extract_last_json(stdout)
        except ValueError:
            continue
        _merge_metrics(metrics, value)
    return metrics


def format_metrics(metrics: dict[str, Any]) -> str:
    parts: list[str] = []
    if isinstance(metrics.get("turn_count"), int):
        parts.append(f"turns={metrics['turn_count']}")
    if isinstance(metrics.get("submitted"), bool):
        parts.append(f"submitted={str(metrics['submitted']).lower()}")
    if isinstance(metrics.get("closed_status_verified"), bool):
        parts.append(f"closed={str(metrics['closed_status_verified']).lower()}")
    success = metrics.get("submit_success_count")
    failed = metrics.get("submit_failed_count")
    if isinstance(success, int) or isinstance(failed, int):
        success_count = success if isinstance(success, int) else 0
        failed_count = failed if isinstance(failed, int) else 0
        parts.append(f"submit={success_count}/{success_count + failed_count}")
    return "; ".join(parts)


def _merge_metrics(metrics: dict[str, Any], value: Any) -> None:
    if not isinstance(value, dict):
        return
    for key in ("turn_count", "submitted", "closed_status_verified", "boundary_crossed"):
        if key in value and isinstance(value[key], (bool, int)):
            metrics[key] = value[key]
    counts = _submit_counts(value)
    if counts:
        metrics["submit_success_count"] = counts[0]
        metrics["submit_failed_count"] = counts[1]


def _submit_counts(value: dict[str, Any]) -> tuple[int, int] | None:
    for key in ("submit_results", "tool_results", "results", "items", "failed_submit_items"):
        items = value.get(key)
        if not isinstance(items, list) or not items:
            continue
        success = 0
        failed = 0
        for item in items:
            if isinstance(item, str):
                failed += 1
                continue
            if not isinstance(item, dict):
                continue
            ok = item.get("ok")
            status = str(item.get("status") or item.get("result") or "").lower()
            if ok is True or status in {"pass", "passed", "success", "succeeded"}:
                success += 1
            elif ok is False or status in {"fail", "failed", "error", "blocked"} or item.get("error"):
                failed += 1
        return success, failed
    return None


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
