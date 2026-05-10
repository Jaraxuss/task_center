#!/usr/bin/env python3
"""Dump the current FastAPI OpenAPI spec to stdout as JSON.

Usage:
    python scripts/dump_openapi.py > ../mobile_frontend/openapi.json
"""

from __future__ import annotations

import json
import sys

from main import app

json.dump(app.openapi(), sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
sys.stdout.write("\n")
