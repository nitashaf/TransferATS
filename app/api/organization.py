import re
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.job import Job
from app.models.match import Match
from app.models.organization import Organization
from app.models.resume import Resume
from app.schemas.organization import OrganizationCreate

router = APIRouter()


def _slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


@router.get("", summary="List organizations")
async def list_organizations(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Organization).order_by(Organization.name))).scalars().all()
    return [{"id": str(row.id), "name": row.name, "slug": row.slug} for row in rows]


@router.post("", status_code=201, summary="Create an organization")
async def create_organization(data: OrganizationCreate, db: AsyncSession = Depends(get_db)):
    slug = _slugify(data.slug or data.name)
    if not slug:
        raise HTTPException(status_code=422, detail="Organization slug cannot be empty.")
    exists = await db.scalar(
        select(Organization).where((Organization.slug == slug) | (Organization.name == data.name.strip()))
    )
    if exists:
        raise HTTPException(status_code=409, detail="Organization name or slug already exists.")
    organization = Organization(name=data.name.strip(), slug=slug)
    db.add(organization)
    await db.commit()
    await db.refresh(organization)
    return {"id": str(organization.id), "name": organization.name, "slug": organization.slug}


@router.get("/{organization_id}/dashboard", summary="Get jobs and ranked candidates for an organization")
async def organization_dashboard(organization_id: str, db: AsyncSession = Depends(get_db)):
    try:
        oid = uuid.UUID(organization_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid organization ID format.")

    organization = await db.scalar(select(Organization).where(Organization.id == oid))
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found.")

    jobs = (await db.execute(
        select(Job).where(Job.organization_id == oid).order_by(Job.created_at.desc())
    )).scalars().all()
    job_ids = [job.id for job in jobs]
    rows = []
    if job_ids:
        rows = (await db.execute(
            select(Match, Resume)
            .join(Resume, Resume.id == Match.resume_id)
            .where(Match.job_id.in_(job_ids))
            .order_by(Match.job_id, Match.overall_score.desc(), Match.created_at.asc())
        )).all()

    by_job = {job.id: [] for job in jobs}
    for match, resume in rows:
        candidates = by_job[match.job_id]
        candidates.append({
            "rank": len(candidates) + 1,
            "match_id": str(match.id),
            "resume_id": str(resume.id),
            "candidate_name": resume.candidate_name,
            "email": resume.email,
            "filename": resume.filename,
            "overall_score": match.overall_score,
            "ats_score": match.ats_score,
            "semantic_score": match.semantic_score,
            "transferable_score": match.transferable_score,
        })

    return {
        "organization": {"id": str(organization.id), "name": organization.name, "slug": organization.slug},
        "jobs": [{
            "id": str(job.id),
            "title": job.title,
            "created_at": job.created_at,
            "candidate_count": len(by_job[job.id]),
            "candidates": by_job[job.id],
        } for job in jobs],
    }
