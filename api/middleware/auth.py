"""Auth middleware — validates Supabase JWT tokens."""
import logging
from fastapi import HTTPException, Header
from supabase import create_client
from config import settings

logger = logging.getLogger(__name__)


async def get_current_user(authorization: str = Header(...)) -> dict:
    """Extract and verify the user from the Authorization header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.replace("Bearer ", "")

    try:
        client = create_client(settings.supabase_url, settings.supabase_service_key)
        user = client.auth.get_user(token)
        if not user or not user.user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return {"id": user.user.id, "email": user.user.email}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")
