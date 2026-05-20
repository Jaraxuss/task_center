"""Schema compatibility / startup helpers.

This module contains the historical hand-written ALTER chain that brought
existing SQLite DBs forward into the v2 schema, plus a datetime storage
normalizer. Going forward, schema changes should be Alembic revisions; the
ensure_schema_compatibility code is retained as a safety net for production
DBs that were created before Alembic adoption.
"""

from __future__ import annotations

import sqlite3

from db import DATABASE_PATH as DB_PATH
from db import Base, engine
from timeutils import to_storage_string

DATETIME_COLUMNS: dict[str, list[str]] = {
    "tasks": ["due_at", "created_at", "updated_at", "completed_at", "canceled_at", "deferred_to", "nightly_reviewed_at"],
    "reminders": ["remind_at", "fired_at", "created_at", "updated_at"],
    "task_recurrences": ["start_at", "end_at", "next_run_at", "last_run_at", "created_at", "updated_at"],
    "task_events": ["created_at"],
    "customer_materials": ["material_date", "created_at", "updated_at", "archived_at", "period_start", "period_end"],
    "customers": ["created_at", "updated_at"],
    "projects": ["start_at", "target_end_at", "actual_end_at", "created_at", "updated_at"],
    "facts": ["fact_date", "created_at", "updated_at"],
    "review_batches": ["period_start", "period_end", "created_at", "updated_at"],
    "customer_material_facts": ["created_at"],
}


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    ensure_schema_compatibility()
    normalize_datetime_storage()


def ensure_schema_compatibility() -> None:
    if not DB_PATH.exists():
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()

        # --- tasks: add v2 columns ---
        cur.execute("PRAGMA table_info(tasks)")
        task_columns = {row[1] for row in cur.fetchall()}
        if "completion_note" not in task_columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN completion_note TEXT")
        if "area" not in task_columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN area VARCHAR(128)")
        if "customer_id" not in task_columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN customer_id INTEGER REFERENCES customers(id) ON DELETE SET NULL")
        if "project_id" not in task_columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN project_id INTEGER REFERENCES projects(id) ON DELETE SET NULL")
        if "source_type" not in task_columns:
            cur.execute("ALTER TABLE tasks ADD COLUMN source_type VARCHAR(32)")

        # --- reminders: add delivery fields ---
        cur.execute("PRAGMA table_info(reminders)")
        reminder_columns = {row[1] for row in cur.fetchall()}
        reminder_cols = {
            "delivery_mode": "VARCHAR(32)",
            "receive_id": "VARCHAR(128)",
            "receive_id_type": "VARCHAR(32)",
            "external_cron_job_id": "VARCHAR(128)",
            "message_id": "VARCHAR(128)",
            "request_uuid": "VARCHAR(128)",
            "fired_at": "TEXT",
            "last_error": "TEXT",
            "retry_count": "INTEGER NOT NULL DEFAULT 0",
            "ai_prompt": "TEXT",
        }
        for col_name, col_def in reminder_cols.items():
            if col_name not in reminder_columns:
                cur.execute(f"ALTER TABLE reminders ADD COLUMN {col_name} {col_def}")

        # --- board_preferences ---
        cur.execute("PRAGMA table_info(board_preference)")
        board_preference_columns = {row[1] for row in cur.fetchall()}
        if board_preference_columns and "project_order_json" not in board_preference_columns:
            cur.execute("ALTER TABLE board_preferences ADD COLUMN project_order_json TEXT NOT NULL DEFAULT '[]'")

        # --- knowledge_preferences ---
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='knowledge_preferences'")
        if not cur.fetchone():
            cur.execute("""
                CREATE TABLE knowledge_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pinned_customer_ids_json TEXT NOT NULL DEFAULT '[]',
                    customer_order_ids_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)

        # --- customer_materials: add v2 columns ---
        cur.execute("PRAGMA table_info(customer_materials)")
        cm_columns = {row[1] for row in cur.fetchall()}
        v2_cm_cols = {
            "customer_id": "INTEGER REFERENCES customers(id) ON DELETE SET NULL",
            "project_v2_id": "INTEGER REFERENCES projects(id) ON DELETE SET NULL",
            "review_batch_id": "INTEGER REFERENCES review_batches(id) ON DELETE SET NULL",
            "material_type": "VARCHAR(32) DEFAULT 'period_summary'",
            "period_start": "TEXT",
            "period_end": "TEXT",
            "raw_facts_markdown": "TEXT",
            "generation_meta_json": "TEXT",
        }
        for col_name, col_def in v2_cm_cols.items():
            if col_name not in cm_columns:
                cur.execute(f"ALTER TABLE customer_materials ADD COLUMN {col_name} {col_def}")

        # --- customer_materials: drop deprecated columns (2026-05-04 Phase 2) ---
        # Step 1: back-fill raw_facts_markdown from legacy fields if empty, so no content is lost
        #   when the legacy columns are dropped below. Priority order matches the data ownership
        #   progression: candidate > raw_source > summary > insights.
        try:
            cur.execute(
                """
                UPDATE customer_materials
                SET raw_facts_markdown = COALESCE(
                    NULLIF(raw_facts_markdown, ''),
                    NULLIF(candidate_markdown, ''),
                    NULLIF(raw_source_markdown, ''),
                    NULLIF(summary_markdown, ''),
                    NULLIF(insights_markdown, '')
                )
                WHERE (raw_facts_markdown IS NULL OR raw_facts_markdown = '')
                """
            )
        except sqlite3.OperationalError:
            # At least one legacy column already gone; the COALESCE is best-effort.
            pass
        # Step 2: drop deprecated columns one by one (requires SQLite >= 3.35).
        for deprecated_col in (
            "raw_source_markdown",
            "candidate_markdown",
            "summary_markdown",
            "insights_markdown",
            "review_note",
        ):
            try:
                cur.execute(f"ALTER TABLE customer_materials DROP COLUMN {deprecated_col}")
            except sqlite3.OperationalError:
                # Column no longer present (already dropped in a previous run).
                pass

        conn.commit()
    finally:
        conn.close()


def normalize_datetime_storage() -> None:
    if not DB_PATH.exists():
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        for table, columns in DATETIME_COLUMNS.items():
            for column in columns:
                cur.execute(f"SELECT rowid, {column} FROM {table} WHERE {column} IS NOT NULL")
                updates: list[tuple[str, int]] = []
                for rowid, raw_value in cur.fetchall():
                    if raw_value is None:
                        continue
                    normalized = to_storage_string(raw_value)
                    if normalized and normalized != raw_value:
                        updates.append((normalized, rowid))
                if updates:
                    cur.executemany(f"UPDATE {table} SET {column}=? WHERE rowid=?", updates)
        conn.commit()
    finally:
        conn.close()
