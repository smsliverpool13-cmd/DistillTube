"""Embedding generation service using Nomic AI API."""
import logging
import os
import httpx

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates embeddings using Nomic AI's nomic-embed-text-v1.5 model."""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.getenv("NOMIC_API_KEY", "")
        logger.info("Embedding service initialized with Nomic AI")

    def chunk_transcript(self, segments: list, chunk_size: int = 45, overlap: int = 2) -> list:
        """Group segments into 45-second windows with 2-segment overlap.

        Args:
            segments: List of dicts with keys: start (float), duration (float), text (str)
            chunk_size: Target window size in seconds
            overlap: Number of segments to repeat at the start of the next chunk

        Returns:
            List of dicts: {start_time, end_time, text}
        """
        chunks = []
        i = 0
        while i < len(segments):
            chunk_segs = []
            total_dur = 0.0
            j = i
            while j < len(segments) and total_dur < chunk_size:
                seg = segments[j]
                chunk_segs.append(seg)
                total_dur += seg.get("duration", 0)
                j += 1

            if not chunk_segs:
                break

            last = chunk_segs[-1]
            chunks.append({
                "start_time": chunk_segs[0]["start"],
                "end_time": last["start"] + last.get("duration", 0),
                "text": " ".join(s["text"] for s in chunk_segs),
            })

            # Advance pointer, keeping last `overlap` segments for next chunk
            i = max(i + 1, j - overlap)

        logger.info(f"Chunked {len(segments)} segments into {len(chunks)} chunks")
        return chunks

    async def embed_text(self, text: str) -> list[float]:
        """Call Nomic AI API and return a 768-dim vector."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api-atlas.nomic.ai/v1/embedding/text",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": "nomic-embed-text-v1.5", "texts": [text]},
            )
            resp.raise_for_status()
            return resp.json()["embeddings"][0]

    async def embed_query(self, question: str) -> list[float]:
        """Embed a user query for similarity search."""
        return await self.embed_text(question)

    async def embed_chunks(self, chunks: list) -> list[dict]:
        """Embed every chunk and return [{chunk, vector}, ...]."""
        result = []
        for chunk in chunks:
            vector = await self.embed_text(chunk["text"])
            result.append({"chunk": chunk, "vector": vector})
        logger.info(f"Embedded {len(result)} chunks")
        return result
