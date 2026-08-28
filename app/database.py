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
        # Additive compatibility migration for databases created before organizations.
        await conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS organization_id UUID"))
        await conn.execute(text(
            "INSERT INTO organizations (id, name, slug) "
            "SELECT gen_random_uuid(), 'NeuroForge', 'neuroforge' "
            "WHERE NOT EXISTS (SELECT 1 FROM organizations WHERE slug = 'neuroforge')"
        ))
        await conn.execute(text(
            "UPDATE jobs SET organization_id = "
            "(SELECT id FROM organizations WHERE slug = 'neuroforge') "
            "WHERE organization_id IS NULL"
        ))
        await conn.execute(text("ALTER TABLE jobs ALTER COLUMN organization_id SET NOT NULL"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_jobs_organization_id ON jobs (organization_id)"))
        await conn.execute(text(
            "DO $$ BEGIN "
            "IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_jobs_organization_id') THEN "
            "ALTER TABLE jobs ADD CONSTRAINT fk_jobs_organization_id "
            "FOREIGN KEY (organization_id) REFERENCES organizations(id); "
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
