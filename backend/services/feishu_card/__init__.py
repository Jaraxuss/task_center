"""TaskCenter Feishu Card V2 SDK.

Public entry points:
- ``FeishuCardClient`` for direct Feishu OpenAPI delivery.
- ``markdown_to_card_v2`` and ``text_to_card_v2`` for Card JSON 2.0 building.
"""
from services.feishu_card.card import (
    CARD_SIZE_LIMIT_BYTES,
    CardSize,
    FeishuCardError,
    FeishuCardPayloadTooLarge,
    build_card_v2,
    ensure_card_within_size_limit,
    extract_first_heading,
    markdown_elements,
    markdown_to_card_v2,
    serialized_card_size,
    split_markdown_by_hr,
    text_to_card_v2,
)
from services.feishu_card.client import (
    FeishuAPIError,
    FeishuAuth,
    FeishuCardClient,
    FeishuConfigError,
    FeishuCredentials,
    FeishuSDKError,
    FeishuTarget,
    post_json,
    validate_receive_id_type,
)

__all__ = [
    "CARD_SIZE_LIMIT_BYTES",
    "CardSize",
    "FeishuAPIError",
    "FeishuAuth",
    "FeishuCardClient",
    "FeishuCardError",
    "FeishuCardPayloadTooLarge",
    "FeishuConfigError",
    "FeishuCredentials",
    "FeishuSDKError",
    "FeishuTarget",
    "build_card_v2",
    "ensure_card_within_size_limit",
    "extract_first_heading",
    "markdown_elements",
    "markdown_to_card_v2",
    "post_json",
    "serialized_card_size",
    "split_markdown_by_hr",
    "text_to_card_v2",
    "validate_receive_id_type",
]
