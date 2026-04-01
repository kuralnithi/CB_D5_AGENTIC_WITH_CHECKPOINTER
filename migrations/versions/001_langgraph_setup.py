"""langgraph_checkpointer_setup

Revision ID: 001_langgraph_setup
Revises:
Create Date: 2026-03-24

Sets up the LangGraph PostgreSQL checkpointer schema.

WHY NOT CONCURRENTLY IN MIGRATION?
  CREATE INDEX CONCURRENTLY is for adding indexes to large LIVE tables
  WITHOUT blocking reads/writes. It is used in production when:
    - The table has millions of rows
    - The app cannot suffer downtime

  In a CI/CD deployment pipeline (the industry-standard approach), you would:
    1. Stop/drain new traffic from the app (zero-downtime deploy strategy)
    2. Run this migration with a separate AUTOCOMMIT connection
    3. Start the new app version

  For initial setup (empty tables), a regular CREATE INDEX is identical in 
  effect to CONCURRENTLY and does not require AUTOCOMMIT. This is what we 
  do here since the tables are brand new and empty.
"""
from alembic import op

revision = '001_langgraph_setup'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # All DDL runs inside Alembic's transaction — safe and correct
    op.execute("""
        CREATE TABLE IF NOT EXISTS checkpoint_migrations (
            v INTEGER PRIMARY KEY
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS checkpoints (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL,
            parent_checkpoint_id TEXT,
            type TEXT,
            checkpoint JSONB NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}',
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS checkpoint_blobs (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            channel TEXT NOT NULL,
            version TEXT NOT NULL,
            type TEXT NOT NULL,
            blob BYTEA,
            PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS checkpoint_writes (
            thread_id TEXT NOT NULL,
            checkpoint_ns TEXT NOT NULL DEFAULT '',
            checkpoint_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            task_path TEXT NOT NULL DEFAULT '',
            idx INTEGER NOT NULL,
            channel TEXT NOT NULL,
            type TEXT,
            blob BYTEA NOT NULL,
            PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
        )
    """)
    op.execute("ALTER TABLE checkpoint_blobs ALTER COLUMN blob DROP NOT NULL")

    # Regular index creation for new/empty tables — no CONCURRENTLY needed.
    # In production for existing large tables, this migration should be run
    # while the app is drained, or via a separate AUTOCOMMIT connection.
    op.execute("CREATE INDEX IF NOT EXISTS checkpoints_thread_id_idx ON checkpoints(thread_id)")
    op.execute("CREATE INDEX IF NOT EXISTS checkpoint_blobs_thread_id_idx ON checkpoint_blobs(thread_id)")
    op.execute("CREATE INDEX IF NOT EXISTS checkpoint_writes_thread_id_idx ON checkpoint_writes(thread_id)")

    # Mark LangGraph's internal migration table as fully applied (v=20)
    op.execute("INSERT INTO checkpoint_migrations (v) VALUES (20) ON CONFLICT DO NOTHING")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS checkpoints_thread_id_idx")
    op.execute("DROP INDEX IF EXISTS checkpoint_blobs_thread_id_idx")
    op.execute("DROP INDEX IF EXISTS checkpoint_writes_thread_id_idx")
    op.execute("DROP TABLE IF EXISTS checkpoint_writes")
    op.execute("DROP TABLE IF EXISTS checkpoint_blobs")
    op.execute("DROP TABLE IF EXISTS checkpoints")
    op.execute("DROP TABLE IF EXISTS checkpoint_migrations")
