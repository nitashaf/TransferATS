import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.job import Job
from app.models.match import Match
from app.models.resume import Resume

router = APIRouter()


@router.get("/{job_id}", summary="Get ranked candidates for a job")
async def get_candidates(
    job_id: str,
    limit: int = Query(default=10, ge=1, le=100, description="Max candidates to return"),
    min_score: float = Query(default=0.0, ge=0.0, le=100.0, description="Minimum overall score filter"),
    db: AsyncSession = Depends(get_db),
):
    try:
        jid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format.")

    job_row = await db.execute(select(Job).where(Job.id == jid))
    job = job_row.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    result = await db.execute(
        select(Match, Resume)
        .join(Resume, Match.resume_id == Resume.id)
        .where(Match.job_id == jid)
        .where(Match.overall_score >= min_score)
        .order_by(Match.overall_score.desc())
        .limit(limit)
    )
    rows = result.all()

    candidates = []
    for rank, (match, resume) in enumerate(rows, start=1):
        details = match.details or {}
        candidates.append({
            "rank": rank,
            "match_id": str(match.id),
            "resume_id": str(resume.id),
            "candidate_name": resume.candidate_name,
            "email": resume.email,
            "filename": resume.filename,
            "scores": {
                "overall": match.overall_score,
                "ats": match.ats_score,
                "llm_judge": details.get("llm_judge_score", 0.0),
                "semantic": match.semantic_score,
                "transferable": match.transferable_score,
            },
            "matched_skills": match.matched_skills,
            "missing_skills": match.missing_skills,
            "transferable_skills": match.transferable_skills,
            "hiring_recommendation": details.get("hiring_recommendation"),
            "overall_assessment": details.get("overall_assessment"),
            "llm_evaluations": details.get("llm_evaluations", []),
            "created_at": match.created_at.isoformat() if match.created_at else None,
        })

    return {
        "job_id": job_id,
        "job_title": job.title,
        "total_candidates": len(candidates),
        "candidates": candidates,
    }
