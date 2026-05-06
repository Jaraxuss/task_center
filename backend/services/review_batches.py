"""Review batch (V2) domain services."""

from __future__ import annotations

from models import ReviewBatch
from schemas import ReviewBatchRead


def serialize_review_batch(batch: ReviewBatch) -> ReviewBatchRead:
    return ReviewBatchRead(
        id=batch.id,
        batch_type=batch.batch_type,
        title=batch.title,
        period_start=batch.period_start,
        period_end=batch.period_end,
        status=batch.status,
        material_count=batch.material_count,
        created_by=batch.created_by,
        created_at=batch.created_at,
        updated_at=batch.updated_at,
    )


__all__ = ["serialize_review_batch"]
