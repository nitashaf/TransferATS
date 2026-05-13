from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    ONET_USERNAME: str = ""
    ONET_PASSWORD: str = ""
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/transferats"

    model_config = {"env_file": ".env"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
