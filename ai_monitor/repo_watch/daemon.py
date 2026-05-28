# -*- coding: utf-8 -*-
"""Hourly daemon loop for repository watch jobs."""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from ai_monitor.config.settings import get_settings
from ai_monitor.repo_watch.helpers import branch_label, job_config_from_record
from ai_monitor.repo_watch.service import REPO_PLATFORMS
from ai_monitor.scheduler.jobs import MonitoringJob
from ai_monitor.store.database import get_session, init_db
from ai_monitor.store.models import MonitoringJob as JobModel

logger = logging.getLogger("ai_monitor")


async def run_all_repo_jobs() -> int:
    """Execute every active github/gitee watch job once."""
    count = 0
    async with get_session() as session:
        result = await session.execute(
            select(JobModel).where(
                JobModel.status == "active",
                JobModel.source_type.in_(REPO_PLATFORMS),
            )
        )
        rows = list(result.scalars().all())

    for record in rows:
        config = job_config_from_record(record)
        job = MonitoringJob(config)
        run_result = await job.execute()
        count += 1
        if run_result.repo_updated:
            br = branch_label(config.branch)
            print(
                f"[{datetime.utcnow().isoformat()}] UPDATE "
                f"{record.platform}/{record.repo}@{br} — "
                f"{run_result.commit_author} @ {run_result.commit_at}"
            )
        elif run_result.status == "failed":
            print(f"[ERROR] {record.job_id}: {run_result.error_message}")
    return count


async def daemon_loop() -> None:
    """Poll all repo watch jobs every hour (configurable)."""
    settings = get_settings()
    interval = settings.REPO_WATCH_INTERVAL_SECONDS
    await init_db()
    logging.basicConfig(level=logging.INFO)
    print(
        f"[repo_watch] Daemon started — interval={interval}s "
        f"({interval // 3600}h), platforms={', '.join(REPO_PLATFORMS)}"
    )

    while True:
        try:
            n = await run_all_repo_jobs()
            print(f"[repo_watch] Checked {n} job(s) at {datetime.utcnow().isoformat()}Z")
        except Exception as e:
            logger.exception("[repo_watch] Daemon cycle failed: %s", e)
        await asyncio.sleep(interval)
