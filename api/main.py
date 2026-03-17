"""Main FastAPI application for Distill."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from config import settings
from routers import health, videos, chat, transcript, summary
from services.qdrant_service import get_qdrant_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown events."""
    # Startup
    logger.info("Starting Distill API...")
    try:
        qdrant_service = get_qdrant_service()
        logger.info(f"Qdrant service initialized: {settings.qdrant_url}")
    except Exception as e:
        logger.warning(f"Failed to initialize Qdrant (will retry on use): {e}")

    yield

    # Shutdown
    logger.info("Shutting down Distill API...")


app = FastAPI(
    title="Distill API",
    description="YouTube Knowledge Assistant",
    version="0.1.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://distilltube.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router)
app.include_router(videos.router)
app.include_router(chat.router)
app.include_router(transcript.router)
app.include_router(summary.router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Distill API",
        "description": "YouTube Knowledge Assistant",
        "version": "0.1.0",
        "endpoints": {
            "health": "/health",
            "videos": "/videos",
            "transcript": "/transcript",
            "summary": "/summary",
            "chat": "/chat",
        },
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=settings.fastapi_port,
        reload=settings.fastapi_reload,
    )
