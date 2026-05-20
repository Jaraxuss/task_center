"""add reminder delivery fields

Revision ID: 9a7c1e2b4d6f
Revises: b2c3d4e5f6a7
Create Date: 2026-05-20 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa

import models
from alembic import op

# revision identifiers, used by Alembic.
revision = "9a7c1e2b4d6f"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The ORM still maps these legacy customer_materials columns for deployed
    # SQLite compatibility. Re-add them if a previous migration dropped them so
    # Alembic head stays aligned with Base.metadata.
    with op.batch_alter_table("customer_materials", schema=None) as batch_op:
        batch_op.add_column(sa.Column("project", sa.String(length=128), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("source_type", sa.String(length=32), nullable=False, server_default="text"))
        batch_op.add_column(sa.Column("source", sa.String(length=32), nullable=False, server_default="system"))
        batch_op.add_column(sa.Column("source_refs_json", sa.Text(), nullable=False, server_default="{}"))
        batch_op.add_column(sa.Column("value_types_json", sa.Text(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("task_id", sa.Integer(), nullable=True))

    with op.batch_alter_table("reminders", schema=None) as batch_op:
        batch_op.add_column(sa.Column("delivery_mode", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("receive_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("receive_id_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("external_cron_job_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("message_id", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("request_uuid", sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column("fired_at", models.UTCDateTimeText(), nullable=True))
        batch_op.add_column(sa.Column("last_error", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("ai_prompt", sa.Text(), nullable=True))
        batch_op.create_index(batch_op.f("ix_reminders_delivery_mode"), ["delivery_mode"], unique=False)
        batch_op.create_index(batch_op.f("ix_reminders_external_cron_job_id"), ["external_cron_job_id"], unique=False)

    with op.batch_alter_table("reminders", schema=None) as batch_op:
        batch_op.alter_column("retry_count", server_default=None)
    with op.batch_alter_table("customer_materials", schema=None) as batch_op:
        batch_op.alter_column("project", server_default=None)
        batch_op.alter_column("source_type", server_default=None)
        batch_op.alter_column("source", server_default=None)
        batch_op.alter_column("source_refs_json", server_default=None)
        batch_op.alter_column("value_types_json", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("reminders", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_reminders_external_cron_job_id"))
        batch_op.drop_index(batch_op.f("ix_reminders_delivery_mode"))
        batch_op.drop_column("ai_prompt")
        batch_op.drop_column("retry_count")
        batch_op.drop_column("last_error")
        batch_op.drop_column("fired_at")
        batch_op.drop_column("request_uuid")
        batch_op.drop_column("message_id")
        batch_op.drop_column("external_cron_job_id")
        batch_op.drop_column("receive_id_type")
        batch_op.drop_column("receive_id")
        batch_op.drop_column("delivery_mode")
    with op.batch_alter_table("customer_materials", schema=None) as batch_op:
        batch_op.drop_column("task_id")
        batch_op.drop_column("value_types_json")
        batch_op.drop_column("source_refs_json")
        batch_op.drop_column("source")
        batch_op.drop_column("source_type")
        batch_op.drop_column("project")
