"""Knowledge module domain services."""

from __future__ import annotations

import json
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from models import Customer, Fact, KnowledgePreference, Project
from schemas import (
    KnowledgeFactCustomerOverview,
    KnowledgeFactProjectOverview,
    KnowledgeFactsOverview,
    KnowledgePreferenceRead,
)

_NULL_CUSTOMER_NAME = "未关联客户"
_UNASSIGNED_PROJECT_NAME = "未归项目"


def build_facts_overview(
    db: Session,
    status: str | None = None,
) -> KnowledgeFactsOverview:
    stmt = select(Fact)
    if status:
        stmt = stmt.where(Fact.status == status)

    facts = db.scalars(stmt).all()

    customer_ids: set[int | None] = set()
    project_ids: set[int | None] = set()
    for f in facts:
        customer_ids.add(f.customer_id)
        project_ids.add(f.project_id)

    customers: dict[int | None, Customer | None] = {}
    projects: dict[int | None, Project | None] = {}

    known_cids = [cid for cid in customer_ids if cid is not None]
    if known_cids:
        for c in db.scalars(select(Customer).where(Customer.id.in_(known_cids))).all():
            customers[c.id] = c

    known_pids = [pid for pid in project_ids if pid is not None]
    if known_pids:
        for p in db.scalars(select(Project).where(Project.id.in_(known_pids))).all():
            projects[p.id] = p

    # Aggregate: customer_id -> project_id -> {count, latest}
    agg: dict[int | None, dict[int | None, tuple[int, str | None]]] = defaultdict(
        lambda: defaultdict(lambda: (0, None))
    )

    for f in facts:
        cid = f.customer_id
        pid = f.project_id
        current_count, current_latest = agg[cid][pid]
        agg[cid][pid] = (current_count + 1, _max_dt(current_latest, f.fact_date))

    total_fact_count = len(facts)

    customer_overviews: list[KnowledgeFactCustomerOverview] = []
    for cid in sorted(agg.keys(), key=lambda k: (k is None, k or 0)):
        project_aggs = agg[cid]
        customer_fact_count = sum(cnt for cnt, _ in project_aggs.values())
        customer_latest = _max_dt(
            *(latest for _, latest in project_aggs.values() if latest is not None),
        )

        project_overviews: list[KnowledgeFactProjectOverview] = []
        for pid in sorted(project_aggs.keys(), key=lambda k: (_pid_sort_score(project_aggs[k][1]), k is None, k or 0)):
            cnt, latest = project_aggs[pid]
            proj = projects.get(pid)
            project_overviews.append(
                KnowledgeFactProjectOverview(
                    project_id=pid,
                    project_name=_UNASSIGNED_PROJECT_NAME if pid is None else (proj.name if proj else f"项目 #{pid}"),
                    status=proj.status if proj else None,
                    fact_count=cnt,
                    latest_fact_at=_to_iso_or_none(latest),
                )
            )

        # Sort projects: latest_fact_at desc, unassigned last
        project_overviews.sort(
            key=lambda p: (
                p.latest_fact_at is None,
                _iso_sort_score(p.latest_fact_at),
                p.project_id is None,
                p.project_id or 0,
            )
        )

        cust = customers.get(cid)
        customer_overviews.append(
            KnowledgeFactCustomerOverview(
                customer_id=cid,
                customer_name=_NULL_CUSTOMER_NAME if cid is None else (cust.name if cust else f"客户 #{cid}"),
                area=cust.area if cust else None,
                fact_count=customer_fact_count,
                project_count=len(project_overviews),
                latest_fact_at=_to_iso_or_none(customer_latest),
                projects=project_overviews,
            )
        )

    # Sort customers: latest_fact_at desc, null customer last
    customer_overviews.sort(
        key=lambda c: (
            c.latest_fact_at is None,
            _iso_sort_score(c.latest_fact_at),
            c.customer_id is None,
            c.customer_id or 0,
        )
    )

    return KnowledgeFactsOverview(
        total_fact_count=total_fact_count,
        customers=customer_overviews,
    )


def _max_dt(*values: str | None) -> str | None:
    result: str | None = None
    for v in values:
        if v is None:
            continue
        if result is None or v > result:
            result = v
    return result


def _to_iso_or_none(dt) -> str | None:
    if dt is None:
        return None
    try:
        return dt.isoformat()
    except Exception:
        return str(dt)


def _iso_sort_score(iso: str | None) -> str:
    return iso if iso else ""


def _pid_sort_score(iso: str | None) -> str:
    return iso if iso else ""


# ── Knowledge preferences ──


def get_knowledge_preference(db: Session) -> KnowledgePreference:
    pref = db.scalar(select(KnowledgePreference).limit(1))
    if pref is None:
        pref = KnowledgePreference()
        db.add(pref)
        db.flush()
    return pref


def serialize_knowledge_preference(pref: KnowledgePreference) -> KnowledgePreferenceRead:
    try:
        pinned = [int(item) for item in json.loads(pref.pinned_customer_ids_json or "[]") if int(item) > 0]
    except Exception:
        pinned = []

    try:
        order = [int(item) for item in json.loads(pref.customer_order_ids_json or "[]") if int(item) > 0]
    except Exception:
        order = []

    normalized_pinned: list[int] = []
    for cid in pinned:
        if cid not in normalized_pinned:
            normalized_pinned.append(cid)

    normalized_order: list[int] = []
    for cid in order:
        if cid not in normalized_order:
            normalized_order.append(cid)

    return KnowledgePreferenceRead(
        pinned_customer_ids=normalized_pinned,
        customer_order_ids=normalized_order,
    )
