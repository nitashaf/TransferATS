import asyncio
import json
import re
from typing import Any, Dict, List

import google.generativeai as genai

from app.config import get_settings

settings = get_settings()
genai.configure(api_key=settings.GEMINI_API_KEY)

def _build_model() -> genai.GenerativeModel:
    # Prefer newer Gemini models, but fall back to whatever is enabled
    # for this API key/project and supports generateContent.
    preferred_models = [
        "models/gemini-2.0-flash",
        "models/gemini-1.5-flash",
        "models/gemini-1.5-pro",
        "models/gemini-pro",
    ]
    try:
        available = list(genai.list_models())
        generate_content_models = [
            m.name
            for m in available
            if "generateContent" in getattr(m, "supported_generation_methods", [])
        ]
        for candidate in preferred_models:
            if candidate in generate_content_models:
                return genai.GenerativeModel(candidate)
        if generate_content_models:
            return genai.GenerativeModel(generate_content_models[0])
    except Exception:
        # Fall back to a broadly available default if list_models is unavailable.
        pass
    return genai.GenerativeModel("models/gemini-1.5-flash")


_model = _build_model()


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
        "python",
        "java",
        "javascript",
        "typescript",
        "sql",
        "excel",
        "power bi",
        "tableau",
        "aws",
        "azure",
        "gcp",
        "docker",
        "kubernetes",
        "git",
        "fastapi",
        "django",
        "flask",
        "react",
        "node.js",
        "machine learning",
        "data analysis",
        "communication",
        "leadership",
    ]
    lower_text = text.lower()
    found = [skill for skill in known_skills if skill in lower_text]
    return found[:30]


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
        response = _model.generate_content(prompt)
        return json.loads(_clean_json(response.text))
    except Exception:
        # Fallback for quota/rate-limit/model-access failures.
        return {
            "skills": _extract_skills_fallback(text),
            "name": _extract_name_fallback(text),
            "email": _extract_email_fallback(text),
            "experience_years": _estimate_experience_years_fallback(text),
        }


def _sync_get_embeddings(text: str) -> List[float]:
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=text[:8000],
        task_type="retrieval_document",
    )
    return result["embedding"]


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
        response = _model.generate_content(prompt)
        return json.loads(_clean_json(response.text))
    except Exception:
        return {"transferable_skills": []}


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
        response = _model.generate_content(prompt)
        return json.loads(_clean_json(response.text))
    except Exception:
        return {
            "title": None,
            "description": text[:500],
            "required_skills": _extract_skills_fallback(text),
            "nice_to_have_skills": [],
        }


async def extract_skills(text: str) -> Dict[str, Any]:
    return await asyncio.to_thread(_sync_extract_skills, text)


async def extract_job_details(text: str) -> Dict[str, Any]:
    return await asyncio.to_thread(_sync_extract_job_details, text)


async def get_embeddings(text: str) -> List[float]:
    return await asyncio.to_thread(_sync_get_embeddings, text)


async def analyze_transferable_skills(
    resume_text: str, job_description: str, missing_skills: List[str]
) -> Dict[str, Any]:
    return await asyncio.to_thread(
        _sync_analyze_transferable, resume_text, job_description, missing_skills
    )
