"""TaskCenter Feishu Card V2 delivery SDK.

The SDK talks to Feishu OpenAPI directly over HTTPS.  It deliberately avoids
shelling out to ``openclaw message send`` so TaskCenter can own deterministic
reminder delivery.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal

from feishu_card_v2.card import ensure_card_within_size_limit

ReceiveIdType = Literal["open_id", "user_id", "union_id", "email", "chat_id"]
_RECEIVE_ID_TYPES = {"open_id", "user_id", "union_id", "email", "chat_id"}
AUTH_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
SEND_MESSAGE_URL = "https://open.feishu.cn/open-apis/im/v1/messages"

JsonTransport = Callable[[str, Mapping[str, Any], Mapping[str, str] | None, Mapping[str, str] | None, float], dict[str, Any]]


class FeishuSDKError(RuntimeError):
    """Base exception for Feishu SDK failures."""


class FeishuConfigError(FeishuSDKError):
    """Raised when credentials or target configuration is missing/invalid."""


class FeishuAPIError(FeishuSDKError):
    """Raised when Feishu OpenAPI returns a non-zero code or HTTP failure."""

    def __init__(self, message: str, *, response: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.response = response or {}


@dataclass(frozen=True)
class FeishuCredentials:
    app_id: str
    app_secret: str

    @classmethod
    def from_settings(cls, settings: Any) -> "FeishuCredentials":
        app_id = getattr(settings, "feishu_app_id", None)
        app_secret = getattr(settings, "feishu_app_secret", None)
        if not app_id or not app_secret:
            raise FeishuConfigError(
                "Feishu credentials are required: set TASK_CENTER_FEISHU_APP_ID "
                "and TASK_CENTER_FEISHU_APP_SECRET"
            )
        return cls(app_id=app_id, app_secret=app_secret)


@dataclass(frozen=True)
class FeishuTarget:
    receive_id: str
    receive_id_type: ReceiveIdType = "open_id"

    @classmethod
    def from_settings(cls, settings: Any) -> "FeishuTarget":
        receive_id = getattr(settings, "feishu_default_receive_id", None)
        receive_id_type = getattr(settings, "feishu_default_receive_id_type", "open_id")
        if not receive_id:
            raise FeishuConfigError("Default Feishu receive_id is required: set TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID")
        return cls(receive_id=receive_id, receive_id_type=validate_receive_id_type(receive_id_type))


def validate_receive_id_type(value: str) -> ReceiveIdType:
    if value not in _RECEIVE_ID_TYPES:
        raise FeishuConfigError(f"Unsupported Feishu receive_id_type: {value}")
    return value  # type: ignore[return-value]


def post_json(
    url: str,
    payload: Mapping[str, Any],
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, str] | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """POST JSON and return decoded JSON using only the standard library."""

    request_url = url
    if params:
        request_url = f"{url}?{urllib.parse.urlencode(params)}"
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        request_url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            **dict(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - controlled OpenAPI URL
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw_error = exc.read().decode("utf-8", errors="replace")
        raise FeishuAPIError(f"Feishu HTTP error {exc.code}: {raw_error}") from exc
    except urllib.error.URLError as exc:
        raise FeishuAPIError(f"Feishu network error: {exc.reason}") from exc
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise FeishuAPIError(f"Feishu returned non-JSON response: {raw[:200]}") from exc
    if not isinstance(decoded, dict):
        raise FeishuAPIError("Feishu returned a non-object JSON response", response={"raw": decoded})
    return decoded


class FeishuAuth:
    """Tenant access token manager with in-process cache and early refresh."""

    def __init__(
        self,
        credentials: FeishuCredentials,
        *,
        transport: JsonTransport = post_json,
        timeout: float = 10.0,
        refresh_margin_seconds: int = 300,
        time_fn: Callable[[], float] = time.time,
    ) -> None:
        self.credentials = credentials
        self.transport = transport
        self.timeout = timeout
        self.refresh_margin_seconds = refresh_margin_seconds
        self.time_fn = time_fn
        self._token: str | None = None
        self._expires_at = 0.0

    @property
    def token(self) -> str:
        now = self.time_fn()
        if self._token and now < self._expires_at - self.refresh_margin_seconds:
            return self._token
        self.refresh()
        if not self._token:
            raise FeishuAPIError("Feishu token refresh succeeded without token")
        return self._token

    def refresh(self) -> None:
        response = self.transport(
            AUTH_URL,
            {"app_id": self.credentials.app_id, "app_secret": self.credentials.app_secret},
            None,
            None,
            self.timeout,
        )
        if response.get("code") != 0:
            raise FeishuAPIError(f"Failed to get Feishu tenant_access_token: {response}", response=response)
        token = response.get("tenant_access_token")
        expire = response.get("expire")
        if not token or not isinstance(expire, int):
            raise FeishuAPIError(f"Invalid Feishu token response: {response}", response=response)
        self._token = str(token)
        self._expires_at = self.time_fn() + expire

    def invalidate(self) -> None:
        self._token = None
        self._expires_at = 0.0


class FeishuCardClient:
    """Send Feishu Card JSON 2.0 messages through Feishu OpenAPI."""

    def __init__(
        self,
        auth: FeishuAuth,
        *,
        transport: JsonTransport = post_json,
        timeout: float = 10.0,
    ) -> None:
        self.auth = auth
        self.transport = transport
        self.timeout = timeout

    @classmethod
    def from_settings(cls, settings: Any) -> "FeishuCardClient":
        credentials = FeishuCredentials.from_settings(settings)
        auth = FeishuAuth(credentials)
        return cls(auth)

    def send_card(
        self,
        *,
        receive_id: str,
        card: dict[str, Any],
        receive_id_type: ReceiveIdType = "open_id",
        uuid: str | None = None,
    ) -> dict[str, Any]:
        """Send a Feishu interactive card and return the raw API response."""

        if not receive_id:
            raise FeishuConfigError("Feishu receive_id is required")
        receive_id_type = validate_receive_id_type(receive_id_type)
        ensure_card_within_size_limit(card)

        payload: dict[str, Any] = {
            "receive_id": receive_id,
            "msg_type": "interactive",
            "content": json.dumps(card, ensure_ascii=False, separators=(",", ":")),
        }
        if uuid:
            payload["uuid"] = uuid

        response = self.transport(
            SEND_MESSAGE_URL,
            payload,
            {"Authorization": f"Bearer {self.auth.token}"},
            {"receive_id_type": receive_id_type},
            self.timeout,
        )
        if response.get("code") != 0:
            raise FeishuAPIError(f"Failed to send Feishu card: {response}", response=response)
        return response

    def send_text_card(
        self,
        *,
        receive_id: str,
        text_card: dict[str, Any],
        receive_id_type: ReceiveIdType = "open_id",
        uuid: str | None = None,
    ) -> dict[str, Any]:
        """Alias for ``send_card`` used by callers that build a simple text card."""

        return self.send_card(receive_id=receive_id, card=text_card, receive_id_type=receive_id_type, uuid=uuid)
