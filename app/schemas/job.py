from typing import List, Optional
from pydantic import BaseModel, model_validator


class JobCreate(BaseModel):
    # Mode 1 – manual JSON
    title: Optional[str] = None
    description: Optional[str] = None
    required_skills: Optional[List[str]] = []
    nice_to_have_skills: Optional[List[str]] = []
    # Mode 2 – raw job description text
    raw_text: Optional[str] = None
    # Mode 3 – URL to a job posting
    url: Optional[str] = None

    @model_validator(mode="after")
    def check_input_mode(self) -> "JobCreate":
        has_manual = bool(self.title and self.description)
        has_url = bool(self.url)
        has_raw = bool(self.raw_text)
        if not (has_manual or has_url or has_raw):
            raise ValueError(
                "Provide one of: (title + description), url, or raw_text."
            )
        return self
