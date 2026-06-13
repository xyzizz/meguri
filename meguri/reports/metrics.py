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


def extract_created_resources_from_steps(steps: list[Any]) -> list[dict[str, str]]:
    resources: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for step in steps:
        stdout = _get_value(step, "stdout")
        if not isinstance(stdout, str) or not stdout:
            continue
        try:
            value = extract_last_json(stdout)
        except ValueError:
            continue
        for resource in _created_resources(value):
            key = (resource["type"], resource["id"], resource["source"])
            if key in seen:
                continue
            seen.add(key)
            resources.append(resource)
    return resources


def extract_attention_flags_from_steps(steps: list[Any]) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    seen: set[str] = set()
    for step in steps:
        stdout = _get_value(step, "stdout")
        if not isinstance(stdout, str) or not stdout:
            continue
        try:
            value = extract_last_json(stdout)
        except ValueError:
            continue
        for flag in _attention_flags(value):
            code = flag["code"]
            if code in seen:
                continue
            seen.add(code)
            flags.append(flag)
    return flags


def format_metrics(metrics: dict[str, Any]) -> str:
    parts: list[str] = []
    if isinstance(metrics.get("turn_count"), int):
        expected = metrics.get("expected_turn_count")
        if isinstance(expected, int):
            parts.append(f"turns={metrics['turn_count']}/{expected}")
        else:
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
    for key in ("turn_count", "expected_turn_count", "submitted", "closed_status_verified", "boundary_crossed"):
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


def _created_resources(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, (dict, list)):
        return []
    resources: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key in ("submit_results", "tool_results", "results", "items"):
            items = value.get(key)
            if isinstance(items, list):
                for item in items:
                    resource = _created_resource_from_item(item, source=key)
                    if resource:
                        resources.append(resource)
        for child in value.values():
            resources.extend(_created_resources(child))
    else:
        for child in value:
            resources.extend(_created_resources(child))
    return resources


def _attention_flags(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, dict):
        return []
    flags: list[dict[str, str]] = []
    turn_count = value.get("turn_count")
    expected_turn_count = value.get("expected_turn_count")
    if isinstance(turn_count, int) and isinstance(expected_turn_count, int) and turn_count < expected_turn_count:
        flags.append({
            "code": "short_run",
            "severity": "warning",
            "message": f"turn_count {turn_count} below expected {expected_turn_count}",
        })
    if value.get("final_submit") is True and value.get("submitted") is False:
        flags.append({
            "code": "not_submitted",
            "severity": "warning",
            "message": "final_submit expected but submitted is false",
        })
    crash_tracebacks = value.get("crash_tracebacks")
    if isinstance(crash_tracebacks, list) and any(str(item).strip() for item in crash_tracebacks):
        flags.append({
            "code": "crash_traceback",
            "severity": "error",
            "message": _compact_message(_first_nonempty(crash_tracebacks)),
        })
    return flags


def _created_resource_from_item(item: Any, *, source: str) -> dict[str, str] | None:
    if not isinstance(item, dict) or not _is_success_item(item):
        return None
    resource_id = _resource_id(item)
    if not resource_id:
        return None
    return {
        "type": _resource_type(item),
        "id": resource_id,
        "source": source,
    }


def _is_success_item(item: dict[str, Any]) -> bool:
    ok = item.get("ok")
    status = str(item.get("status") or item.get("result") or "").lower()
    return ok is True or status in {"pass", "passed", "success", "succeeded"}


def _resource_type(item: dict[str, Any]) -> str:
    for key in ("resource_type", "kind", "type", "object_type"):
        value = item.get(key)
        if isinstance(value, str) and value:
            return value
    for key in ("campaign_id", "adset_id", "ad_id", "creative_id"):
        if item.get(key):
            return key.removesuffix("_id")
    for key in ("name", "tool", "function", "action"):
        value = item.get(key)
        if not isinstance(value, str):
            continue
        lowered = value.lower()
        if "copy_facebook_campaign" in lowered:
            return "campaign"
        if "copy_facebook_adset" in lowered:
            return "adset"
        if "copy_facebook_ad_" in lowered or "copy_facebook_ad_to" in lowered:
            return "ad"
        for resource_type in ("campaign", "adset", "creative", "ad"):
            if resource_type in lowered:
                return resource_type
    return "resource"


def _resource_id(item: dict[str, Any]) -> str:
    for key in ("id", "resource_id", "campaign_id", "adset_id", "ad_id", "creative_id"):
        value = item.get(key)
        resource_id = _normalise_resource_id(value)
        if resource_id:
            return resource_id
    result = item.get("result")
    if isinstance(result, dict):
        return _resource_id(result)
    return ""


def _normalise_resource_id(value: Any) -> str:
    if not isinstance(value, (str, int)):
        return ""
    text = str(value).strip()
    if not text or text.lower() in {"-", "n/a", "na", "none", "null", "unknown"}:
        return ""
    return text


def _first_nonempty(values: list[Any]) -> str:
    for value in values:
        text = str(value).strip()
        if text:
            return text
    return ""


def _compact_message(value: str, *, limit: int = 180) -> str:
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return f"{text[:limit - 3]}..."


def _get_value(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
