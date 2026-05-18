from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

SDK_DIR = Path(__file__).resolve().parents[1] / "scripts" / "sdk" / "feishu-card-v1"
if str(SDK_DIR) not in sys.path:
    sys.path.insert(0, str(SDK_DIR))

from config import get_settings
from feishu_card_v1 import (  # noqa: E402
    FeishuAuth,
    FeishuCardV1APIError,
    FeishuCardV1Client,
    FeishuCardV1ConfigError,
    FeishuCardV1PayloadTooLarge,
    FeishuCredentials,
    FeishuTarget,
    build_card_v1,
    markdown_to_card_v1,
    serialized_card_size,
    text_to_card_v1,
    validate_receive_id_type,
)


def test_markdown_to_card_v1_extracts_heading_without_schema_and_splits_blocks() -> None:
    card = markdown_to_card_v1(
        "# 晚间收口\n\n- 已完成：A\n\n---\n\n- 待确认：B",
        template="green",
        split=True,
    )

    assert "schema" not in card
    assert "body" not in card
    assert card["header"]["title"]["content"] == "晚间收口"
    assert card["header"]["template"] == "green"
    assert [item["tag"] for item in card["elements"]] == ["markdown", "hr", "markdown"]
    assert "已完成" in card["elements"][0]["content"]
    assert "待确认" in card["elements"][2]["content"]


def test_text_to_card_v1_builds_small_reminder_card() -> None:
    card = text_to_card_v1("提醒：跟进同程报价清单流程。", title="TaskCenter 提醒")

    assert "schema" not in card
    assert card["header"]["title"]["content"] == "TaskCenter 提醒"
    assert card["config"]["update_multi"] is False
    assert card["elements"][0]["content"] == "提醒：跟进同程报价清单流程。"
    assert serialized_card_size(card).within_limit


def test_build_card_v1_rejects_payload_over_feishu_limit() -> None:
    huge = "x" * (31 * 1024)

    with pytest.raises(FeishuCardV1PayloadTooLarge):
        build_card_v1(title="too large", markdown=huge)


def test_validate_receive_id_type_rejects_unknown_value() -> None:
    with pytest.raises(FeishuCardV1ConfigError):
        validate_receive_id_type("bad_id")


def test_settings_load_task_center_feishu_env_for_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TASK_CENTER_FEISHU_APP_ID", "cli_test")
    monkeypatch.setenv("TASK_CENTER_FEISHU_APP_SECRET", "secret")
    monkeypatch.setenv("TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID", "ou_test")
    monkeypatch.setenv("TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID_TYPE", "open_id")

    settings = get_settings()
    credentials = FeishuCredentials.from_settings(settings)
    target = FeishuTarget.from_settings(settings)

    assert credentials.app_id == "cli_test"
    assert credentials.app_secret == "secret"
    assert target.receive_id == "ou_test"
    assert target.receive_id_type == "open_id"


def test_client_fetches_token_and_sends_card_v1_payload() -> None:
    calls: list[dict[str, Any]] = []

    def fake_transport(
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str] | None,
        params: Mapping[str, str] | None,
        timeout: float,
    ) -> dict[str, Any]:
        calls.append(
            {
                "url": url,
                "payload": dict(payload),
                "headers": dict(headers or {}),
                "params": dict(params or {}),
                "timeout": timeout,
            }
        )
        if url.endswith("/tenant_access_token/internal"):
            return {"code": 0, "msg": "ok", "tenant_access_token": "t-test", "expire": 7200}
        if url.endswith("/im/v1/messages"):
            return {"code": 0, "msg": "success", "data": {"message_id": "om_test"}}
        raise AssertionError(f"Unexpected URL: {url}")

    auth = FeishuAuth(FeishuCredentials("cli_test", "secret"), transport=fake_transport, time_fn=lambda: 1000.0)
    client = FeishuCardV1Client(auth, transport=fake_transport)
    card = text_to_card_v1("提醒：测试")

    response = client.send_card(receive_id="ou_test", receive_id_type="open_id", card=card, uuid="task-1")

    assert response["data"]["message_id"] == "om_test"
    assert len(calls) == 2
    assert calls[0]["payload"] == {"app_id": "cli_test", "app_secret": "secret"}
    send_call = calls[1]
    assert send_call["headers"]["Authorization"] == "Bearer t-test"
    assert send_call["params"] == {"receive_id_type": "open_id"}
    assert send_call["payload"]["receive_id"] == "ou_test"
    assert send_call["payload"]["msg_type"] == "interactive"
    assert send_call["payload"]["uuid"] == "task-1"
    content = json.loads(send_call["payload"]["content"])
    assert "schema" not in content
    assert "body" not in content
    assert content["elements"][0]["tag"] == "markdown"


def test_client_reuses_cached_token() -> None:
    token_calls = 0

    def fake_transport(
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str] | None,
        params: Mapping[str, str] | None,
        timeout: float,
    ) -> dict[str, Any]:
        nonlocal token_calls
        if url.endswith("/tenant_access_token/internal"):
            token_calls += 1
            return {"code": 0, "msg": "ok", "tenant_access_token": "t-test", "expire": 7200}
        return {"code": 0, "msg": "success", "data": {"message_id": "om_test"}}

    auth = FeishuAuth(FeishuCredentials("cli_test", "secret"), transport=fake_transport, time_fn=lambda: 1000.0)
    client = FeishuCardV1Client(auth, transport=fake_transport)
    card = text_to_card_v1("提醒：测试")

    client.send_card(receive_id="ou_test", card=card)
    client.send_card(receive_id="ou_test", card=card)

    assert token_calls == 1


def test_client_raises_api_error_on_nonzero_response() -> None:
    def fake_transport(
        url: str,
        payload: Mapping[str, Any],
        headers: Mapping[str, str] | None,
        params: Mapping[str, str] | None,
        timeout: float,
    ) -> dict[str, Any]:
        if url.endswith("/tenant_access_token/internal"):
            return {"code": 0, "msg": "ok", "tenant_access_token": "t-test", "expire": 7200}
        return {"code": 230034, "msg": "receive_id invalid"}

    auth = FeishuAuth(FeishuCredentials("cli_test", "secret"), transport=fake_transport)
    client = FeishuCardV1Client(auth, transport=fake_transport)

    with pytest.raises(FeishuCardV1APIError) as exc:
        client.send_card(receive_id="ou_bad", card=text_to_card_v1("提醒：测试"))

    assert exc.value.response["code"] == 230034
