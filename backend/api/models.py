from datetime import date
from typing import Optional

from pydantic import BaseModel


class Job(BaseModel):
    id: int
    title: str
    company: str
    location_raw: Optional[str] = None
    location_tag: str
    job_type: Optional[str] = None
    source_name: str
    source_url: str
    apply_url: str
    posted_date: Optional[date] = None
    fetched_date: date
    skills: Optional[str] = None
    experience_level: Optional[str] = None
    role_type: Optional[str] = None


class JobsResponse(BaseModel):
    fetched_at: str
    total: int
    jobs: list[Job]


class HealthResponse(BaseModel):
    status: str
    last_run: Optional[str] = None
    last_run_status: Optional[str] = None
    total_jobs: int
    sources: dict[str, Optional[str]]
