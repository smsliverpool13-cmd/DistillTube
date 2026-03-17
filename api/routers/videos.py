"""Video library endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List

from services.db_service import get_db_service
from middleware.auth import get_current_user

router = APIRouter(prefix="/videos", tags=["videos"])


class VideoListItem(BaseModel):
    video_id: str
    url: str
    title: str
    channel: str
    duration: int
    thumbnail_url: str
    status: str
    created_at: str


class VideoListResponse(BaseModel):
    videos: List[VideoListItem]
    total: int


@router.get("", response_model=VideoListResponse)
async def list_videos(limit: int = 50, offset: int = 0,
                      current_user: dict = Depends(get_current_user)):
    """List all saved videos ordered by most recent."""
    db = get_db_service()
    rows = db.list_videos(user_id=current_user["id"], limit=limit, offset=offset)
    videos = [
        VideoListItem(
            video_id=r["id"],
            url=r["url"],
            title=r["title"],
            channel=r.get("channel", ""),
            duration=r["duration"],
            thumbnail_url=r.get("thumbnail_url", f"https://i.ytimg.com/vi/{r['id']}/hqdefault.jpg"),
            status=r["status"],
            created_at=r["created_at"],
        )
        for r in rows
    ]
    return VideoListResponse(videos=videos, total=len(videos))


@router.get("/{video_id}", response_model=VideoListItem)
async def get_video(video_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific video by ID."""
    db = get_db_service()
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    return VideoListItem(
        video_id=video["id"],
        url=video["url"],
        title=video["title"],
        channel=video.get("channel", ""),
        duration=video["duration"],
        thumbnail_url=video.get("thumbnail_url", f"https://i.ytimg.com/vi/{video['id']}/hqdefault.jpg"),
        status=video["status"],
        created_at=video["created_at"],
    )


@router.delete("/{video_id}")
async def delete_video(video_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a video and its Qdrant embeddings."""
    from services.qdrant_service import get_qdrant_service
    db = get_db_service()
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    # Remove Qdrant chunks
    qdrant = get_qdrant_service()
    qdrant.delete_video_points(video_id)

    # Remove from Supabase (summaries + videos)
    db.delete_video(video_id)

    return {"deleted": video_id}
