import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import finance

from contextlib import asynccontextmanager
from app.core.database import db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Open the connection pool
    await db.open()
    yield
    # Shutdown: Close the connection pool
    await db.close()

app = FastAPI(
    title="FinBot API",
    description="AI-powered Financial Analyst API",
    version="1.0.0",
    lifespan=lifespan
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(finance.router, prefix="/api", tags=["finance"])

@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "HF Space is working 🚀"}