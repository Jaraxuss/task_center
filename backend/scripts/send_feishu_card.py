#!/usr/bin/env python3
"""Backward-compatible wrapper for the Feishu Card V2 smoke script.

Canonical script:
``backend/scripts/sdk/feishu-card-v2/send_card_v2.py``.
"""
from __future__ import annotations

import runpy
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "sdk" / "feishu-card-v2" / "send_card_v2.py"

if __name__ == "__main__":
    runpy.run_path(str(SCRIPT), run_name="__main__")
