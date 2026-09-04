from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Keep databases previously used by the organization branch compatible
        # without deleting their tenant metadata.
        await conn.execute(text(
            "DO $$ BEGIN IF EXISTS ("
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'jobs' AND column_name = 'organization_id'"
            ") THEN ALTER TABLE jobs ALTER COLUMN organization_id DROP NOT NULL; "
            "END IF; END $$"
        ))
        await conn.execute(text(
            "DO $$ BEGIN IF EXISTS ("
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'resumes' AND column_name = 'organization_id'"
            ") THEN ALTER TABLE resumes ALTER COLUMN organization_id DROP NOT NULL; "
            "END IF; END $$"
        ))
        await conn.execute(text(
            "DELETE FROM matches older USING matches newer "
            "WHERE older.resume_id = newer.resume_id AND older.job_id = newer.job_id "
            "AND (older.created_at, older.id) < (newer.created_at, newer.id)"
        ))
        await conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_match_resume_job ON matches (resume_id, job_id)"
        ))
