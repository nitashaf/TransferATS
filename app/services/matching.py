from typing import Dict, List, Tuple

import numpy as np

from app.services.gemini import analyze_transferable_skills


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    a, b = np.array(vec1), np.array(vec2)
    norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def _ats_score(
    resume_skills: List[str], job_skills: List[str]
) -> Tuple[float, List[str], List[str]]:
    resume_set = {s.lower().strip() for s in resume_skills}
    job_normalized = [s.lower().strip() for s in job_skills]

    matched = [s for s in job_normalized if s in resume_set]
    missing = [s for s in job_normalized if s not in resume_set]

    score = len(matched) / len(job_normalized) if job_normalized else 0.0
    return score, matched, missing


def _transferable_score(transferable_skills: List[Dict]) -> float:
    if not transferable_skills:
        return 0.0
    weight_map = {"high": 1.0, "medium": 0.6, "low": 0.3}
    scores = [weight_map.get(s.get("confidence", "low"), 0.3) for s in transferable_skills]
    return sum(scores) / len(scores)


async def match_resume_to_job(
    resume_content: str,
    resume_skills: List[str],
    resume_embeddings: List[float],
    job_description: str,
    job_skills: List[str],
    job_embeddings: List[float],
) -> Dict:
    # Layer 1: ATS exact keyword matching (40% weight)
    ats, matched_skills, missing_skills = _ats_score(resume_skills, job_skills)

    # Layer 2: Semantic similarity via embeddings (40% weight)
    semantic = (
        _cosine_similarity(resume_embeddings, job_embeddings)
        if resume_embeddings and job_embeddings
        else 0.0
    )
    # Clamp to [0, 1] — cosine can be slightly negative for unrelated texts
    semantic = max(0.0, min(1.0, semantic))

    # Layer 3: Transferable skills via Gemini (20% weight)
    transferable_data = {"transferable_skills": []}
    if missing_skills:
        transferable_data = await analyze_transferable_skills(
            resume_content, job_description, missing_skills
        )
    transferable_skills = transferable_data.get("transferable_skills", [])
    transferable = _transferable_score(transferable_skills)

    overall = (ats * 0.40) + (semantic * 0.40) + (transferable * 0.20)

    return {
        "ats_score": round(ats * 100, 2),
        "semantic_score": round(semantic * 100, 2),
        "transferable_score": round(transferable * 100, 2),
        "overall_score": round(overall * 100, 2),
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "transferable_skills": transferable_skills,
    }
