import asyncio
from typing import Optional

import requests
from bs4 import BeautifulSoup

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

_NOISE_TAGS = {"script", "style", "nav", "footer", "header", "aside", "noscript", "iframe"}

# Ordered list of (tag, attrs) pairs tried before falling back to full body.
# Each tuple is (tag_name_or_None, attrs_dict).
_JOB_SELECTORS = [
    (None,  {"id": "jobDescriptionText"}),       # Indeed
    (None,  {"id": "content"}),                   # Greenhouse
    ("div", {"class": "description__text"}),      # LinkedIn
    ("div", {"class": "jobsearch-jobDescriptionText"}),  # Indeed alt
    ("div", {"class": "posting-description"}),    # Lever
    ("div", {"class": "job-description"}),        # Generic
    ("div", {"class": "job_description"}),        # Generic alt
    ("section", {"class": "job-description"}),
    ("article", {}),
    ("main",    {}),
]


def _scrape_sync(url: str, timeout: int = 15) -> str:
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise ValueError(f"Failed to fetch URL: {exc}") from exc

    soup = BeautifulSoup(resp.text, "lxml")

    for tag in soup.find_all(_NOISE_TAGS):
        tag.decompose()

    # Try job-specific selectors first
    for tag_name, attrs in _JOB_SELECTORS:
        element = soup.find(tag_name, attrs=attrs) if attrs else soup.find(tag_name)
        if element:
            text = _clean_text(element.get_text(separator="\n"))
            if len(text) > 200:
                return text

    # Fallback: full body text
    body = soup.find("body") or soup
    return _clean_text(body.get_text(separator="\n"))


def _clean_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    # Remove consecutive duplicate lines (common in nav/button spam)
    deduped: list[str] = []
    for line in lines:
        if not deduped or line != deduped[-1]:
            deduped.append(line)
    return "\n".join(deduped)


async def scrape_job_url(url: str) -> str:
    """Fetch a job posting URL and return clean plain text."""
    return await asyncio.to_thread(_scrape_sync, url)
