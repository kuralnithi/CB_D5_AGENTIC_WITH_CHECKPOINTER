"""
Alembic env.py — Production-grade configuration.

Key design decisions:
1. DATABASE_URL is read from .env — never hardcoded or written to alembic.ini
   (alembic.ini uses ConfigParser which interprets '%' as interpolation,
    breaking passwords like 'Pasam123%40kural'. The fix: inject via set_main_option
    at runtime, bypassing the ini file's interpolation entirely.)
2. NullPool ensures each migration gets a fresh, isolated connection.
3. transaction_per_migration=True so each migration script is its own transaction.
   This is REQUIRED for CREATE INDEX CONCURRENTLY to work.
"""
import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context
from dotenv import load_dotenv

# Load .env
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ✅ KEY FIX: Inject DATABASE_URL at runtime using set_main_option().
# This bypasses alembic.ini's ConfigParser interpolation, which breaks
# on '%' characters in passwords (e.g. URL-encoded '@' = '%40').
raw_url = os.environ.get("DATABASE_URL", "").strip()

# Handle both 'postgres://' and 'postgresql://' prefixes.
# Also ensure we are using the 'psycopg' (v3) driver dialect.
if raw_url.startswith("postgres://"):
    db_url = raw_url.replace("postgres://", "postgresql+psycopg://", 1)
elif raw_url.startswith("postgresql://"):
    db_url = raw_url.replace("postgresql://", "postgresql+psycopg://", 1)
else:
    db_url = raw_url

# ConfigParser interprets '%' as interpolation syntax — escape it.
db_url_escaped = db_url.replace("%", "%%")

# Debug: Print the transformed URL prefix (safe for logs)
print(f"[alembic] Using database dialect: {db_url.split(':', 1)[0]}")

config.set_main_option("sqlalchemy.url", db_url_escaped)

target_metadata = None


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Production-grade online migration runner.
    NullPool = no connection reuse between migrations (safest for DDL).
    transaction_per_migration = each migration has its own BEGIN/COMMIT.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            transaction_per_migration=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
