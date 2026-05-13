import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.resume import Resume
from app.services.gemini import get_embeddings
from app.services.groq_service import extract_skills
from app.services.parser import parse_resume

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}


@router.post("/upload", summary="Upload and parse a resume")
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and TXT files are supported.")

    content = await parse_resume(file)
    if not content.strip():
        raise HTTPException(status_code=422, detail="Could not extract text from the file.")

    extracted, embeddings = await _gather(content)

    resume = Resume(
        filename=file.filename,
        content=content,
        candidate_name=extracted.get("name"),
        email=extracted.get("email"),
        parsed_skills=extracted.get("skills", []),
        embeddings=embeddings,
    )
    db.add(resume)
    await db.commit()
    await db.refresh(resume)

    return {
        "id": str(resume.id),
        "filename": resume.filename,
        "candidate_name": resume.candidate_name,
        "email": resume.email,
        "skills": resume.parsed_skills,
        "skill_count": len(resume.parsed_skills),
        "created_at": resume.created_at,
    }


@router.get("/{resume_id}", summary="Get a resume by ID")
async def get_resume(resume_id: str, db: AsyncSession = Depends(get_db)):
    try:
        rid = uuid.UUID(resume_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid resume ID format.")

    result = await db.execute(select(Resume).where(Resume.id == rid))
    resume = result.scalar_one_or_none()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found.")

    return {
        "id": str(resume.id),
        "filename": resume.filename,
        "candidate_name": resume.candidate_name,
        "email": resume.email,
        "skills": resume.parsed_skills,
        "created_at": resume.created_at,
    }


async def _gather(content: str):
    import asyncio
    return await asyncio.gather(extract_skills(content), get_embeddings(content))
