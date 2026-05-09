import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.job import Job
from app.models.match import Match
from app.models.resume import Resume
from app.schemas.match import MatchRequest
from app.services.matching import match_resume_to_job

router = APIRouter()


@router.post("", summary="Match a resume against a job description")
async def match(request: MatchRequest, db: AsyncSession = Depends(get_db)):
    try:
        rid, jid = uuid.UUID(request.resume_id), uuid.UUID(request.job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format.")

    resume_row = await db.execute(select(Resume).where(Resume.id == rid))
    resume = resume_row.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found.")

    job_row = await db.execute(select(Job).where(Job.id == jid))
    job = job_row.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    scores = await match_resume_to_job(
        resume_content=resume.content,
        resume_skills=resume.parsed_skills or [],
        resume_embeddings=resume.embeddings or [],
        job_description=job.description,
        job_skills=job.required_skills or [],
        job_embeddings=job.embeddings or [],
    )

    match_record = Match(
        resume_id=resume.id,
        job_id=job.id,
        ats_score=scores["ats_score"],
        semantic_score=scores["semantic_score"],
        transferable_score=scores["transferable_score"],
        overall_score=scores["overall_score"],
        matched_skills=scores["matched_skills"],
        missing_skills=scores["missing_skills"],
        transferable_skills=scores["transferable_skills"],
        details=scores,
    )
    db.add(match_record)
    await db.commit()
    await db.refresh(match_record)

    return {
        "match_id": str(match_record.id),
        "resume_id": request.resume_id,
        "job_id": request.job_id,
        "candidate_name": resume.candidate_name,
        "job_title": job.title,
        **scores,
    }
