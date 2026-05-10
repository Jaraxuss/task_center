"""drop tasks.project column

Revision ID: a1b2c3d4e5f6
Revises: 612481f0ad55
Create Date: 2026-05-10 23:00:00.000000

Pre-condition: all tasks with a project string must have been backfilled
to project_id. The upgrade() function verifies this with a safety check
and aborts if any unbackfilled rows remain.

Run the backfill first:
    python backend/scripts/backfill_task_project_id.py --apply
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: str | Sequence[str] | None = '612481f0ad55'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop tasks.project after verifying backfill is complete."""
    conn = op.get_bind()
    unbackfilled = conn.execute(
        sa.text(
            "SELECT count(*) FROM tasks "
            "WHERE project IS NOT NULL AND project_id IS NULL"
        )
    ).scalar()
    if unbackfilled:
        raise RuntimeError(
            f"Cannot drop tasks.project: {unbackfilled} row(s) still have "
            f"project IS NOT NULL AND project_id IS NULL.  "
            f"Run backfill_task_project_id.py --apply first."
        )

    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_index("ix_tasks_project")
        batch_op.drop_column("project")


def downgrade() -> None:
    """Re-add tasks.project column (data will be lost)."""
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(
            sa.Column("project", sa.String(128), nullable=True)
        )
        batch_op.create_index("ix_tasks_project", ["project"])
