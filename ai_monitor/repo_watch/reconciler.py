# -*- coding: utf-8 -*-
"""Reconcile discovered repositories into branch watch jobs."""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select

from ai_monitor.collectors.gitee_collector import GiteeCollector
from ai_monitor.collectors.github_collector import GitHubCollector
from ai_monitor.repo_watch.helpers import make_repo_job_id
from ai_monitor.repo_watch.service import REPO_CRON_HOURLY, REPO_PLATFORMS
from ai_monitor.store.database import get_session
from ai_monitor.store.models import MonitoredBranch, MonitoredRepository, MonitoringJob


def _collector_for(platform: str):
    if platform == "github":
        return GitHubCollector()
    if platform == "gitee":
        return GiteeCollector()
    raise ValueError(f"unsupported repository platform: {platform}")


async def reconcile_repositories(repository_id: Optional[int] = None) -> Dict:
    """Discover remote branches and ensure each branch has a watch job."""
    now = datetime.utcnow()
    stats = {
        "repositories": 0,
        "branches_seen": 0,
        "branches_created": 0,
        "branches_updated": 0,
        "jobs_created": 0,
        "jobs_updated": 0,
        "branches_deleted": 0,
        "errors": [],
    }

    async with get_session() as session:
        q = select(MonitoredRepository).where(MonitoredRepository.status != "deleted")
        if repository_id is not None:
            q = q.where(MonitoredRepository.id == repository_id)
        result = await session.execute(q)
        repositories = list(result.scalars().all())

    for repo_row in repositories:
        stats["repositories"] += 1
        try:
            item_stats = await reconcile_repository(repo_row.id, now=now)
            for key in (
                "branches_seen",
                "branches_created",
                "branches_updated",
                "jobs_created",
                "jobs_updated",
                "branches_deleted",
            ):
                stats[key] += item_stats.get(key, 0)
        except Exception as e:
            stats["errors"].append({
                "repository_id": repo_row.id,
                "platform": repo_row.platform,
                "repo": repo_row.repo,
                "error": str(e),
            })
            async with get_session() as session:
                row = await session.get(MonitoredRepository, repo_row.id)
                if row:
                    row.status = "error"
                    row.error_message = str(e)
                    row.updated_at = datetime.utcnow()

    return stats


async def reconcile_repository(repository_id: int, now: Optional[datetime] = None) -> Dict:
    """Reconcile a single repository by id."""
    now = now or datetime.utcnow()
    stats = {
        "branches_seen": 0,
        "branches_created": 0,
        "branches_updated": 0,
        "jobs_created": 0,
        "jobs_updated": 0,
        "branches_deleted": 0,
    }

    async with get_session() as session:
        repo_row = await session.get(MonitoredRepository, repository_id)
        if not repo_row:
            raise ValueError(f"monitored repository not found: {repository_id}")
        platform = repo_row.platform
        repo = repo_row.repo

    collector = _collector_for(platform)
    info = await collector.fetch_repo_info(repo)
    branches = await collector.list_branches(repo)
    remote_names = {b.name for b in branches}
    stats["branches_seen"] = len(remote_names)

    async with get_session() as session:
        repo_row = await session.get(MonitoredRepository, repository_id)
        if not repo_row:
            raise ValueError(f"monitored repository not found: {repository_id}")

        repo_row.default_branch = info.default_branch
        repo_row.repo_url = info.html_url or repo_row.repo_url
        repo_row.status = "active"
        repo_row.error_message = ""
        repo_row.last_branch_sync_at = now
        repo_row.updated_at = now

        existing_result = await session.execute(
            select(MonitoredBranch).where(MonitoredBranch.repository_id == repository_id)
        )
        existing = {row.branch: row for row in existing_result.scalars().all()}

        for branch in branches:
            job_id = make_repo_job_id(platform, repo, branch.name)
            branch_row = existing.get(branch.name)
            if branch_row:
                branch_row.is_default = branch.name == info.default_branch
                branch_row.job_id = branch_row.job_id or job_id
                branch_row.last_sha = branch.sha or branch_row.last_sha
                branch_row.last_seen_at = now
                branch_row.status = "active" if branch_row.status == "deleted" else branch_row.status
                branch_row.updated_at = now
                stats["branches_updated"] += 1
            else:
                branch_row = MonitoredBranch(
                    repository_id=repository_id,
                    branch=branch.name,
                    is_default=branch.name == info.default_branch,
                    job_id=job_id,
                    last_sha=branch.sha,
                    status="active",
                    first_seen_at=now,
                    last_seen_at=now,
                )
                session.add(branch_row)
                stats["branches_created"] += 1

            job_stats = await _ensure_monitoring_job(
                session=session,
                platform=platform,
                repo=repo,
                branch=branch.name,
                job_id=branch_row.job_id or job_id,
            )
            stats["jobs_created"] += job_stats["created"]
            stats["jobs_updated"] += job_stats["updated"]

        for branch_name, branch_row in existing.items():
            if branch_name not in remote_names and branch_row.status != "deleted":
                branch_row.status = "deleted"
                branch_row.updated_at = now
                stats["branches_deleted"] += 1
                job = await _get_job(session, branch_row.job_id)
                if job:
                    job.status = "paused"
                    job.updated_at = now

    return stats


async def _ensure_monitoring_job(
    session,
    platform: str,
    repo: str,
    branch: str,
    job_id: str,
) -> Dict[str, int]:
    row = await _get_job(session, job_id)
    if row:
        row.source_type = platform
        row.platform = platform
        row.repo = repo
        row.branch = branch
        row.keywords = repo
        row.crawler_type = "commits"
        row.cron_expression = row.cron_expression or REPO_CRON_HOURLY
        row.save_option = "db"
        row.enable_comments = False
        if row.status == "deleted":
            row.status = "active"
        row.updated_at = datetime.utcnow()
        return {"created": 0, "updated": 1}

    session.add(
        MonitoringJob(
            job_id=job_id,
            source_type=platform,
            platform=platform,
            repo=repo,
            branch=branch,
            keywords=repo,
            crawler_type="commits",
            cron_expression=REPO_CRON_HOURLY,
            save_option="db",
            enable_comments=False,
            status="active",
        )
    )
    return {"created": 1, "updated": 0}


async def _get_job(session, job_id: str):
    result = await session.execute(
        select(MonitoringJob).where(MonitoringJob.job_id == job_id)
    )
    return result.scalar_one_or_none()
