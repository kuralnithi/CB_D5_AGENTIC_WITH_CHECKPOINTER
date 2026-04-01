"""
Database connection pool with production-grade configuration.

Production patterns:
- TCP keepalives to prevent Neon serverless from dropping idle connections
- Connection health check before lending (detects dead connections early)
- Bounded pool with aggressive idle recycling
- Structured logging for pool lifecycle events
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from psycopg_pool import AsyncConnectionPool
from app.core.config import settings

logger = logging.getLogger("finbot.database")


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
            max_idle=30.0,           # Recycle connections idle for > 30s
            max_lifetime=300.0,      # Force-recycle after 5 minutes
            timeout=30.0,            # Wait up to 30s for a connection
            reconnect_timeout=30.0,  # Keep trying to reconnect for 30s
            check=AsyncConnectionPool.check_connection,  # Ping before lending
            open=False               # Don't open at import time
        )
        logger.debug("Database pool configured", extra={
            "max_size": 10, "min_size": 1, "max_idle": 30.0, "max_lifetime": 300.0
        })

    async def open(self):
        if not self._pool._opened:
            await self._pool.open()
            logger.info("Database pool opened")

    async def close(self):
        if self._pool._opened:
            await self._pool.close()
            logger.info("Database pool closed")

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
        pass
