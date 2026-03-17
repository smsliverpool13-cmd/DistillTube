"""Transcript fetching endpoint."""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from config import settings
from middleware.auth import get_current_user
from services.embedding import EmbeddingService
from services.qdrant_service import get_qdrant_service
from services.db_service import get_db_service
from services.transcript import extract_video_id, fetch_transcript

router = APIRouter(prefix="/transcript", tags=["transcript"])
logger = logging.getLogger(__name__)


# ── Request / Response schemas ────────────────────────────────────────────────

class TranscriptRequest(BaseModel):
    url: str

    @field_validator("url")
    @classmethod
    def must_be_youtube(cls, v: str) -> str:
        v = v.strip()
        if not any(d in v for d in ("youtube.com", "youtu.be")):
            raise ValueError("URL must be a YouTube URL")
        return v


class TranscriptSegment(BaseModel):
    start: float      # seconds
    duration: float   # seconds
    text: str


class TranscriptResponse(BaseModel):
    video_id: str
    title: str
    channel: str
    duration: int     # seconds
    thumbnail_url: str
    cached: bool
    segments: List[TranscriptSegment]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{video_id}")
async def get_cached_transcript(video_id: str,
                                current_user: dict = Depends(get_current_user)):
    """Return a previously saved transcript by video ID."""
    import json
    db = get_db_service()
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    segments = video.get("transcript") or []
    if isinstance(segments, str):
        segments = json.loads(segments)
    return {
        "video_id": video_id,
        "title": video["title"],
        "channel": video.get("channel", ""),
        "segments": segments,
        "status": video["status"],
    }


@router.post("", response_model=TranscriptResponse)
async def get_transcript(request: TranscriptRequest,
                         current_user: dict = Depends(get_current_user)):
    """
    Fetch transcript for a YouTube video.

    - Returns cached data immediately if already processed (status=ready).
    - Otherwise fetches fresh transcript, saves to Supabase with status='pending',
      and returns the segments.
    """
    url = request.url

    video_id = extract_video_id(url)
    if not video_id:
        raise HTTPException(status_code=400, detail="Invalid YouTube URL — could not extract video ID")

    db = get_db_service()

    # ── Cache hit ──
    cached = db.get_video(video_id)
    if cached and cached.get("status") == "ready" and cached.get("transcript"):
        segments = cached["transcript"]
        if isinstance(segments, str):
            import json
            segments = json.loads(segments)
        return TranscriptResponse(
            video_id=video_id,
            title=cached["title"],
            channel=cached.get("channel", ""),
            duration=cached["duration"],
            thumbnail_url=cached.get("thumbnail_url", f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"),
            cached=True,
            segments=[TranscriptSegment(**s) for s in segments],
        )

    # ── Fresh fetch ──
    try:
        result = await fetch_transcript(url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Could not fetch transcript. Video may not have captions or may be unavailable.")
    except Exception as e:
        logger.error(f"Unexpected error fetching transcript for {video_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch transcript")

    metadata = result["metadata"]
    segments = result["segments"]

    # Persist with status='pending' before embedding
    try:
        db.save_video(
            video_id=video_id,
            url=url,
            title=metadata["title"],
            channel=metadata.get("channel", ""),
            duration=metadata["duration"],
            thumbnail_url=metadata.get("thumbnail_url", ""),
            transcript=segments,
            user_id=current_user["id"],
            status="pending",
        )
    except Exception as e:
        logger.warning(f"Failed to cache transcript for {video_id}: {e}")

    # ── Chunk + embed + upsert to Qdrant ──
    try:
        embedder = EmbeddingService(api_key=settings.nomic_api_key)
        chunks = embedder.chunk_transcript(segments)
        embedded = await embedder.embed_chunks(chunks)

        qdrant = get_qdrant_service()
        qdrant.upsert_chunks(video_id, embedded)
        db.update_status(video_id, "ready")
        logger.info(f"Embedding complete for {video_id}")
    except Exception as e:
        logger.error(f"Embedding/upsert failed for {video_id}: {e}", exc_info=True)
        # Leave status as 'pending'; transcript is still returned

    return TranscriptResponse(
        video_id=video_id,
        title=metadata["title"],
        channel=metadata.get("channel", ""),
        duration=metadata["duration"],
        thumbnail_url=metadata.get("thumbnail_url", f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"),
        cached=False,
        segments=[TranscriptSegment(**s) for s in segments],
    )
