"""Compatibility path helper for the canonical Feishu Card V2 SDK."""
from __future__ import annotations

import sys
from pathlib import Path


def ensure_feishu_card_v2_sdk_path() -> None:
    sdk_dir = Path(__file__).resolve().parents[2] / "scripts" / "sdk" / "feishu-card-v2"
    if str(sdk_dir) not in sys.path:
        sys.path.insert(0, str(sdk_dir))
