# -*- coding: utf-8 -*-
"""Unified daemon: social media + repository watch jobs."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select

from ai_monitor.config.settings import get_settings
from ai_monitor.repo_watch.daemon import run_all_repo_jobs
from ai_monitor.repo_watch.service import REPO_PLATFORMS
from ai_monitor.scheduler.base import JobConfig
from ai_monitor.scheduler.jobs import MonitoringJob
from ai_monitor.store.database import get_session, init_db
from ai_monitor.store.models import MonitoringJob as JobModel

logger = logging.getLogger("ai_monitor")
_last_feishu_sync_at: Optional[datetime] = None
_last_branch_sync_at: Optional[datetime] = None

# Minimal cron → seconds mapping
CRON_INTERVALS = {
    "0 * * * *": 3600,
    "0 */2 * * *": 7200,
    "0 */4 * * *": 14400,
    "0 0 * * *": 86400,
}


def cron_to_interval(cron: str) -> int:
    return CRON_INTERVALS.get(cron.strip(), 7200)


def _job_due(record: JobModel, interval: int) -> bool:
    if not record.last_run_at:
        return True
    elapsed = (datetime.utcnow() - record.last_run_at).total_seconds()
    return elapsed >= interval


async def run_social_jobs() -> int:
    count = 0
    async with get_session() as session:
        result = await session.execute(
            select(JobModel).where(
                JobModel.status == "active",
                JobModel.source_type == "social",
            )
        )
        rows = list(result.scalars().all())

    for record in rows:
        interval = cron_to_interval(record.cron_expression or "0 */2 * * *")
        if not _job_due(record, interval):
            continue
        config = JobConfig(
            job_id=record.job_id,
            source_type=record.source_type or "social",
            platform=record.platform,
            repo=record.repo or "",
            keywords=record.keywords or "",
            crawler_type=record.crawler_type,
            cron_expression=record.cron_expression,
            save_option=record.save_option,
            enable_comments=record.enable_comments,
            max_notes=record.max_notes,
            max_comments=10,
            start_page=record.start_page,
            rule_set_ids=record.rule_set_ids or [],
        )
        print(f"[daemon] Running social job {record.job_id} ({record.platform})...")
        run = await MonitoringJob(config).execute()
        count += 1
        print(
            f"  -> status={run.status} crawled={run.items_crawled} "
            f"analyzed={run.items_analyzed} alerts={run.alerts_triggered}"
        )
        if run.error_message:
            print(f"  -> error: {run.error_message}")
    return count


async def run_daemon_cycle() -> dict:
    global _last_feishu_sync_at, _last_branch_sync_at
    settings = get_settings()
    now = datetime.utcnow()
    feishu_n = 0
    branch_sync = None

    if (
        settings.FEISHU_REPO_DOC_TOKEN
        and settings.FEISHU_APP_ID
        and settings.FEISHU_APP_SECRET
        and (
            _last_feishu_sync_at is None
            or (now - _last_feishu_sync_at).total_seconds() >= settings.FEISHU_SYNC_INTERVAL_SECONDS
        )
    ):
        from ai_monitor.feishu.sync import sync_repositories_from_feishu

        feishu_result = await sync_repositories_from_feishu(run_reconcile=False)
        feishu_n = feishu_result.get("found", 0)
        _last_feishu_sync_at = now

    if (
        _last_branch_sync_at is None
        or (now - _last_branch_sync_at).total_seconds() >= settings.REPO_BRANCH_SYNC_INTERVAL_SECONDS
    ):
        from ai_monitor.repo_watch.reconciler import reconcile_repositories

        branch_sync = await reconcile_repositories()
        _last_branch_sync_at = now

    repo_n = await run_all_repo_jobs()
    social_n = await run_social_jobs()
    return {
        "repo_jobs": repo_n,
        "social_jobs": social_n,
        "feishu_repos": feishu_n,
        "branch_sync": branch_sync,
    }


async def daemon_loop(interval_seconds: Optional[int] = None) -> None:
    settings = get_settings()
    interval = interval_seconds or settings.REPO_WATCH_INTERVAL_SECONDS
    await init_db()
    logging.basicConfig(level=logging.INFO)
    print(f"[daemon] Unified monitor started (cycle every {interval}s)")

    while True:
        try:
            stats = await run_daemon_cycle()
            print(
                f"[daemon] Cycle done at {datetime.utcnow().isoformat()}Z — "
                f"repo={stats['repo_jobs']} social={stats['social_jobs']}"
            )
        except Exception as e:
            logger.exception("[daemon] Cycle failed: %s", e)
        await asyncio.sleep(interval)
