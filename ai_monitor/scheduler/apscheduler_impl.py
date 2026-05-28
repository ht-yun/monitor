# -*- coding: utf-8 -*-
"""APScheduler implementation of the abstract scheduler."""

import sys
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

from apscheduler import AsyncScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.datastores.sqlalchemy import SQLAlchemyDataStore

from ai_monitor.config.settings import get_settings
from ai_monitor.scheduler.base import AbstractScheduler, JobConfig, JobRunResult
from ai_monitor.scheduler.jobs import MonitoringJob


class APSchedulerImpl(AbstractScheduler):
    """APScheduler-based scheduler implementation."""

    def __init__(self):
        self.settings = get_settings()
        self._scheduler: Optional[AsyncScheduler] = None
        self._jobs: Dict[str, MonitoringJob] = {}
        self._run_history: Dict[str, List[JobRunResult]] = {}

    async def start(self) -> None:
        datastore = SQLAlchemyDataStore(
            engine=self.settings.DATABASE_URL
            .replace("sqlite+aiosqlite", "sqlite")
            .replace("///", ":///")
        )
        self._scheduler = AsyncScheduler(data_store=datastore)
        async with self._scheduler:
            await self._scheduler.start_in_background()
        # Load persisted jobs
        await self._load_persisted_jobs()

    async def shutdown(self) -> None:
        if self._scheduler:
            await self._scheduler.stop()

    async def add_job(self, config: JobConfig) -> str:
        if not config.job_id:
            from uuid import uuid4

            if config.source_type in ("github", "gitee"):
                slug = (config.repo or config.keywords).replace("/", "_")
                config.job_id = f"{config.platform}_{slug}"
            else:
                config.job_id = f"{config.platform}_{config.crawler_type}_{uuid4().hex[:8]}"

        job = MonitoringJob(config)
        self._jobs[config.job_id] = job

        async with self._scheduler as sched:
            await sched.add_schedule(
                self._execute_job_wrapper,
                CronTrigger.from_crontab(config.cron_expression),
                id=config.job_id,
                kwargs={"job_id": config.job_id},
                max_running_jobs=1,
            )

        await self._persist_job(config)
        return config.job_id

    async def remove_job(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False
        async with self._scheduler as sched:
            await sched.delete_schedule(job_id)
        self._jobs.pop(job_id, None)
        await self._delete_persisted_job(job_id)
        return True

    async def pause_job(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False
        async with self._scheduler as sched:
            await sched.pause_schedule(job_id)
        await self._update_job_status(job_id, "paused")
        return True

    async def resume_job(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False
        async with self._scheduler as sched:
            await sched.resume_schedule(job_id)
        await self._update_job_status(job_id, "active")
        return True

    async def run_job_now(self, job_id: str) -> JobRunResult:
        job = self._jobs.get(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")
        started = datetime.utcnow()
        try:
            result = await job.execute()
            result.started_at = started
            result.completed_at = datetime.utcnow()
        except Exception as e:
            result = JobRunResult(
                job_id=job_id,
                platform=job.config.platform,
                status="failed",
                error_message=str(e),
                started_at=started,
                completed_at=datetime.utcnow(),
            )
        self._record_run_history(job_id, result)
        return result

    async def list_jobs(self) -> List[Dict[str, Any]]:
        result = []
        async with self._scheduler as sched:
            schedules = await sched.get_schedules()
        schedule_map = {s.id: s for s in schedules}
        for job_id, job in self._jobs.items():
            s = schedule_map.get(job_id)
            result.append({
                "job_id": job_id,
                "platform": job.config.platform,
                "keywords": job.config.keywords,
                "crawler_type": job.config.crawler_type,
                "cron_expression": job.config.cron_expression,
                "next_run": str(s.next_fire_time) if s and s.next_fire_time else None,
                "status": "active" if s else "paused",
            })
        return result

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        jobs = await self.list_jobs()
        for j in jobs:
            if j["job_id"] == job_id:
                return j
        return None

    async def get_run_history(self, job_id: str, limit: int = 10) -> List[JobRunResult]:
        history = self._run_history.get(job_id, [])
        return history[-limit:]

    # ----- private -----

    async def _execute_job_wrapper(self, job_id: str):
        """Wrapper called by APScheduler."""
        await self.run_job_now(job_id)

    def _record_run_history(self, job_id: str, result: JobRunResult):
        if job_id not in self._run_history:
            self._run_history[job_id] = []
        self._run_history[job_id].append(result)
        if len(self._run_history[job_id]) > 100:
            self._run_history[job_id] = self._run_history[job_id][-100:]

    async def _load_persisted_jobs(self):
        """Load jobs from database on startup."""
        from ai_monitor.store.database import get_session
        from ai_monitor.store.models import MonitoringJob as JobModel
        from sqlalchemy import select

        async with get_session() as session:
            result = await session.execute(
                select(JobModel).where(JobModel.status == "active")
            )
            for record in result.scalars():
                from ai_monitor.repo_watch.helpers import job_config_from_record

                config = job_config_from_record(record)
                await self.add_job(config)

    async def _persist_job(self, config: JobConfig):
        from ai_monitor.store.database import get_session
        from ai_monitor.store.models import MonitoringJob as JobModel
        from sqlalchemy import select

        async with get_session() as session:
            existing = await session.execute(
                select(JobModel).where(JobModel.job_id == config.job_id)
            )
            record = existing.scalar_one_or_none()
            if record:
                record.source_type = config.source_type
                record.platform = config.platform
                record.repo = config.repo or None
                record.branch = config.branch or None
                record.keywords = config.keywords
                record.crawler_type = config.crawler_type
                record.cron_expression = config.cron_expression
            else:
                record = JobModel(
                    job_id=config.job_id,
                    source_type=config.source_type,
                    platform=config.platform,
                    repo=config.repo or None,
                    branch=config.branch or None,
                    keywords=config.keywords,
                    crawler_type=config.crawler_type,
                    cron_expression=config.cron_expression,
                    save_option=config.save_option,
                    enable_comments=config.enable_comments,
                    max_notes=config.max_notes,
                    start_page=config.start_page,
                    rule_set_ids=config.rule_set_ids,
                )
                session.add(record)

    async def _delete_persisted_job(self, job_id: str):
        from ai_monitor.store.database import get_session
        from ai_monitor.store.models import MonitoringJob as JobModel
        from sqlalchemy import select

        async with get_session() as session:
            result = await session.execute(
                select(JobModel).where(JobModel.job_id == job_id)
            )
            record = result.scalar_one_or_none()
            if record:
                await session.delete(record)

    async def _update_job_status(self, job_id: str, status: str):
        from ai_monitor.store.database import get_session
        from ai_monitor.store.models import MonitoringJob as JobModel
        from sqlalchemy import select

        async with get_session() as session:
            result = await session.execute(
                select(JobModel).where(JobModel.job_id == job_id)
            )
            record = result.scalar_one_or_none()
            if record:
                record.status = status
