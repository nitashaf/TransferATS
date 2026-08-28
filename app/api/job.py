import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.job import Job
from app.models.organization import Organization
from app.schemas.job import JobCreate
from app.services.gemini import get_embeddings
from app.services.groq_service import extract_job_details, extract_skills
from app.services.scraper import scrape_job_url

router = APIRouter()


@router.post("/create", summary="Create a job — supports manual JSON, raw text, or a URL")
async def create_job(job_data: JobCreate, db: AsyncSession = Depends(get_db)):
    if job_data.organization_id:
        try:
            organization = await db.scalar(
                select(Organization).where(Organization.id == uuid.UUID(job_data.organization_id))
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid organization ID format.")
    else:
        organization = await db.scalar(select(Organization).where(Organization.slug == "neuroforge"))
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found.")

    title = job_data.title
    description = job_data.description
    required_skills: list[str] = list(job_data.required_skills or [])
    nice_to_have: list[str] = list(job_data.nice_to_have_skills or [])
    source = "manual"

    # ── Mode 3: URL ──────────────────────────────────────────────────────────
    if job_data.url:
        try:
            scraped_text = await scrape_job_url(job_data.url)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc))

        extracted = await extract_job_details(scraped_text)
        title = title or extracted.get("title") or job_data.url
        description = description or extracted.get("description") or scraped_text[:1000]
        required_skills = _merge(required_skills, extracted.get("required_skills", []))
        nice_to_have = _merge(nice_to_have, extracted.get("nice_to_have_skills", []))
        source = "url"

    # ── Mode 2: raw text ─────────────────────────────────────────────────────
    elif job_data.raw_text:
        extracted = await extract_job_details(job_data.raw_text) or {}
        title = title or extracted.get("title") or "Untitled Position"
        description = description or extracted.get("description") or job_data.raw_text[:1000]
        required_skills = _merge(required_skills, extracted.get("required_skills", []))
        nice_to_have = _merge(nice_to_have, extracted.get("nice_to_have_skills", []))
        source = "raw_text"

    # ── Mode 1: manual JSON ───────────────────────────────────────────────────
    else:
        pass

    embeddings = await get_embeddings(description)

    job = Job(
        organization_id=organization.id,
        title=title,
        description=description,
        required_skills=required_skills,
        nice_to_have_skills=nice_to_have,
        embeddings=embeddings,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    return {
        "id": str(job.id),
        "title": job.title,
        "organization_id": str(job.organization_id),
        "source": source,
        "required_skills": job.required_skills,
        "nice_to_have_skills": job.nice_to_have_skills,
        "skill_count": len(job.required_skills),
        "created_at": job.created_at,
    }

@router.get("/list", summary="List all jobs")
async def list_jobs(
    limit: int = Query(default=50, ge=1, le=200),
    organization_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    statement = select(Job).order_by(Job.created_at.desc()).limit(limit)
    if organization_id:
        try:
            statement = statement.where(Job.organization_id == uuid.UUID(organization_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid organization ID format.")
    result = await db.execute(statement)
    jobs = result.scalars().all()
    return [
        {
            "id": str(j.id),
            "title": j.title,
            "organization_id": str(j.organization_id),
            "source": "manual",
            "skill_count": len(j.required_skills or []),
            "created_at": j.created_at,
        }
        for j in jobs
    ]

@router.get("/{job_id}", summary="Get a job by ID")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    try:
        jid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format.")

    result = await db.execute(select(Job).where(Job.id == jid))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    return {
        "id": str(job.id),
        "title": job.title,
        "organization_id": str(job.organization_id),
        "required_skills": job.required_skills,
        "nice_to_have_skills": job.nice_to_have_skills,
        "created_at": job.created_at,
    }


def _merge(*skill_lists: list[str]) -> list[str]:
    """Deduplicate and lowercase-normalise skills from multiple sources."""
    return list({s.lower().strip() for lst in skill_lists for s in lst if s.strip()})
