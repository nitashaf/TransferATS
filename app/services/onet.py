import asyncio
from typing import Dict, List

import httpx

from app.config import get_settings

ONET_BASE_URL = "https://services.onetcenter.org/ws/"


def _auth() -> tuple[str, str]:
    s = get_settings()
    return (s.ONET_USERNAME, s.ONET_PASSWORD or "")


def search_occupation(skill: str) -> List[Dict]:
    """Search O*NET for occupations matching a skill keyword."""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{ONET_BASE_URL}online/search",
                params={"keyword": skill, "start": 1, "end": 10},
                auth=_auth(),
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                return []
            return resp.json().get("occupation", [])
    except Exception:
        return []


def get_related_occupations(onet_code: str) -> List[Dict]:
    """Get related occupations for an O*NET occupation code."""
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{ONET_BASE_URL}online/occupations/{onet_code}/related_occupations",
                auth=_auth(),
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                return []
            return resp.json().get("related_occupation", [])
    except Exception:
        return []


def find_transferable_skills(resume_skills: list, job_skills: list) -> Dict:
    """
    For each job skill not found in resume_skills, find the best-matching
    resume skill based on O*NET occupation overlap (Jaccard similarity).

    Returns the same format as groq_service.analyze_transferable_skills:
    {"transferable_skills": [{missing_skill, transferable_from, confidence, explanation}]}
    """
    resume_lower = {s.lower().strip() for s in resume_skills}
    job_lower = [s.lower().strip() for s in job_skills]
    missing = [s for s in job_lower if s not in resume_lower]

    if not missing:
        return {"transferable_skills": []}

    # Fetch occupation code sets for every relevant skill (one API call each)
    all_skills = list(resume_lower) + missing
    skill_codes: dict[str, set] = {}
    for skill in all_skills:
        if skill not in skill_codes:
            occs = search_occupation(skill)
            skill_codes[skill] = {o.get("code", "") for o in occs if o.get("code")}

    results = []
    for missing_skill in missing:
        missing_codes = skill_codes.get(missing_skill, set())
        if not missing_codes:
            continue

        best_skill: str | None = None
        best_jaccard = 0.0
        best_overlap = 0

        for resume_skill in resume_lower:
            resume_codes = skill_codes.get(resume_skill, set())
            if not resume_codes:
                continue
            union = missing_codes | resume_codes
            overlap = missing_codes & resume_codes
            jaccard = len(overlap) / len(union) if union else 0.0
            if jaccard > best_jaccard:
                best_jaccard = jaccard
                best_skill = resume_skill
                best_overlap = len(overlap)

        if best_skill is None or best_jaccard < 0.05:
            continue

        if best_jaccard >= 0.3:
            confidence = "high"
        elif best_jaccard >= 0.15:
            confidence = "medium"
        else:
            confidence = "low"

        results.append({
            "missing_skill": missing_skill,
            "transferable_from": best_skill,
            "confidence": confidence,
            "explanation": (
                f"'{best_skill}' and '{missing_skill}' co-occur in "
                f"{best_overlap} O*NET occupation{'s' if best_overlap != 1 else ''}, "
                "suggesting transferable experience."
            ),
        })

    return {"transferable_skills": results}


async def find_transferable_skills_async(
    resume_skills: list, job_skills: list
) -> Dict:
    return await asyncio.to_thread(find_transferable_skills, resume_skills, job_skills)
