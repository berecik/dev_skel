"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import settings
from app.database import engine
from app.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    async with engine.begin() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.project_name,
    version=settings.version,
    lifespan=lifespan,
)

app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint returning project info."""
    return {
        "project": settings.project_name,
        "version": settings.version,
        "framework": "FastAPI",
        "status": "running",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}
