"""Transcript fetching and processing service."""
import asyncio
import html
import logging
import re
from typing import Dict, List, Optional, Any

import yt_dlp
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def extract_video_id(url: str) -> Optional[str]:
    """Extract 11-char YouTube video ID from any YouTube URL format."""
    patterns = [
        r"(?:v=)([A-Za-z0-9_-]{11})",
        r"(?:youtu\.be/)([A-Za-z0-9_-]{11})",
        r"(?:embed/)([A-Za-z0-9_-]{11})",
        r"(?:shorts/)([A-Za-z0-9_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


async def fetch_transcript(url: str) -> Dict[str, Any]:
    """
    Fetch transcript for a YouTube video URL.

    Returns:
        {
            "video_id": str,
            "metadata": {title, channel, channel_id, duration, thumbnail_url, url},
            "segments": [{"start": float, "duration": float, "text": str}, ...],
        }

    Raises:
        ValueError: invalid URL, private video, no captions, fetch failure.
    """
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {url}")

    # Run yt-dlp first; fall back to youtube-transcript-api for any failure
    try:
        metadata, segments = await asyncio.to_thread(_fetch_via_ytdlp, video_id, url)
    except Exception as e:
        logger.warning(f"yt-dlp failed ({e}), falling back to transcript API")
        try:
            segments = await asyncio.to_thread(_fetch_via_transcript_api, video_id)
            metadata = {'title': video_id, 'channel': '', 'channel_id': '', 'duration': 0,
                        'thumbnail_url': f'https://i.ytimg.com/vi/{video_id}/hqdefault.jpg',
                        'url': url, 'video_id': video_id}
        except Exception as e2:
            raise HTTPException(status_code=400, detail=f"Could not fetch transcript: {str(e2)}")

    if not segments:
        raise ValueError("No caption segments found in track")

    logger.info(f"Fetched {len(segments)} segments for {video_id}")
    return {"video_id": video_id, "metadata": metadata, "segments": segments}


# ── yt-dlp implementation (sync, runs in thread) ──────────────────────────────

def _fetch_via_ytdlp(video_id: str, original_url: str) -> tuple:
    """Extract subtitle URLs via yt-dlp (no download) and return (metadata, segments)."""
    import urllib.request

    watch_url = f"https://www.youtube.com/watch?v={video_id}"

    ydl_opts = {
        'skip_download': True,
        'writeautomaticsub': True,
        'writesubtitles': True,
        'subtitleslangs': ['en'],
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'web'],
            }
        },
        'http_headers': {
            'User-Agent': 'com.google.ios.youtube/17.33.2 CFNetwork/1331.0.7 Darwin/21.4.0',
            'X-YouTube-Client-Name': '5',
            'X-YouTube-Client-Version': '17.33.2',
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(watch_url, download=False)
    except yt_dlp.utils.DownloadError as e:
        msg = str(e).lower()
        if "private" in msg:
            raise ValueError("This video is private")
        if "not available" in msg or "not found" in msg:
            raise ValueError(f"Video not found: {video_id}")
        raise ValueError(f"Failed to fetch video: {e}")
    except Exception as e:
        raise ValueError(f"Failed to fetch video: {e}")

    # Find a subtitle URL — prefer requested_subtitles, fall back to automatic_captions
    subtitle_url = None

    requested = info.get('requested_subtitles') or {}
    for lang_data in requested.values():
        if lang_data and lang_data.get('url'):
            subtitle_url = lang_data['url']
            break

    if not subtitle_url:
        auto_caps = info.get('automatic_captions', {})
        for lang_key in ['en', 'en-US', 'en-GB']:
            for fmt in auto_caps.get(lang_key, []):
                if fmt.get('ext') == 'vtt' and fmt.get('url'):
                    subtitle_url = fmt['url']
                    break
            if subtitle_url:
                break

    if not subtitle_url:
        raise ValueError("No captions available for this video")

    # Fetch VTT content from URL
    logger.info(f"Fetching captions from URL for {video_id}")
    try:
        req = urllib.request.Request(subtitle_url, headers={
            'User-Agent': 'com.google.ios.youtube/17.33.2 CFNetwork/1331.0.7 Darwin/21.4.0',
        })
        with urllib.request.urlopen(req, timeout=15) as response:
            vtt_content = response.read().decode('utf-8')
    except Exception as e:
        raise ValueError(f"Failed to download captions: {e}")

    metadata = {
        "video_id": video_id,
        "url": original_url,
        "title": info.get("title", "Unknown Title"),
        "channel": info.get("uploader") or info.get("channel", "Unknown Channel"),
        "channel_id": info.get("channel_id", ""),
        "duration": int(info.get("duration") or 0),
        "thumbnail_url": (
            info.get("thumbnail")
            or f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
        ),
    }

    segments = _parse_vtt(vtt_content)
    return metadata, segments


# ── youtube-transcript-api fallback (sync, runs in thread) ───────────────────

def _fetch_via_transcript_api(video_id: str) -> List[Dict]:
    from youtube_transcript_api import YouTubeTranscriptApi
    transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'en-US', 'en-GB'])
    return [{'start': t['start'], 'duration': t['duration'], 'text': t['text']} for t in transcript]


# ── VTT parser ────────────────────────────────────────────────────────────────

_TIMESTAMP_RE = re.compile(
    r"(\d+):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d+):(\d{2}):(\d{2})\.(\d{3})"
)
_TAG_RE = re.compile(r"<[^>]+>")


def _vtt_ts_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _parse_vtt(vtt_text: str) -> List[Dict]:
    """Parse WebVTT into segment dicts."""
    segments = []
    lines = vtt_text.splitlines()
    i = 0
    while i < len(lines):
        m = _TIMESTAMP_RE.match(lines[i])
        if m:
            start = _vtt_ts_to_seconds(m.group(1), m.group(2), m.group(3), m.group(4))
            end = _vtt_ts_to_seconds(m.group(5), m.group(6), m.group(7), m.group(8))
            duration = end - start
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i])
                i += 1
            raw = " ".join(text_lines)
            # Strip VTT inline tags (<c>, <b>, timestamps, etc.) and HTML entities
            text = html.unescape(_TAG_RE.sub("", raw)).replace("\n", " ").strip()
            if text:
                segments.append({"start": start, "duration": duration, "text": text})
        else:
            i += 1
    return segments
