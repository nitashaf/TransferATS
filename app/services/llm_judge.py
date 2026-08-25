"""
LLM Judge — evaluates resume against job requirements holistically.
Uses Claude for contextual understanding beyond keyword matching.
"""
import asyncio
import json
from typing import Dict, List

from app.services.claude_client import call_claude
from app.services.groq_service import _clean_json


def _sync_judge(
    resume_content: str,
    job_description: str,
    job_skills: List[str],
) -> Dict:

    prompt = f"""You are an expert technical recruiter evaluating a candidate.

JOB DESCRIPTION:
{job_description}

REQUIRED SKILLS TO EVALUATE: {", ".join(job_skills)}

CANDIDATE RESUME:
{resume_content}

For EACH required skill, evaluate if the candidate meets it.
Consider:
- Direct mentions (exact skill named in resume)
- Implied experience ("deployed on AWS" satisfies "cloud experience")
- Related technology ("Apache Kafka" satisfies "kafka")
- Demonstrated through work ("led team of 8" satisfies "leadership")
- Partial match ("AWS experience" partially satisfies "azure")

Return ONLY valid JSON, no markdown:
{{
  "evaluations": [
    {{
      "skill": "required skill name",
      "status": "MET" | "PARTIAL" | "NOT_MET",
      "confidence": "high" | "medium" | "low",
      "evidence": "exact quote from resume supporting this or null",
      "explanation": "one sentence why this status was assigned"
    }}
  ],
  "overall_assessment": "2-3 sentence summary of candidate fit",
  "hiring_recommendation": "STRONG_YES" | "YES" | "MAYBE" | "NO"
}}"""

    try:
        content = call_claude(prompt, max_tokens=2000)
        return json.loads(_clean_json(content))
    except Exception as e:
        print(f"[Claude Judge ERROR] {e}")
        return {
            "evaluations": [],
            "overall_assessment": "",
            "hiring_recommendation": "MAYBE"
        }


async def evaluate_candidate(
    resume_content: str,
    job_description: str,
    job_skills: List[str],
) -> Dict:
    return await asyncio.to_thread(
        _sync_judge,
        resume_content,
        job_description,
        job_skills,
    )


def calculate_llm_score(evaluations: List[Dict]) -> float:
    if not evaluations:
        return 0.0

    weight_map = {
        "MET": 1.0,
        "PARTIAL": 0.5,
        "NOT_MET": 0.0
    }

    scores = [
        weight_map.get(e.get("status", "NOT_MET"), 0.0)
        for e in evaluations
    ]

    return round((sum(scores) / len(scores)) * 100, 2)