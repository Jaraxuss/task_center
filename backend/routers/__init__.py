"""HTTP routers.

Each module exposes an ``APIRouter`` that wires URL routes to service
helpers. Routers are intentionally thin: they only handle parameter
binding, validation, calling services, and HTTP-layer concerns
(status codes, response models). Domain logic lives in ``services/``.
"""
