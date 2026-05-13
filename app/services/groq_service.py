import asyncio
import json
import re
from typing import Any, Dict, List

from groq import Groq

from app.config import get_settings

settings = get_settings()
_client = Groq(api_key=settings.GROQ_API_KEY)

_MODEL = "llama-3.1-8b-instant"


def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _extract_skills_fallback(text: str) -> List[str]:
    known_skills = [
        "python", "java", "javascript", "typescript", "sql", "excel",
        "power bi", "tableau", "aws", "azure", "gcp", "docker", "kubernetes",
        "git", "fastapi", "django", "flask", "react", "node.js",
        "machine learning", "data analysis", "communication", "leadership",
    ]
    lower_text = text.lower()
    return [skill for skill in known_skills if skill in lower_text][:30]


def _extract_email_fallback(text: str) -> str | None:
    match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return match.group(0) if match else None


def _extract_name_fallback(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines[:10]:
        words = line.split()
        if 2 <= len(words) <= 4 and all(w.replace("-", "").isalpha() for w in words):
            return line
    return None


def _estimate_experience_years_fallback(text: str) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)\+?\s+years?", text.lower())
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


def _sync_extract_skills(text: str) -> Dict[str, Any]:
    prompt = f"""Extract structured information from this resume or job description text.

Text:
{text[:6000]}

Return ONLY a valid JSON object (no markdown, no explanation) with these fields:
{{
  "skills": ["list", "of", "technical", "and", "soft", "skills"],
  "name": "candidate full name or null",
  "email": "email address or null",
  "experience_years": estimated years of experience as number or null
}}"""

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1024,
        )
        return json.loads(_clean_json(response.choices[0].message.content))
    except Exception:
        return {
            "skills": _extract_skills_fallback(text),
            "name": _extract_name_fallback(text),
            "email": _extract_email_fallback(text),
            "experience_years": _estimate_experience_years_fallback(text),
        }


def _sync_extract_job_details(text: str) -> Dict[str, Any]:
    prompt = f"""Extract structured job posting information from this text.

Text:
{text[:6000]}

Return ONLY a valid JSON object (no markdown, no explanation) with these fields:
{{
  "title": "job title string",
  "description": "clean 2-4 sentence summary of the role",
  "required_skills": ["must-have", "technical", "and", "soft", "skills"],
  "nice_to_have_skills": ["preferred", "but", "not", "required", "skills"]
}}"""

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1024,
        )
        return json.loads(_clean_json(response.choices[0].message.content))
    except Exception:
        return {
            "title": None,
            "description": text[:500],
            "required_skills": _extract_skills_fallback(text),
            "nice_to_have_skills": [],
        }


def _sync_analyze_transferable(
    resume_text: str, job_description: str, missing_skills: List[str]
) -> Dict[str, Any]:
    prompt = f"""You are an expert career counselor analyzing transferable skills.

Resume (excerpt):
{resume_text[:2500]}

Job Description (excerpt):
{job_description[:2500]}

Missing Required Skills: {", ".join(missing_skills)}

For each missing skill, determine if the candidate has related transferable experience from their background.
Return ONLY a valid JSON object (no markdown):
{{
  "transferable_skills": [
    {{
      "missing_skill": "the required skill they lack",
      "transferable_from": "what experience they have that transfers",
      "confidence": "high | medium | low",
      "explanation": "one sentence explanation"
    }}
  ]
}}"""

    try:
        response = _client.chat.completions.create(
            model=_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1024,
        )
        return json.loads(_clean_json(response.choices[0].message.content))
    except Exception:
        return {"transferable_skills": []}


async def extract_skills(text: str) -> Dict[str, Any]:
    return await asyncio.to_thread(_sync_extract_skills, text)


async def extract_job_details(text: str) -> Dict[str, Any]:
    return await asyncio.to_thread(_sync_extract_job_details, text)


async def analyze_transferable_skills(
    resume_text: str, job_description: str, missing_skills: List[str]
) -> Dict[str, Any]:
    return await asyncio.to_thread(
        _sync_analyze_transferable, resume_text, job_description, missing_skills
    )
