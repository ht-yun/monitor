# -*- coding: utf-8 -*-
"""Check repository for new commits and persist update events."""

import logging
from datetime import datetime
from typing import Optional, Tuple

from sqlalchemy import select

from ai_monitor.collectors.gitee_collector import GiteeCollector
from ai_monitor.collectors.github_collector import GitHubCollector
from ai_monitor.repo_watch.helpers import branch_label
from ai_monitor.scheduler.base import JobConfig, JobRunResult
from ai_monitor.store.database import get_session
from ai_monitor.store.models import MonitoringJob, RepoUpdateEvent

logger = logging.getLogger("ai_monitor")

REPO_CRON_HOURLY = "0 * * * *"
REPO_PLATFORMS = ("github", "gitee")


async def check_repo_update(config: JobConfig) -> JobRunResult:
    """Poll latest commit; record event when SHA changes."""
    platform = config.platform
    repo = (config.repo or config.keywords or "").strip()
    if platform not in REPO_PLATFORMS:
        raise ValueError(f"Unsupported repo platform: {platform}")
    if not repo:
        raise ValueError("Repository is required (owner/name)")

    result = JobRunResult(
        job_id=config.job_id,
        platform=platform,
        status="success",
        started_at=datetime.utcnow(),
    )

    branch = (config.branch or "").strip()

    try:
        commit = await _fetch_latest(platform, repo, branch)
        has_update, is_baseline = await _apply_commit_state(
            config.job_id, platform, repo, branch, commit
        )

        result.commit_sha = commit.sha
        result.commit_author = commit.author
        result.commit_at = commit.committed_at
        result.commit_message = commit.message
        result.repo_updated = has_update

        if is_baseline:
            result.status = "success"
            logger.info(
                "[repo_watch] Baseline set for %s/%s@%s @ %s by %s",
                platform,
                repo,
                branch_label(branch),
                commit.sha[:8],
                commit.author,
            )
        elif has_update:
            logger.info(
                "[repo_watch] UPDATE %s/%s@%s — author=%s time=%s sha=%s",
                platform,
                repo,
                branch_label(branch),
                commit.author,
                commit.committed_at.isoformat(),
                commit.sha[:8],
            )
            await _notify_repo_update(platform, repo, branch, commit, config.job_id)
        else:
            logger.debug(
                "[repo_watch] No change for %s/%s@%s",
                platform,
                repo,
                branch_label(branch),
            )

        await _update_job_run_meta(config.job_id, result.status, commit, has_update)

    except Exception as e:
        result.status = "failed"
        result.error_message = str(e)
        logger.exception("[repo_watch] Failed %s/%s: %s", platform, repo, e)
        await _update_job_run_meta(config.job_id, "failed", None, False)

    result.completed_at = datetime.utcnow()
    return result


async def _fetch_latest(platform: str, repo: str, branch: str = ""):
    if platform == "github":
        return await GitHubCollector().fetch_latest_commit(repo, branch)
    return await GiteeCollector().fetch_latest_commit(repo, branch)


async def _apply_commit_state(
    job_id: str,
    platform: str,
    repo: str,
    branch: str,
    commit,
) -> Tuple[bool, bool]:
    """Returns (has_update, is_baseline)."""
    async with get_session() as session:
        row = await session.execute(
            select(MonitoringJob).where(MonitoringJob.job_id == job_id)
        )
        job = row.scalar_one_or_none()
        if not job:
            raise ValueError(f"Monitoring job not found: {job_id}")

        previous_sha = job.last_sha
        is_baseline = not previous_sha

        if previous_sha == commit.sha:
            job.last_run_at = datetime.utcnow()
            job.last_run_status = "success"
            await _update_branch_snapshot(session, job_id, commit)
            return False, False

        if not is_baseline:
            session.add(
                RepoUpdateEvent(
                    job_id=job_id,
                    platform=platform,
                    repo=repo,
                    branch=branch or "",
                    commit_sha=commit.sha,
                    commit_author=commit.author,
                    committed_at=commit.committed_at,
                    commit_message=commit.message[:500] if commit.message else "",
                    commit_url=commit.url,
                )
            )

        job.last_sha = commit.sha
        job.last_commit_author = commit.author
        job.last_commit_at = commit.committed_at
        job.last_run_at = datetime.utcnow()
        job.last_run_status = "success"
        job.updated_at = datetime.utcnow()
        await _update_branch_snapshot(session, job_id, commit)

        return (not is_baseline), is_baseline


async def _update_job_run_meta(
    job_id: str,
    status: str,
    commit: Optional[object],
    has_update: bool,
) -> None:
    async with get_session() as session:
        row = await session.execute(
            select(MonitoringJob).where(MonitoringJob.job_id == job_id)
        )
        job = row.scalar_one_or_none()
        if job:
            job.last_run_at = datetime.utcnow()
            job.last_run_status = status


async def _update_branch_snapshot(session, job_id: str, commit) -> None:
    from ai_monitor.store.models import MonitoredBranch

    row = await session.execute(
        select(MonitoredBranch).where(MonitoredBranch.job_id == job_id)
    )
    branch = row.scalar_one_or_none()
    if branch:
        branch.last_sha = commit.sha
        branch.last_commit_author = commit.author
        branch.last_commit_at = commit.committed_at
        branch.updated_at = datetime.utcnow()


async def _notify_repo_update(
    platform: str, repo: str, branch: str, commit, job_id: str
) -> None:
    from ai_monitor.notification.dispatcher import NotificationDispatcher

    summary = (
        f"仓库 {platform}/{repo} 分支 {branch_label(branch)} 有新提交\n"
        f"提交人: {commit.author}\n"
        f"时间: {commit.committed_at.isoformat()}\n"
        f"SHA: {commit.sha[:12]}\n"
        f"说明: {commit.message[:200]}"
    )
    dispatcher = NotificationDispatcher()
    channels = ["console"]
    if await _notification_channel_enabled("dingtalk"):
        channels.append("dingtalk")
    if await _notification_channel_enabled("feishu"):
        channels.append("feishu")
    if await _notification_channel_enabled("webhook"):
        channels.append("webhook")

    await dispatcher.send_alert(
        rule_name="仓库代码更新",
        severity="info",
        platform=platform,
        job_id=job_id,
        summary=summary,
        matched_count=1,
        channels=channels,
        sample=commit.message[:200],
    )


async def _notification_channel_enabled(channel_name: str) -> bool:
    from ai_monitor.config.settings import get_settings
    from ai_monitor.store.models import NotificationConfig

    async with get_session() as session:
        result = await session.execute(
            select(NotificationConfig).where(NotificationConfig.channel_name == channel_name)
        )
        row = result.scalar_one_or_none()
        if row and row.is_enabled:
            return True

    settings = get_settings()
    if channel_name == "dingtalk":
        return bool(settings.DINGTALK_WEBHOOK_URL)
    if channel_name == "feishu":
        return bool(settings.FEISHU_WEBHOOK_URL)
    if channel_name == "webhook":
        return bool(settings.WEBHOOK_URL)
    return False
