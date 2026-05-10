"""drop customer_materials legacy columns

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-11 00:15:00.000000

Drops 6 legacy columns from customer_materials:
  project, source_type, source, source_refs_json, value_types_json, task_id

Pre-condition: all customer materials must have customer_id set (the V2
foreign key replaces the old project string).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: str | Sequence[str] | None = 'a1b2c3d4e5f6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop legacy columns after verifying all rows have customer_id."""
    conn = op.get_bind()
    orphaned = conn.execute(
        sa.text(
            "SELECT count(*) FROM customer_materials "
            "WHERE customer_id IS NULL"
        )
    ).scalar()
    if orphaned:
        raise RuntimeError(
            f"Cannot drop legacy columns: {orphaned} row(s) still have "
            f"customer_id IS NULL.  Backfill customer_id first."
        )

    with op.batch_alter_table("customer_materials") as batch_op:
        batch_op.drop_index("ix_customer_materials_project")
        batch_op.drop_index("ix_customer_materials_source_type")
        batch_op.drop_index("ix_customer_materials_task_id")
        batch_op.drop_constraint("fk_customer_materials_task_id_tasks", type_="foreignkey")
        batch_op.drop_column("project")
        batch_op.drop_column("source_type")
        batch_op.drop_column("source")
        batch_op.drop_column("source_refs_json")
        batch_op.drop_column("value_types_json")
        batch_op.drop_column("task_id")


def downgrade() -> None:
    """Re-add legacy columns (data will be lost)."""
    with op.batch_alter_table("customer_materials") as batch_op:
        batch_op.add_column(sa.Column("project", sa.String(128), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("source_type", sa.String(32), nullable=False, server_default="text"))
        batch_op.add_column(sa.Column("source", sa.String(32), nullable=False, server_default="chat"))
        batch_op.add_column(sa.Column("source_refs_json", sa.Text(), nullable=False, server_default="{}"))
        batch_op.add_column(sa.Column("value_types_json", sa.Text(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("task_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_customer_materials_project", ["project"])
        batch_op.create_index("ix_customer_materials_source_type", ["source_type"])
        batch_op.create_index("ix_customer_materials_task_id", ["task_id"])
        batch_op.create_foreign_key(
            "fk_customer_materials_task_id_tasks",
            "tasks",
            ["task_id"],
            ["id"],
            ondelete="SET NULL",
        )
