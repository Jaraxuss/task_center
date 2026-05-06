"""Application services.

Each module here contains pure-logic helpers (DB queries, serializers,
business rules). Routers in ``routers/`` orchestrate these services to
respond to HTTP requests.

No module in ``services/`` should import FastAPI primitives like
``Depends``/``Query``/``HTTPException`` directly into the public API
surface (``HTTPException`` is okay to raise from within a service when
the resulting status code is the right cross-cutting concern, e.g. 404
for "not found"; see ``get_task_or_404``).
"""
