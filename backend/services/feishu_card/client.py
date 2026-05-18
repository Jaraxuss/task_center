"""Backward-compatible imports for Feishu Card JSON 2.0 client.

Canonical implementation lives in:
``backend/scripts/sdk/feishu-card-v2/feishu_card_v2/client.py``.
"""
from services.feishu_card._sdk_path import ensure_feishu_card_v2_sdk_path

ensure_feishu_card_v2_sdk_path()

from feishu_card_v2.client import *  # noqa: F401,F403,E402
