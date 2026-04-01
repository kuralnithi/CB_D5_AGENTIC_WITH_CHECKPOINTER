"""
FinBot API — Production-grade FastAPI application.

Production patterns implemented:
1. Structured JSON logging (Datadog/CloudWatch ready)
2. Request ID tracing (X-Request-ID header on every response)
3. Deep health checks (pings DB, returns component status + latency)
4. Request timeout middleware (504 after configured seconds)
5. Graceful shutdown (drain in-flight requests before closing DB)
6. CORS with configurable origins
"""

import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import os
import time
import uuid
import signal
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import finance
from app.core.database import db
from app.core.config import settings
from app.core.logging_config import setup_logging

# ── Initialize logging FIRST ─────────────────────────────────────────────────
setup_logging(log_level=settings.LOG_LEVEL, environment=settings.ENVIRONMENT)
logger = logging.getLogger("finbot.app")


# ── Lifespan (startup/shutdown) ──────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    logger.info("FinBot API starting up", extra={
        "environment": settings.ENVIRONMENT,
        "log_level": settings.LOG_LEVEL,
    })
    await db.open()
    logger.info("Database pool opened")

    yield

    # ── Shutdown ──
    logger.info("FinBot API shutting down — draining connections...")
    await db.close()
    logger.info("Database pool closed. Goodbye.")


app = FastAPI(
    title="FinBot API",
    description="AI-powered Financial Analyst API",
    version="1.0.0",
    lifespan=lifespan
)


# ── Middleware 1: Request ID Tracing ─────────────────────────────────────────
# Every request gets a unique ID for end-to-end tracing across logs.
# The client can also send their own X-Request-ID to correlate frontend↔backend.
class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Use client-provided ID or generate one
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# ── Middleware 2: Request Logging + Timing ───────────────────────────────────
# Log every request with method, path, status code, and latency.
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start = time.monotonic()

        response = await call_next(request)

        latency_ms = round((time.monotonic() - start) * 1000)
        request_id = getattr(request.state, "request_id", "unknown")

        # Skip logging health checks to reduce noise
        if request.url.path not in ("/health", "/"):
            logger.info(
                f"{request.method} {request.url.path} → {response.status_code}",
                extra={
                    "method": request.method,
                    "path": str(request.url.path),
                    "status_code": response.status_code,
                    "latency_ms": latency_ms,
                    "request_id": request_id,
                }
            )
        return response


# ── Middleware 3: Request Timeout ────────────────────────────────────────────
# Abort requests that take longer than REQUEST_TIMEOUT seconds.
# Returns 504 Gateway Timeout instead of hanging forever.
class TimeoutMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, timeout: int = 60):
        super().__init__(app)
        self.timeout = timeout

    async def dispatch(self, request: Request, call_next):
        # Don't timeout health checks
        if request.url.path in ("/health", "/"):
            return await call_next(request)

        try:
            return await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout
            )
        except asyncio.TimeoutError:
            request_id = getattr(request.state, "request_id", "unknown")
            logger.error(
                f"Request timed out after {self.timeout}s",
                extra={
                    "method": request.method,
                    "path": str(request.url.path),
                    "request_id": request_id,
                    "timeout": self.timeout,
                }
            )
            return JSONResponse(
                status_code=504,
                content={
                    "detail": f"Request timed out after {self.timeout} seconds",
                    "request_id": request_id,
                }
            )


# ── Register Middleware (order matters: last added = first executed) ──────────
app.add_middleware(TimeoutMiddleware, timeout=settings.REQUEST_TIMEOUT)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routes ────────────────────────────────────────────────────────────────────
app.include_router(finance.router, prefix="/api", tags=["finance"])


@app.get("/health", tags=["health"])
async def health_check():
    """
    Deep health check — actually pings the database.

    Production pattern: Returns structured health with per-component status
    and latency. Kubernetes & Railway use this to restart unhealthy pods.
    Returns 200 if healthy, 503 if any critical component is down.
    """
    health = {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
        "checks": {}
    }

    # ── Check Database ──
    try:
        start = time.monotonic()
        async with db.get_pool().connection() as conn:
            await conn.execute("SELECT 1")
        latency = round((time.monotonic() - start) * 1000)
        health["checks"]["database"] = {"status": "up", "latency_ms": latency}
    except Exception as e:
        logger.error("Health check: database unreachable", extra={"error": str(e)})
        health["checks"]["database"] = {"status": "down", "error": str(e)[:200]}
        health["status"] = "unhealthy"

    status_code = 200 if health["status"] == "healthy" else 503
    return JSONResponse(content=health, status_code=status_code)


@app.get("/")
def root():
    return {"message": "FinBot API is running 🚀", "version": "1.0.0"}