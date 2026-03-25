import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from psycopg_pool import AsyncConnectionPool
from app.core.config import settings

# For a production app, we use a connection pool to manage DB resources efficiently.
# Using AsyncConnectionPool for better performance with FastAPI.

class Database:
    def __init__(self, dsn: str):
        # Neon serverless drops idle SSL connections aggressively.
        # We inject TCP keepalive parameters directly into the DSN string
        # (psycopg3 reads them from conninfo, not from kwargs).
        neon_safe_dsn = dsn
        if "keepalives" not in dsn:
            sep = "&" if "?" in dsn else "?"
            neon_safe_dsn = (
                f"{dsn}{sep}"
                "keepalives=1"
                "&keepalives_idle=30"
                "&keepalives_interval=10"
                "&keepalives_count=5"
            )

        self._pool = AsyncConnectionPool(
            conninfo=neon_safe_dsn,
            max_size=10,
            min_size=1,
            max_idle=60.0,    # Recycle connections idle for > 60s before Neon drops them
            max_lifetime=300.0,  # Force-recycle after 5 minutes
            timeout=30.0,
            open=False  # Don't open it immediately
        )

    async def open(self):
        if not self._pool._opened:
            await self._pool.open()

    async def close(self):
        if self._pool._opened:
            await self._pool.close()

    def get_pool(self) -> AsyncConnectionPool:
        return self._pool

db = Database(settings.DATABASE_URL)

@asynccontextmanager
async def get_db_pool() -> AsyncGenerator[AsyncConnectionPool, None]:
    """Dependency for getting the database pool."""
    await db.open()
    try:
        yield db.get_pool()
    finally:
        # For long running app, we don't necessarily close the pool here
        # but the app lifecycle handles it.
        pass
