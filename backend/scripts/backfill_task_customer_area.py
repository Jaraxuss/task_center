"""Backfill tasks.customer_id / area / project (canonical) based on customers table.

策略（与用户讨论后确定）：
- area 枚举：customer / customer_ops / internal / personal
- B/F 类：重写 project 为 canonical "客户_<name>"
- C 类（客户跟进 / 客户交接 / 客户反馈）：area=customer, customer_id=NULL
- D 类内部 / E 类个人：按列表分流
- G 类（空 project）：跳过

使用：
  python3 backend/scripts/backfill_task_customer_area.py --dry-run
  python3 backend/scripts/backfill_task_customer_area.py --apply
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

DB_PATH = Path("backend/data/task_center.db")

# project 字面值的硬编码分类（C/D/E）
CUSTOMER_OPS_PROJECTS = {"客户跟进", "客户交接", "客户反馈"}
INTERNAL_PROJECTS = {"内部协同", "OpenClaw/TaskCenter", "NDR统计", "影刀6.0灰度", "内部_培训"}
PERSONAL_PROJECTS = {"生活", "个人事务", "出差", "闲鱼"}


def build_alias_map(cursor: sqlite3.Cursor) -> tuple[dict[str, int], dict[int, str]]:
    """返回 (alias_lower → customer_id, customer_id → canonical_name)。"""
    cursor.execute("SELECT id, name, aliases_json FROM customers")
    alias_to_id: dict[str, int] = {}
    id_to_name: dict[int, str] = {}
    for cid, name, aliases_json in cursor.fetchall():
        id_to_name[cid] = name
        candidates = {name, f"客户_{name}"}
        try:
            for a in json.loads(aliases_json or "[]"):
                if isinstance(a, str) and a.strip():
                    candidates.add(a.strip())
        except json.JSONDecodeError:
            pass
        for a in candidates:
            key = a.lower()
            # 第一次写入优先；冲突时跳过并打印
            if key in alias_to_id and alias_to_id[key] != cid:
                print(f"[warn] alias collision: {a!r} 同时指向 cid={alias_to_id[key]} 和 cid={cid}", file=sys.stderr)
                continue
            alias_to_id[key] = cid
    return alias_to_id, id_to_name


def resolve_customer(project: str, alias_to_id: dict[str, int]) -> int | None:
    """尝试把 project 字符串解析成 customer_id。"""
    if not project:
        return None
    candidates = [project]
    if project.startswith("客户_"):
        candidates.append(project[len("客户_"):])
    for c in candidates:
        cid = alias_to_id.get(c.lower())
        if cid is not None:
            return cid
    return None


def classify_task(project: str | None, alias_to_id: dict[str, int], id_to_name: dict[int, str]):
    """返回 (area, customer_id, new_project) 或 None 表示跳过。"""
    if not project:
        return None  # G 类，跳过

    # C 类：客户运营标签
    if project in CUSTOMER_OPS_PROJECTS:
        return ("customer", None, project)

    # D 类：内部
    if project in INTERNAL_PROJECTS:
        return ("internal", None, project)

    # E 类：个人
    if project in PERSONAL_PROJECTS:
        return ("personal", None, project)

    # A/B/F 类：尝试解析为客户
    cid = resolve_customer(project, alias_to_id)
    if cid is not None:
        canonical = f"客户_{id_to_name[cid]}"
        return ("customer", cid, canonical)

    # 未匹配上 → 不分类，跳过并打印警告
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="实际写入；不加则 dry-run")
    parser.add_argument("--db", default=str(DB_PATH))
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    cursor = conn.cursor()

    alias_to_id, id_to_name = build_alias_map(cursor)
    print(f"loaded {len(id_to_name)} customers / {len(alias_to_id)} aliases")

    cursor.execute("SELECT id, title, project, customer_id, area FROM tasks ORDER BY id")
    tasks = cursor.fetchall()

    counts = {"customer": 0, "customer_ops": 0, "internal": 0, "personal": 0,
              "skipped_empty": 0, "skipped_unknown": 0, "no_change": 0}
    updates: list[tuple] = []
    unknown: list[tuple] = []

    for tid, title, project, old_cid, old_area in tasks:
        result = classify_task(project, alias_to_id, id_to_name)
        if result is None:
            # 空 project 但已有 customer_id：补 area='customer'，project 留空
            if not project and old_cid is not None and old_cid in id_to_name:
                result = ("customer", old_cid, project or "")
            else:
                if not project:
                    counts["skipped_empty"] += 1
                else:
                    counts["skipped_unknown"] += 1
                    unknown.append((tid, title, project))
                continue

        area, new_cid, new_project = result
        if area == "customer" and new_cid is None:
            counts["customer_ops"] += 1
        else:
            counts[area] += 1

        if (old_cid == new_cid) and (old_area == area) and (project == new_project):
            counts["no_change"] += 1
            continue

        updates.append((tid, title, project, new_project, old_cid, new_cid, old_area, area))

    print("\n=== summary ===")
    for k, v in counts.items():
        print(f"  {k}: {v}")
    print(f"  pending updates: {len(updates)}")

    if unknown:
        print("\n=== unknown projects (will skip) ===")
        for tid, title, project in unknown:
            print(f"  task#{tid} project={project!r} title={title!r}")

    print("\n=== sample updates (first 30) ===")
    for row in updates[:30]:
        tid, title, oldp, newp, oldc, newc, olda, newa = row
        proj_change = f"{oldp!r} → {newp!r}" if oldp != newp else f"{oldp!r}"
        print(f"  task#{tid} project={proj_change} customer_id={oldc}→{newc} area={olda}→{newa} | {title}")

    if not args.apply:
        print("\n[dry-run] 未写入。加 --apply 真正执行。")
        return

    if not updates:
        print("\nnothing to apply.")
        return

    now_iso = datetime.utcnow().isoformat(timespec="microseconds") + "Z"
    for tid, _title, _oldp, new_project, _oldc, new_cid, _olda, new_area in updates:
        cursor.execute(
            "UPDATE tasks SET project = ?, customer_id = ?, area = ?, updated_at = ? WHERE id = ?",
            (new_project, new_cid, new_area, now_iso, tid),
        )
    conn.commit()
    print(f"\napplied {len(updates)} updates.")
    conn.close()


if __name__ == "__main__":
    main()
