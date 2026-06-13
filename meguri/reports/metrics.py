from __future__ import annotations

import json
import re
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


def extract_failed_items_from_steps(steps: list[Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for step in steps:
        stdout = _get_value(step, "stdout")
        if not isinstance(stdout, str) or not stdout:
            continue
        try:
            value = extract_last_json(stdout)
        except ValueError:
            continue
        for item in _failed_items(value):
            key = (item["type"], item["id"], item["name"], item["error"])
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
    return items


def extract_validation_issues_from_steps(steps: list[Any]) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str, str, str]] = set()
    for step in steps:
        stdout = _get_value(step, "stdout")
        if not isinstance(stdout, str) or not stdout:
            continue
        try:
            value = extract_last_json(stdout)
        except ValueError:
            continue
        for issue in _validation_issues(value):
            key = (
                issue["code"],
                issue["object"],
                issue["count"],
                issue["path"],
                issue["types"],
                issue["source"],
            )
            if key in seen:
                continue
            seen.add(key)
            issues.append(issue)
    return issues


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


def extract_failure_reasons_from_steps(steps: list[Any]) -> list[str]:
    item_reasons: list[str] = []
    general_reasons: list[str] = []
    for step in steps:
        stdout = _get_value(step, "stdout")
        if not isinstance(stdout, str) or not stdout:
            continue
        try:
            value = extract_last_json(stdout)
        except ValueError:
            continue
        item_values, general_values = _json_failure_reason_groups(value)
        item_reasons.extend(item_values)
        general_reasons.extend(general_values)
    if item_reasons:
        actionable_general = [reason for reason in general_reasons if not _is_mechanical_failure_reason(reason)]
        return _dedupe_texts(actionable_general + item_reasons)
    return _dedupe_texts(general_reasons)


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


def _failed_items(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, (dict, list)):
        return []
    failed: list[dict[str, str]] = []
    if isinstance(value, dict):
        for key in ("submit_results", "tool_results", "results", "items", "failed_submit_items"):
            items = value.get(key)
            if isinstance(items, list):
                for item in items:
                    failed_item = _failed_item_from_item(item, source=key)
                    if failed_item:
                        failed.append(failed_item)
        for child in value.values():
            failed.extend(_failed_items(child))
    else:
        for child in value:
            failed.extend(_failed_items(child))
    return failed


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


def _validation_issues(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, (dict, list)):
        return []
    issues: list[dict[str, str]] = []
    if isinstance(value, dict):
        for source in ("errors", "crash_tracebacks", "failure_reasons"):
            for text in _string_list(value.get(source)):
                issues.extend(_validation_issues_from_text(text, source=source))
        if isinstance(value.get("error"), str):
            issues.extend(_validation_issues_from_text(value["error"], source="error"))
        for child in value.values():
            issues.extend(_validation_issues(child))
    else:
        for child in value:
            issues.extend(_validation_issues(child))
    return issues


def _validation_issues_from_text(text: str, *, source: str) -> list[dict[str, str]]:
    issues: list[dict[str, str]] = []
    if _looks_like_schema_validation(text):
        issues.append(_schema_validation_issue(text, source=source))
    if _looks_like_agent_response_parse_error(text):
        issues.append(_agent_response_parse_issue(text, source=source))
    return issues


def _looks_like_schema_validation(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "ValidationError",
            "validation errors for",
            "extra_forbidden",
            "literal_error",
            "type=missing",
        )
    )


def _looks_like_agent_response_parse_error(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "AgentResponseParseError",
            "没有完整 AgentResponse",
            "missing complete AgentResponse",
            "顶层必须包含 reply 和 plan",
        )
    )


def _schema_validation_issue(text: str, *, source: str) -> dict[str, str]:
    match = re.search(r"(\d+)\s+validation errors?\s+for\s+([A-Za-z_][\w.]*)", text)
    count = match.group(1) if match else ""
    object_name = match.group(2) if match else ("AgentResponse" if "AgentResponse" in text else "")
    path = _first_validation_path(text)
    types = ",".join(_validation_types(text))
    message_parts = [f"{object_name or 'schema'} validation failed"]
    if count:
        message_parts.append(f"with {count} errors")
    if path:
        message_parts.append(f"at {path}")
    if types:
        message_parts.append(f"({types})")
    return {
        "code": "schema_validation",
        "severity": "error",
        "object": object_name,
        "count": count,
        "path": path,
        "types": types,
        "message": " ".join(message_parts),
        "source": source,
    }


def _agent_response_parse_issue(text: str, *, source: str) -> dict[str, str]:
    if "没有完整 AgentResponse" in text or "missing complete AgentResponse" in text:
        message = "AgentResponse parse failed: missing complete AgentResponse"
    else:
        message = "AgentResponse parse failed"
    return {
        "code": "agent_response_parse",
        "severity": "error",
        "object": "AgentResponse",
        "count": "",
        "path": "",
        "types": "parse_error",
        "message": message,
        "source": source,
    }


def _first_validation_path(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^[A-Za-z_][\w]*(?:\.[A-Za-z0-9_]+)+$", stripped):
            return stripped
    return ""


def _validation_types(text: str) -> list[str]:
    types: list[str] = []
    seen: set[str] = set()
    for value in re.findall(r"\[type=([a-zA-Z_]+)", text):
        if value in seen:
            continue
        seen.add(value)
        types.append(value)
    return types


def _json_failure_reason_groups(value: Any) -> tuple[list[str], list[str]]:
    item_reasons: list[str] = []
    general_reasons: list[str] = []
    if isinstance(value, dict):
        general_reasons.extend(_string_list(value.get("failure_reasons")))
        general_reasons.extend(_string_list(value.get("errors")))
        if isinstance(value.get("error"), str):
            general_reasons.append(value["error"])
        item_collection_keys = ("submit_results", "tool_results", "results", "items", "failed_submit_items")
        for key in item_collection_keys:
            item_reasons.extend(_failed_item_reasons(value.get(key)))
        for key, child in value.items():
            if key in item_collection_keys:
                continue
            child_items, child_general = _json_failure_reason_groups(child)
            item_reasons.extend(child_items)
            general_reasons.extend(child_general)
    elif isinstance(value, list):
        for child in value:
            child_items, child_general = _json_failure_reason_groups(child)
            item_reasons.extend(child_items)
            general_reasons.extend(child_general)
    return item_reasons, general_reasons


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


def _failed_item_from_item(item: Any, *, source: str) -> dict[str, str] | None:
    if not isinstance(item, dict) or not _is_failed_item(item):
        return None
    error = _failed_item_error(item)
    return {
        "type": _resource_type(item),
        "id": _resource_id(item),
        "name": _item_name(item),
        "error": error,
        "source": source,
    }


def _is_success_item(item: dict[str, Any]) -> bool:
    ok = item.get("ok")
    status = str(item.get("status") or item.get("result") or "").lower()
    return ok is True or status in {"pass", "passed", "success", "succeeded"}


def _is_failed_item(item: dict[str, Any]) -> bool:
    ok = item.get("ok")
    status = str(item.get("status") or item.get("result") or "").lower()
    return ok is False or status in {"fail", "failed", "error", "blocked"} or bool(item.get("error"))


def _failed_item_error(item: dict[str, Any]) -> str:
    for key in ("error", "message", "reason"):
        if isinstance(item.get(key), str) and item[key].strip():
            return _normalise_failure_reason(item[key])
    result = item.get("result")
    if isinstance(result, dict):
        for key in ("error", "message", "reason"):
            if isinstance(result.get(key), str) and result[key].strip():
                return _normalise_failure_reason(result[key])
    return ""


def _item_name(item: dict[str, Any]) -> str:
    for key in ("name", "tool", "function", "action"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    result = item.get("result")
    if isinstance(result, dict):
        return _item_name(result)
    return ""


def _failed_item_reasons(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    reasons: list[str] = []
    for item in value:
        if isinstance(item, str):
            reasons.append(item)
            continue
        if not isinstance(item, dict):
            continue
        ok = item.get("ok")
        status = str(item.get("status") or item.get("result") or "").lower()
        failed = ok is False or status in {"fail", "failed", "error", "blocked"} or bool(item.get("error"))
        if not failed:
            continue
        for key in ("error", "message", "reason"):
            if isinstance(item.get(key), str):
                reasons.append(item[key])
        result = item.get("result")
        if isinstance(result, dict):
            for key in ("error", "message", "reason"):
                if isinstance(result.get(key), str):
                    reasons.append(result[key])
    return reasons


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


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _dedupe_texts(values: list[str], *, limit: int = 5) -> list[str]:
    results: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = _normalise_failure_reason(value)
        if not text or text in seen:
            continue
        seen.add(text)
        results.append(text[:500])
        if len(results) >= limit:
            break
    return results


def _normalise_failure_reason(value: Any) -> str:
    text = " ".join(str(value).split())
    if "[Tool loop warning:" in text:
        text = text.split("[Tool loop warning:", 1)[0].strip()
    if text.startswith("{") and text.endswith("}"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return text
        if isinstance(parsed, dict):
            for key in ("error", "message", "reason"):
                parsed_value = parsed.get(key)
                if isinstance(parsed_value, str) and parsed_value.strip():
                    return " ".join(parsed_value.split())
    return text


def _is_mechanical_failure_reason(value: str) -> bool:
    text = " ".join(str(value).lower().split())
    return (
        "submitted success item count" in text
        or "submitted failed item count" in text
    ) and "expected" in text


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
