import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from psycopg_pool import AsyncConnectionPool
from app.core.config import settings

# For a production app, we use a connection pool to manage DB resources efficiently.
# Using AsyncConnectionPool for better performance with FastAPI.

class Database:
    def __init__(self, dsn: str):
        self._pool = AsyncConnectionPool(
            conninfo=dsn,
            max_size=20,
            min_size=1,  # Lower minimum so we don't hoard stale connections
            max_idle=60.0,  # Recycle connections that are idle for 60 seconds
            max_lifetime=300.0,  # Force disconnect after 5 minutes (prevents Neon proxy drops)
            kwargs={
                "keepalives": 1,
                "keepalives_idle": 30,
                "keepalives_interval": 10,
                "keepalives_count": 5
            },
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
