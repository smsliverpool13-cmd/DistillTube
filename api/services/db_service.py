"""Database service using Supabase."""
import logging
from typing import Optional
from supabase import create_client, Client

logger = logging.getLogger(__name__)


class DBService:
    def __init__(self, supabase_url: str, supabase_key: str):
        self.client: Client = create_client(supabase_url, supabase_key)
        logger.info("Database service initialized with Supabase")

    def save_video(self, video_id: str, url: str, title: str, channel: str,
                   duration: int, thumbnail_url: str, transcript: list,
                   user_id: str, status: str = "pending") -> dict:
        data = {
            "id": video_id,
            "url": url,
            "title": title,
            "channel": channel,
            "duration": duration,
            "thumbnail_url": thumbnail_url,
            "status": status,
            "transcript": transcript,
            "user_id": user_id,
        }
        result = self.client.table("videos").upsert(data).execute()
        return result.data[0] if result.data else {}

    def update_status(self, video_id: str, status: str):
        self.client.table("videos").update({"status": status}).eq("id", video_id).execute()

    def get_video(self, video_id: str) -> Optional[dict]:
        result = self.client.table("videos").select("*").eq("id", video_id).execute()
        return result.data[0] if result.data else None

    def list_videos(self, user_id: str, limit: int = 20, offset: int = 0) -> list:
        result = (
            self.client.table("videos")
            .select("id, url, title, channel, duration, thumbnail_url, status, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        return result.data or []

    def delete_video(self, video_id: str):
        self.client.table("summaries").delete().eq("video_id", video_id).execute()
        self.client.table("videos").delete().eq("id", video_id).execute()

    def save_summary(self, video_id: str, summary: str, key_moments: list,
                     topics: list, linkedin_post: str, tweet_thread: list):
        data = {
            "video_id": video_id,
            "summary": summary,
            "key_moments": key_moments,
            "topics": topics,
            "linkedin_post": linkedin_post,
            "tweet_thread": tweet_thread,
        }
        self.client.table("summaries").upsert(data, on_conflict="video_id").execute()

    def get_summary(self, video_id: str) -> Optional[dict]:
        result = self.client.table("summaries").select("*").eq("video_id", video_id).execute()
        return result.data[0] if result.data else None


_db_service: Optional[DBService] = None


def get_db_service() -> DBService:
    global _db_service
    if _db_service is None:
        from config import settings
        _db_service = DBService(settings.supabase_url, settings.supabase_service_key)
    return _db_service
