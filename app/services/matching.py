from typing import Dict, List, Tuple

import numpy as np

from app.services import groq_service, onet
from app.services.llm_judge import evaluate_candidate, calculate_llm_score


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

    # Layer 1: ATS — fast keyword match (20% weight)
    ats, matched_skills, missing_skills = _ats_score(resume_skills, job_skills)

    # Layer 2: LLM Judge — contextual understanding (50% weight)
    llm_evaluation = await evaluate_candidate(
        resume_content=resume_content,
        job_description=job_description,
        job_skills=job_skills,
    )
    evaluations = llm_evaluation.get("evaluations", [])
    llm_score = calculate_llm_score(evaluations) / 100  # normalize to 0-1

    # Layer 3: Semantic similarity (15% weight)
    semantic = (
        _cosine_similarity(resume_embeddings, job_embeddings)
        if resume_embeddings and job_embeddings
        else 0.0
    )
    semantic = max(0.0, min(1.0, semantic))

    # Layer 4: Transferable — only for truly missing skills (15% weight)
    # Use LLM judge NOT_MET skills for transferable analysis
    # These are genuinely missing, not just keyword mismatches
    truly_missing = [
        e["skill"] for e in evaluations
        if e.get("status") == "NOT_MET"
    ]

    transferable_data: Dict = {"transferable_skills": []}
    if truly_missing:
        transferable_data = await onet.find_transferable_skills_async(
            resume_skills, truly_missing
        )
        if not transferable_data.get("transferable_skills"):
            transferable_data = await groq_service.analyze_transferable_skills(
                resume_content, job_description, truly_missing
            )

    transferable_skills = transferable_data.get("transferable_skills", [])
    transferable = _transferable_score(transferable_skills)

    # Combined score with new weights
    overall = (
        ats * 0.20 +
        llm_score * 0.50 +
        semantic * 0.15 +
        transferable * 0.15
    )

    return {
        "ats_score": round(ats * 100, 2),
        "llm_judge_score": round(llm_score * 100, 2),
        "semantic_score": round(semantic * 100, 2),
        "transferable_score": round(transferable * 100, 2),
        "overall_score": round(overall * 100, 2),
        "matched_skills": matched_skills,
        "missing_skills": truly_missing,
        "transferable_skills": transferable_skills,
        "llm_evaluations": evaluations,
        "overall_assessment": llm_evaluation.get("overall_assessment", ""),
        "hiring_recommendation": llm_evaluation.get("hiring_recommendation", "MAYBE"),
    }