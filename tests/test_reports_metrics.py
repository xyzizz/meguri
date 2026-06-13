import json

from meguri.reports.metrics import extract_created_resources_from_steps, extract_failure_reasons_from_steps


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
