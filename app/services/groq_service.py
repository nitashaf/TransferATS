"""
Extraction Service — uses Ollama for resume extraction
and Claude for job description extraction.

Ollama: fast, free, good for structured resume text
Claude: handles any job description format and length
"""
import asyncio
import json
import logging
import re
from typing import Any, Dict, List

import httpx
from app.config import get_settings
from app.services.claude_client import call_claude

settings = get_settings()
logger = logging.getLogger(__name__)
_OLLAMA_URL = "http://localhost:11434/api/chat"
_OLLAMA_MODEL = "llama3.2"


# ─── JSON Utilities ───────────────────────────────────────────────────────────

def _clean_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


# ─── Fallback utilities (when LLM fails) ─────────────────────────────────────

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


# ─── Ollama client ────────────────────────────────────────────────────────────

def _ollama_call(prompt: str) -> str:
    """Call local Ollama for resume extraction."""
    response = httpx.post(
        _OLLAMA_URL,
        json={
            "model": _OLLAMA_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.1}
        },
        timeout=180.0
    )
    response.raise_for_status()
    return response.json()["message"]["content"]


# ─── Resume extraction (Ollama) ───────────────────────────────────────────────

def _sync_extract_skills(text: str) -> Dict[str, Any]:
    """
    Extract skills from resume using Ollama.
    Ollama works well for resume text — structured, consistent format.
    Full text passed — no truncation for better coverage.
    """
    prompt = f"""Extract ALL technical and professional skills from this resume.

Resume:
{text[:6000]}

Return ONLY valid JSON, no markdown:
{{
  "skills": ["skill1", "skill2", ...],
  "name": "full name or null",
  "email": "email or null",
  "experience_years": number or null
}}

Rules:
- Extract EVERY skill mentioned
- Include: languages, frameworks, databases, cloud, tools, methodologies
- Keep atomic and lowercase: "spring boot" not "spring boot framework"
- Include soft skills if explicitly mentioned
- Extract at least 20-40 skills from a senior resume
- Examples: java, spring boot, aws, kafka, postgresql, docker, kubernetes"""

    try:
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured.")
        content = call_claude(prompt, max_tokens=1500)
        return json.loads(_clean_json(content))
    except Exception:
        logger.exception("Claude resume extraction failed; using fallback extraction")
        return {
            "skills": _extract_skills_fallback(text),
            "name": _extract_name_fallback(text),
            "email": _extract_email_fallback(text),
            "experience_years": _estimate_experience_years_fallback(text),
        }


# ─── Job extraction (Claude) ──────────────────────────────────────────────────

def _sync_extract_job_details(text: str) -> Dict[str, Any]:
    """
    Extract skills from job description using Claude.
    Claude handles any format, length, and writing style.
    No text truncation needed — Claude has 200k context window.
    """
    prompt = f"""Extract structured information from this job posting.
Handle any format — explicit skills lists, embedded requirements,
or descriptions without clear sections.

Job Posting:
{text}

Return ONLY valid JSON, no markdown:
{{
  "title": "exact job title",
  "description": "2-3 sentence summary of the role",
  "required_skills": ["atomic", "skills", "only"],
  "nice_to_have_skills": ["atomic", "skills", "only"]
}}

Rules:
- Extract specific named skills regardless of how described
- "experience with Java" → "java"
- "must know SQL" → "sql"
- "ability to debug" → "debugging"
- "strong communicator" → "communication"
- "2+ years leadership" → "leadership"
- NEVER extract vague phrases:
  "modern frameworks" ❌
  "cloud platforms" ❌  
  "various tools" ❌
- Keep all skills lowercase and atomic
- required_skills: must-have, required, essential
- nice_to_have_skills: preferred, bonus, plus, desired"""

    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured on the server.")

    try:
        content = call_claude(prompt, max_tokens=1000)
        result = json.loads(_clean_json(content))
    except Exception as exc:
        logger.exception("Claude job extraction failed")
        raise RuntimeError("The AI job extraction service failed.") from exc

    if not result.get("required_skills"):
        logger.warning("Claude job extraction returned no required skills")
        raise RuntimeError("No required skills could be extracted from this job posting.")

    return result


# ─── Transferable skills analysis (Ollama) ───────────────────────────────────

def _sync_analyze_transferable(
    resume_text: str, job_description: str, missing_skills: List[str]
) -> Dict[str, Any]:
    """
    Analyze transferable skills using Ollama.
    Only called for skills LLM Judge marked as NOT_MET.
    """
    prompt = f"""You are an expert career counselor analyzing transferable skills.

Resume (excerpt):
{resume_text[:2500]}

Job Description (excerpt):
{job_description[:2500]}

Missing Required Skills: {", ".join(missing_skills)}

For each missing skill, determine if the candidate has related 
transferable experience from their background.

Return ONLY valid JSON, no markdown:
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
        content = _ollama_call(prompt)
        return json.loads(_clean_json(content))
    except Exception as e:
        print(f"[Ollama Transferable ERROR] {e}")
        return {"transferable_skills": []}


# ─── Async wrappers ───────────────────────────────────────────────────────────

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
