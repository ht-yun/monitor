# -*- coding: utf-8 -*-
"""Abstract base classes for the scheduler module."""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JobConfig(BaseModel):
    """Configuration for a single monitoring job."""

    job_id: str = ""
    source_type: str = "social"  # social | github | gitee
    platform: str  # xhs, dy, ... or github | gitee
    repo: str = ""  # owner/name for github | gitee
    branch: str = ""  # git ref; empty = default branch
    keywords: str = ""
    crawler_type: str = "search"  # search, detail, creator
    cron_expression: str = "0 */2 * * *"  # every 2 hours
    save_option: str = "jsonl"
    enable_comments: bool = True
    enable_sub_comments: bool = False
    max_notes: int = 20
    max_comments: int = 10
    start_page: int = 1
    rule_set_ids: List[str] = Field(default_factory=list)
    login_type: str = "cookie"
    cookies: str = ""
    headless: bool = True


class JobRunResult(BaseModel):
    """Result of a single job execution."""

    job_id: str
    platform: str
    status: str  # success | failed | partial
    items_crawled: int = 0
    comments_crawled: int = 0
    items_analyzed: int = 0
    alerts_triggered: int = 0
    repo_updated: bool = False
    commit_sha: Optional[str] = None
    commit_author: Optional[str] = None
    commit_at: Optional[datetime] = None
    commit_message: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class AbstractScheduler(ABC):
    """Abstract scheduler for managing periodic monitoring jobs."""

    @abstractmethod
    async def add_job(self, config: JobConfig) -> str:
        """Register a new monitoring job, returns job_id."""

    @abstractmethod
    async def remove_job(self, job_id: str) -> bool:
        """Remove a monitoring job."""

    @abstractmethod
    async def pause_job(self, job_id: str) -> bool:
        """Pause a job without removing it."""

    @abstractmethod
    async def resume_job(self, job_id: str) -> bool:
        """Resume a paused job."""

    @abstractmethod
    async def run_job_now(self, job_id: str) -> JobRunResult:
        """Trigger a job execution immediately."""

    @abstractmethod
    async def start(self) -> None:
        """Start the scheduler."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully stop the scheduler."""

    @abstractmethod
    async def list_jobs(self) -> List[Dict[str, Any]]:
        """List all registered jobs."""

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific job's details."""

    @abstractmethod
    async def get_run_history(self, job_id: str, limit: int = 10) -> List[JobRunResult]:
        """Get recent run history for a job."""
