"""RAG chat endpoint."""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from config import settings
from middleware.auth import get_current_user
from services.embedding import EmbeddingService
from services.llm_service import get_llm_service
from services.qdrant_service import get_qdrant_service
from services.db_service import get_db_service

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    video_id: str
    question: str
    chat_history: List = []


class Source(BaseModel):
    start_time: float
    end_time: float
    text: str
    score: float


class ChatResponse(BaseModel):
    video_id: str
    question: str
    answer: str
    sources: List[Source]


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    """
    Answer a question about a video using RAG.

    - Embeds the question and retrieves the top 5 most relevant transcript chunks.
    - Passes those chunks as context to the LLM.
    - Returns the answer and source chunks with timestamps for clickable citations.
    """
    video_id = request.video_id
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    db = get_db_service()
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")
    if video.get("status") != "ready":
        raise HTTPException(
            status_code=409,
            detail=f"Video is not ready yet (status={video.get('status')}). Process the transcript first.",
        )

    # Embed the question
    embedder = EmbeddingService(api_key=settings.nomic_api_key)
    try:
        query_vector = await embedder.embed_query(question)
    except Exception as e:
        logger.error(f"Failed to embed question: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"Embedding failed: {e}")

    # Retrieve top 5 relevant chunks
    qdrant = get_qdrant_service()
    results = qdrant.search(video_id, query_vector, limit=5)

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No transcript chunks found for this video. Re-process the transcript to enable chat.",
        )

    # Build context string with timestamps
    def _mss(secs: float) -> str:
        m, s = int(secs) // 60, int(secs) % 60
        return f"{m}:{s:02d}"

    context_lines = [
        f"[{_mss(r.payload['start_time'])}] {r.payload['text']}"
        for r in results
    ]
    context = "\n".join(context_lines)

    # Generate answer
    llm = get_llm_service(settings.groq_api_key)
    try:
        answer = await llm.generate_chat_response(question, context)
    except Exception as e:
        logger.error(f"LLM chat failed for {video_id}: {e}", exc_info=True)
        raise HTTPException(status_code=502, detail=f"LLM generation failed: {e}")

    sources = [
        Source(
            start_time=r.payload["start_time"],
            end_time=r.payload["end_time"],
            text=r.payload["text"],
            score=round(r.score, 4),
        )
        for r in results
    ]

    return ChatResponse(
        video_id=video_id,
        question=question,
        answer=answer,
        sources=sources,
    )
