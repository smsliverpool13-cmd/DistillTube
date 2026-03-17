"""Summary generation endpoint."""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import settings
from middleware.auth import get_current_user
from services.llm_service import get_llm_service
from services.db_service import get_db_service

router = APIRouter(prefix="/summary", tags=["summary"])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class SummaryRequest(BaseModel):
    video_id: str


class KeyMoment(BaseModel):
    timestamp: float
    text: str


class SummaryResponse(BaseModel):
    video_id: str
    summary: str
    key_moments: List[KeyMoment]
    topics: List[str]
    linkedin_post: str
    tweet_thread: List[str]
    cached: bool


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("", response_model=SummaryResponse)
async def generate_summary(request: SummaryRequest,
                           current_user: dict = Depends(get_current_user)):
    """
    Generate summary, key moments, topics, and social posts for a video.

    - Requires the video to already be processed (status='ready').
    - Returns cached results if they already exist.
    """
    video_id = request.video_id
    db = get_db_service()

    # Verify video exists and is ready
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    if video.get("status") != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Video is not ready yet (status={video.get('status')}). Process the transcript first.",
        )
    if not video.get("transcript"):
        raise HTTPException(status_code=422, detail="Video has no transcript stored")

    # Return cached summary if available
    cached = db.get_summary(video_id)
    if cached:
        return SummaryResponse(
            video_id=video_id,
            summary=cached["summary"],
            key_moments=[KeyMoment(**m) for m in cached["key_moments"]],
            topics=cached["topics"],
            linkedin_post=cached.get("linkedin_post", ""),
            tweet_thread=cached.get("tweet_thread", []),
            cached=True,
        )

    # Transcript from Supabase is already a list (JSONB), not a JSON string
    segments = video["transcript"]
    if isinstance(segments, str):
        import json
        segments = json.loads(segments)

    segments.sort(key=lambda s: s["start"])
    segments = [s for s in segments if s.get("text", "").strip()]

    if not segments:
        raise HTTPException(status_code=422, detail="Transcript is empty")

    def _mss(secs: float) -> str:
        m, s = int(secs) // 60, int(secs) % 60
        return f"{m}:{s:02d}"

    # Build timestamped transcript, capping at ~120 segments to stay within context
    capped = segments[:120]
    transcript_text = " ".join(f"[{_mss(s['start'])}] {s['text'].strip()}" for s in capped)
    if len(capped) < len(segments):
        transcript_text += " [truncated]"

    duration_seconds = segments[-1]["start"] if segments else 0

    title = video.get("title", "Unknown Video")
    llm = get_llm_service(settings.groq_api_key)

    # Single LLM call for everything
    try:
        data = await llm._generate_all(transcript_text, title, duration_seconds)
    except Exception as e:
        logger.error(f"LLM generation failed for {video_id}: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {e}")

    # Persist to Supabase
    try:
        db.save_summary(
            video_id=video_id,
            summary=data["summary"],
            key_moments=data["key_moments"],
            topics=data["topics"],
            linkedin_post=data["linkedin_post"],
            tweet_thread=data["tweet_thread"],
        )
    except Exception as e:
        logger.warning(f"Failed to cache summary for {video_id}: {e}")

    return SummaryResponse(
        video_id=video_id,
        summary=data["summary"],
        key_moments=[KeyMoment(**m) for m in data["key_moments"]],
        topics=data["topics"],
        linkedin_post=data["linkedin_post"],
        tweet_thread=data["tweet_thread"],
        cached=False,
    )
