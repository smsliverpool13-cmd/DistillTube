"""SQLite database service for video metadata."""
import sqlite3
import json
from pathlib import Path
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class SQLiteService:
    """Manages SQLite connection and video table."""

    def __init__(self, db_path: str = "./data/videos.db"):
        self.db_path = db_path
        self._ensure_db_exists()

    def _ensure_db_exists(self):
        """Create database and tables if they don't exist; migrate if needed."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS videos (
                    id            TEXT PRIMARY KEY,
                    url           TEXT NOT NULL UNIQUE,
                    title         TEXT NOT NULL,
                    channel       TEXT NOT NULL DEFAULT '',
                    duration      INTEGER NOT NULL,
                    thumbnail_url TEXT NOT NULL DEFAULT '',
                    transcript    TEXT,
                    status        TEXT NOT NULL DEFAULT 'pending',
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

            # Migrate older schemas that lack the new columns
            for col, definition in [
                ("channel", "TEXT NOT NULL DEFAULT ''"),
                ("thumbnail_url", "TEXT NOT NULL DEFAULT ''"),
                ("status", "TEXT NOT NULL DEFAULT 'pending'"),
            ]:
                try:
                    cursor.execute(f"ALTER TABLE videos ADD COLUMN {col} {definition}")
                    conn.commit()
                except sqlite3.OperationalError:
                    pass  # Column already exists

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS summaries (
                    video_id      TEXT PRIMARY KEY REFERENCES videos(id),
                    summary       TEXT NOT NULL,
                    key_moments   TEXT NOT NULL DEFAULT '[]',
                    topics        TEXT NOT NULL DEFAULT '[]',
                    linkedin_post TEXT NOT NULL DEFAULT '',
                    tweet_thread  TEXT NOT NULL DEFAULT '[]',
                    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

            logger.info(f"SQLite database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize SQLite: {e}")
            raise
        finally:
            conn.close()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save_video(
        self,
        video_id: str,
        url: str,
        title: str,
        duration: int,
        channel: str = "",
        thumbnail_url: str = "",
        transcript: Optional[List] = None,
        status: str = "pending",
    ):
        """Insert or replace a video record."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            transcript_json = json.dumps(transcript) if transcript is not None else None
            cursor.execute(
                """
                INSERT OR REPLACE INTO videos
                    (id, url, title, channel, duration, thumbnail_url, transcript, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (video_id, url, title, channel, duration, thumbnail_url, transcript_json, status),
            )
            conn.commit()
            logger.info(f"Saved video {video_id}: {title} (status={status})")
        except Exception as e:
            logger.error(f"Failed to save video: {e}")
            raise
        finally:
            conn.close()

    def update_status(self, video_id: str, status: str):
        """Update the processing status of a video."""
        conn = self.get_connection()
        try:
            conn.execute(
                "UPDATE videos SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, video_id),
            )
            conn.commit()
        finally:
            conn.close()

    def get_video(self, video_id: str) -> Optional[dict]:
        """Get a video by ID, returning a plain dict or None."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def save_summary(
        self,
        video_id: str,
        summary: str,
        key_moments: list,
        topics: list,
        linkedin_post: str,
        tweet_thread: list,
    ):
        """Insert or replace a summary record."""
        conn = self.get_connection()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO summaries
                    (video_id, summary, key_moments, topics, linkedin_post, tweet_thread)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    video_id,
                    summary,
                    json.dumps(key_moments),
                    json.dumps(topics),
                    linkedin_post,
                    json.dumps(tweet_thread),
                ),
            )
            conn.commit()
            logger.info(f"Saved summary for {video_id}")
        except Exception as e:
            logger.error(f"Failed to save summary: {e}")
            raise
        finally:
            conn.close()

    def get_summary(self, video_id: str) -> Optional[dict]:
        """Get a cached summary by video_id, or None."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM summaries WHERE video_id = ?", (video_id,))
            row = cursor.fetchone()
            if not row:
                return None
            d = dict(row)
            d["key_moments"] = json.loads(d["key_moments"])
            d["topics"] = json.loads(d["topics"])
            d["tweet_thread"] = json.loads(d["tweet_thread"])
            return d
        finally:
            conn.close()

    def list_videos(self, limit: int = 10, offset: int = 0) -> List[dict]:
        """List all videos ordered by most recent, with pagination."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM videos ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()


# ── Singleton ─────────────────────────────────────────────────────────────────

_sqlite_service: Optional[SQLiteService] = None


def get_sqlite_service(db_path: str = "./data/videos.db") -> SQLiteService:
    global _sqlite_service
    if _sqlite_service is None:
        _sqlite_service = SQLiteService(db_path)
    return _sqlite_service
