"""Task Center backend FastAPI application.

This module is intentionally thin: it wires the FastAPI app together
(lifespan, CORS, routers) and re-exports a handful of helpers that legacy
scripts/tests still import directly. Domain logic lives in ``services/``
and HTTP routes are split per-domain under ``routers/``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from routers import (
    customer_materials as customer_materials_router,
)
from routers import (
    customers as customers_router,
)
from routers import (
    dashboard as dashboard_router,
)
from routers import (
    facts as facts_router,
)
from routers import (
    health as health_router,
)
from routers import (
    knowledge as knowledge_router,
)
from routers import (
    preferences as preferences_router,
)
from routers import (
    projects as projects_router,
)
from routers import (
    review_batches as review_batches_router,
)
from routers import (
    tasks as tasks_router,
)
from services.schema_compat import (
    ensure_schema_compatibility,
    init_db,
    normalize_datetime_storage,
)
from services.tasks import add_event

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="Task Center Backend", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(health_router.router)
app.include_router(preferences_router.router)
app.include_router(knowledge_router.router)
app.include_router(projects_router.router)
app.include_router(projects_router.legacy_v2_router)
app.include_router(tasks_router.router)
app.include_router(dashboard_router.router)
app.include_router(customer_materials_router.router)
app.include_router(customers_router.router)
app.include_router(facts_router.router)
app.include_router(review_batches_router.router)


# Re-exports for backwards compatibility with seed scripts and ad-hoc tools
# that historically imported these names from ``main``. New callers should
# import from ``services.*`` / ``routers.*`` directly.
update_task = tasks_router.update_task

__all__ = [
    "add_event",
    "app",
    "ensure_schema_compatibility",
    "init_db",
    "lifespan",
    "normalize_datetime_storage",
    "settings",
    "update_task",
]


if __name__ == "__main__":
    import uvicorn

    init_db()
    uvicorn.run("main:app", host=settings.api_host, port=settings.api_port, reload=True)
