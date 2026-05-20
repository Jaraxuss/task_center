"""TaskCenter Feishu Card V1 SDK compatibility imports."""

from __future__ import annotations

import sys
from pathlib import Path

_SDK_DIR = Path(__file__).resolve().parents[1] / "scripts" / "sdk" / "feishu-card-v1"
if str(_SDK_DIR) not in sys.path:
    sys.path.insert(0, str(_SDK_DIR))

from feishu_card_v1 import (  # noqa: E402,F401
    FeishuAuth,
    FeishuCardV1APIError,
    FeishuCardV1Client,
    FeishuCardV1ConfigError,
    FeishuCardV1PayloadTooLarge,
    FeishuCardV1SDKError,
    FeishuCredentials,
    FeishuTarget,
    build_card_v1,
    markdown_to_card_v1,
    serialized_card_size,
    text_to_card_v1,
    validate_receive_id_type,
)

__all__ = [
    "FeishuAuth",
    "FeishuCardV1APIError",
    "FeishuCardV1Client",
    "FeishuCardV1ConfigError",
    "FeishuCardV1PayloadTooLarge",
    "FeishuCardV1SDKError",
    "FeishuCredentials",
    "FeishuTarget",
    "build_card_v1",
    "markdown_to_card_v1",
    "serialized_card_size",
    "text_to_card_v1",
    "validate_receive_id_type",
]
