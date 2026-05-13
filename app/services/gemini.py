import asyncio
from typing import List

from openai import AsyncOpenAI

from app.config import get_settings

settings = get_settings()
_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)


async def get_embeddings(text: str) -> List[float]:
    response = await _client.embeddings.create(
        model="text-embedding-3-small",
        input=text[:8191],
    )
    return response.data[0].embedding
