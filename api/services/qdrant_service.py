"""Qdrant vector database service for embeddings."""
import uuid
import logging
from typing import Optional, List

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    FilterSelector,
)

logger = logging.getLogger(__name__)


class QdrantService:
    """Manages Qdrant connection and embeddings collection."""

    def __init__(self, qdrant_url: str = "http://localhost:6333", collection_name: str = "transcripts", api_key: str = ""):
        self.qdrant_url = qdrant_url
        self.collection_name = collection_name
        self.api_key = api_key
        self.client = None
        self._connect()

    def _connect(self):
        """Connect to Qdrant and create collection if it doesn't exist."""
        try:
            self.client = QdrantClient(
                url=self.qdrant_url,
                api_key=self.api_key if self.api_key else None,
            )
            collections = self.client.get_collections()
            existing = {col.name for col in collections.collections}
            if self.collection_name not in existing:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=768, distance=Distance.COSINE),
                )
                logger.info(f"Created Qdrant collection: {self.collection_name}")
            else:
                logger.info(f"Qdrant collection already exists: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            self.client = None

    def _video_filter(self, video_id: str) -> Filter:
        return Filter(must=[FieldCondition(key="video_id", match=MatchValue(value=video_id))])

    def upsert_chunks(self, video_id: str, embedded_chunks: list):
        if self.client is None or not embedded_chunks:
            return

        points = []
        for i, item in enumerate(embedded_chunks):
            chunk = item["chunk"]
            vector = item["vector"]
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{video_id}:{i}"))
            points.append(PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "video_id": video_id,
                    "text": chunk["text"],
                    "start_time": chunk["start_time"],
                    "end_time": chunk["end_time"],
                },
            ))

        self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info(f"Upserted {len(points)} chunks for video {video_id}")

    def search(self, video_id: str, query_vector: List[float], limit: int = 5) -> list:
        if self.client is None:
            return []

        try:
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=self._video_filter(video_id),
                limit=limit,
            )
            return response.points
        except Exception as e:
            logger.error(f"Failed to search Qdrant: {e}")
            return []

    def delete_video_points(self, video_id: str):
        if self.client is None:
            return
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=FilterSelector(filter=self._video_filter(video_id)),
            )
            logger.info(f"Deleted all points for video {video_id}")
        except Exception as e:
            logger.error(f"Failed to delete points from Qdrant: {e}")


# ── Singleton ──────────────────────────────────────────────────────────────────

_qdrant_service: Optional[QdrantService] = None


def get_qdrant_service(*args, **kwargs) -> QdrantService:
    from config import settings
    global _qdrant_service
    if _qdrant_service is None:
        _qdrant_service = QdrantService(
            qdrant_url=settings.qdrant_url,
            collection_name=settings.qdrant_collection,
            api_key=settings.qdrant_api_key,
        )
    return _qdrant_service
