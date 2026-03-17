"""LLM generation service using Groq API."""
import json
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_PROMPT = """\
Analyze this YouTube video transcript and return a JSON object with exactly these 5 keys.

Title: {title}
Duration: {duration} seconds
Transcript ([M:SS] format):
{transcript}

Return JSON with these keys:
- "summary": string, 2 sentences
- "key_moments": array of 6 objects with "timestamp" (number, in SECONDS as integer, spread across the full duration) and "text" (string).
  For a {duration} second video, spread timestamps like: 0, {t1}, {t2}, {t3}, {t4}, {duration}.
  DO NOT use timestamps like 0,1,2,3,4,5 — spread them across the full video duration.
- "topics": array of 6 specific strings — named people, technologies, or concepts
- "linkedin_post": string, 3 sentences + 3 hashtags. Hook, insight, call to action.
- "tweet_thread": array of 5 strings under 280 chars each

JSON only:"""


def _parse_json_response(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        if start != -1:
            return json.loads(text[start:])
        raise


def _seconds_to_mss(seconds: float) -> str:
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}:{s:02d}"


class LLMService:
    def __init__(self):
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.model = "llama-3.1-8b-instant"
        self.base_url = "https://api.groq.com/openai/v1"
        logger.info(f"LLM service initialized with Groq/{self.model}")

    async def _chat(self, messages: list, json_mode: bool = False) -> str:
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": 2048,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

    async def _generate_all(self, transcript_text: str, title: str, duration_seconds: float = 0) -> dict:
        dur = max(duration_seconds, 60)
        d = round(dur)
        prompt = _PROMPT.format(
            title=title, transcript=transcript_text, duration=d,
            t1=d//5, t2=2*d//5, t3=3*d//5, t4=4*d//5,
        )
        logger.info(f"Generating content for: {title}")
        raw = await self._chat([{"role": "user", "content": prompt}], json_mode=True)
        try:
            result = _parse_json_response(raw)
            return {
                "summary": str(result.get("summary", "")),
                "key_moments": [
                    {"timestamp": float(m["timestamp"]), "text": str(m["text"])}
                    for m in result.get("key_moments", [])
                ],
                "topics": [str(t) for t in result.get("topics", [])],
                "linkedin_post": str(result.get("linkedin_post", "")),
                "tweet_thread": [str(t)[:280] for t in result.get("tweet_thread", [])],
            }
        except Exception as e:
            logger.warning(f"Failed to parse JSON: {e}\nRaw: {raw[:500]}")
            return {"summary": raw.strip(), "key_moments": [], "topics": [], "linkedin_post": "", "tweet_thread": []}

    async def generate_summary(self, transcript_text: str, title: str, duration_seconds: float = 0) -> dict:
        return await self._generate_all(transcript_text, title, duration_seconds)

    async def generate_chat_response(self, question: str, context: str) -> str:
        logger.info(f"Chat: {question}")
        messages = [
            {"role": "system", "content": "Answer questions about a YouTube video using only the provided context. Be concise and cite timestamps when relevant."},
            {"role": "user", "content": f"CONTEXT:\n{context}\n\nQUESTION: {question}"},
        ]
        return (await self._chat(messages)).strip()


_llm_service: LLMService | None = None


def get_llm_service(*args, **kwargs) -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
