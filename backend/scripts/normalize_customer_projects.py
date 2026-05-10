"""ARCHIVED: This script relied on the legacy PATCH /api/projects/rename
endpoint which has been removed. Project renaming now goes through the V2
project model. Kept for historical reference only.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from db import SessionLocal  # noqa: E402
from models import Task  # noqa: E402

EXCLUDED_PROJECTS = {"生活", "闲鱼", "影刀6.0灰度"}
CUSTOMER_PREFIX = "客户_"
CUSTOMER_TAG = "客户"


def load_tags(task: Task) -> list[str]:
    return list(task.tags or [])


def main() -> None:
    print("ERROR: This script is archived. The PATCH /api/projects/rename")
    print("endpoint has been removed. Use the V2 project model to rename projects.")
    sys.exit(1)


if __name__ == "__main__":
    main()
