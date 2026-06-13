import json

from meguri.reports import metrics
from meguri.reports.metrics import (
    extract_created_resources_from_steps,
    extract_failure_reasons_from_steps,
    extract_validation_issues_from_steps,
)


def test_created_resources_are_found_inside_nested_agent_items() -> None:
    stdout = json.dumps(
        {
            "submitted": True,
            "turns": [
                {
                    "id": "submit",
                    "events": [
                        {
                            "tool_result": {
                                "outcome": "partial",
                                "items": [
                                    {
                                        "id": "120250081016770683",
                                        "name": "copy_facebook_campaign_to_account",
                                        "status": "success",
                                    },
                                    {
                                        "id": "-",
                                        "name": "copy_facebook_adset_to_campaign",
                                        "status": "success",
                                    },
                                    {
                                        "name": "copy_facebook_adset_to_campaign",
                                        "status": "error",
                                        "error": "location conflict",
                                    },
                                ],
                            }
                        }
                    ],
                }
            ],
        }
    )

    resources = extract_created_resources_from_steps([{"stdout": stdout}])

    assert resources == [
        {
            "type": "campaign",
            "id": "120250081016770683",
            "source": "items",
        }
    ]


def test_failure_reasons_are_found_inside_nested_agent_items() -> None:
    stdout = json.dumps(
        {
            "submitted": True,
            "errors": ["submit: submitted failed item count=1, expected 0"],
            "turns": [
                {
                    "id": "submit",
                    "events": [
                        {
                            "tool_result": {
                                "items": [
                                    {
                                        "name": "copy_facebook_campaign_to_account",
                                        "status": "success",
                                        "id": "120250081016770683",
                                    },
                                    {
                                        "name": "copy_facebook_adset_to_campaign",
                                        "status": "error",
                                        "error": "please remove conflicting locations",
                                    },
                                    {
                                        "ok": False,
                                        "result": {
                                            "message": "Param video_id is not a valid video_id ID"
                                        },
                                    },
                                    {
                                        "status": "error",
                                        "error": "{\"error\": \"未知错误\"} [Tool loop warning: retry loop]",
                                    },
                                ]
                            }
                        }
                    ],
                }
            ],
        }
    )

    reasons = extract_failure_reasons_from_steps([{"stdout": stdout}])

    assert reasons == [
        "please remove conflicting locations",
        "Param video_id is not a valid video_id ID",
        "未知错误",
    ]


def test_failed_items_are_found_inside_nested_agent_items() -> None:
    stdout = json.dumps(
        {
            "submitted": True,
            "turns": [
                {
                    "id": "submit",
                    "events": [
                        {
                            "tool_result": {
                                "items": [
                                    {
                                        "id": "120247360426150090",
                                        "name": "copy_facebook_ad_to_adset",
                                        "status": "success",
                                    },
                                    {
                                        "id": "120246917768180090",
                                        "name": "copy_facebook_ad_to_adset",
                                        "status": "error",
                                        "error": "image could not be loaded",
                                        "resource_type": "ad",
                                    },
                                    {
                                        "ad_id": "120246917768930090",
                                        "name": "copy_facebook_ad_to_adset",
                                        "ok": False,
                                        "result": {"message": "image could not be loaded"},
                                    },
                                ],
                            }
                        }
                    ],
                }
            ],
        }
    )

    assert hasattr(metrics, "extract_failed_items_from_steps")
    failed_items = metrics.extract_failed_items_from_steps([{"stdout": stdout}])

    assert failed_items == [
        {
            "type": "ad",
            "id": "120246917768180090",
            "name": "copy_facebook_ad_to_adset",
            "error": "image could not be loaded",
            "source": "items",
        },
        {
            "type": "ad",
            "id": "120246917768930090",
            "name": "copy_facebook_ad_to_adset",
            "error": "image could not be loaded",
            "source": "items",
        },
    ]


def test_validation_issues_are_extracted_from_agent_schema_errors() -> None:
    validation_text = """confirm_3: exception ValidationError: 11 validation errors for AgentResponse
plan.panel.DRAFTING.display.CopyAdConfirm.cards.0.subtitle
  Extra inputs are not permitted [type=extra_forbidden, input_value='19 条源广告复制到 2 个目标 Campaign', input_type=str]
plan.panel.DRAFTING.display.BatchEditConfirm.display_schema
  Input should be 'batch_edit_confirm' [type=literal_error, input_value='copy_ad_confirm', input_type=str]
"""
    stdout = json.dumps(
        {
            "passed": False,
            "errors": [validation_text, "submit: flexible_submit_begin was not called"],
            "crash_tracebacks": [
                "AgentResponseParseError: 模型输出中只找到 panel/display/notices/draft 等内部 JSON 片段，没有完整 AgentResponse；顶层必须包含 reply 和 plan。"
            ],
        },
        ensure_ascii=False,
    )

    issues = extract_validation_issues_from_steps([{"stdout": stdout}])

    assert issues == [
        {
            "code": "schema_validation",
            "severity": "error",
            "object": "AgentResponse",
            "count": "11",
            "path": "plan.panel.DRAFTING.display.CopyAdConfirm.cards.0.subtitle",
            "types": "extra_forbidden,literal_error",
            "message": "AgentResponse validation failed with 11 errors at plan.panel.DRAFTING.display.CopyAdConfirm.cards.0.subtitle (extra_forbidden,literal_error)",
            "source": "errors",
        },
        {
            "code": "agent_response_parse",
            "severity": "error",
            "object": "AgentResponse",
            "count": "",
            "path": "",
            "types": "parse_error",
            "message": "AgentResponse parse failed: missing complete AgentResponse",
            "source": "crash_tracebacks",
        },
    ]
