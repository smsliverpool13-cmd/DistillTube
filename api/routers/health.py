"""Health check endpoints."""
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    """Check API health status."""
    return {"status": "ok", "message": "Distill API is running"}
