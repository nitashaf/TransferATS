"""
Shared Claude API client for TransferATS.
Used by: llm_judge.py, groq_service.py
"""
import httpx
from app.config import get_settings

settings = get_settings()
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_MODEL = "claude-haiku-4-5-20251001"


def call_claude(prompt: str, max_tokens: int = 1000) -> str:
    """
    Call Claude API and return text response.
    Handles any input length up to 200k tokens.
    """
    response = httpx.post(
        _ANTHROPIC_URL,
        headers={
            "x-api-key": settings.ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": _MODEL,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]
        },
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]