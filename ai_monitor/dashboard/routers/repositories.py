# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ai_monitor.repo_watch.reconciler import reconcile_repositories
from ai_monitor.store.database import get_session
from ai_monitor.store.models import MonitoredBranch, MonitoredRepository, MonitoringJob

router = APIRouter(prefix="/api/repositories", tags=["repositories"])


@router.get("")
async def list_repositories():
    async with get_session() as session:
        result = await session.execute(
            select(MonitoredRepository).order_by(MonitoredRepository.platform, MonitoredRepository.repo)
        )
        repos = list(result.scalars().all())
        branch_result = await session.execute(select(MonitoredBranch))
        branches = list(branch_result.scalars().all())

    by_repo = {}
    for branch in branches:
        by_repo.setdefault(branch.repository_id, []).append(branch)

    return [
        _repo_response(row, by_repo.get(row.id, []))
        for row in repos
    ]


@router.get("/{repository_id}/branches")
async def list_repository_branches(repository_id: int):
    async with get_session() as session:
        repo = await session.get(MonitoredRepository, repository_id)
        if not repo:
            raise HTTPException(404, "Repository not found")
        result = await session.execute(
            select(MonitoredBranch)
            .where(MonitoredBranch.repository_id == repository_id)
            .order_by(MonitoredBranch.is_default.desc(), MonitoredBranch.branch)
        )
        branches = list(result.scalars().all())
    return {"repository": _repo_response(repo, branches), "branches": [_branch_response(b) for b in branches]}


@router.post("/reconcile")
async def reconcile_all_repositories():
    return await reconcile_repositories()


@router.post("/{repository_id}/reconcile")
async def reconcile_one_repository(repository_id: int):
    return await reconcile_repositories(repository_id)


@router.patch("/{repository_id}")
async def update_repository_status(repository_id: int, status: str):
    if status not in ("active", "paused"):
        raise HTTPException(400, "status must be active or paused")
    async with get_session() as session:
        repo = await session.get(MonitoredRepository, repository_id)
        if not repo:
            raise HTTPException(404, "Repository not found")
        repo.status = status
        branch_result = await session.execute(
            select(MonitoredBranch).where(MonitoredBranch.repository_id == repository_id)
        )
        for branch in branch_result.scalars().all():
            branch.status = status
            job = await _get_job(session, branch.job_id)
            if job:
                job.status = "active" if status == "active" else "paused"
    return {"repository_id": repository_id, "status": status}


@router.patch("/{repository_id}/branches/{branch_name:path}")
async def update_branch_status(repository_id: int, branch_name: str, status: str):
    if status not in ("active", "paused"):
        raise HTTPException(400, "status must be active or paused")
    async with get_session() as session:
        result = await session.execute(
            select(MonitoredBranch).where(
                MonitoredBranch.repository_id == repository_id,
                MonitoredBranch.branch == branch_name,
            )
        )
        branch = result.scalar_one_or_none()
        if not branch:
            raise HTTPException(404, "Branch not found")
        branch.status = status
        job = await _get_job(session, branch.job_id)
        if job:
            job.status = "active" if status == "active" else "paused"
    return {"repository_id": repository_id, "branch": branch_name, "status": status}


async def _get_job(session, job_id: str):
    result = await session.execute(select(MonitoringJob).where(MonitoringJob.job_id == job_id))
    return result.scalar_one_or_none()


def _repo_response(row: MonitoredRepository, branches: list[MonitoredBranch]) -> dict:
    return {
        "id": row.id,
        "platform": row.platform,
        "owner": row.owner,
        "name": row.name,
        "repo": row.repo,
        "repo_url": row.repo_url,
        "default_branch": row.default_branch,
        "source": row.source,
        "status": row.status,
        "error_message": row.error_message,
        "first_seen_at": row.first_seen_at.isoformat() if row.first_seen_at else None,
        "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
        "last_branch_sync_at": row.last_branch_sync_at.isoformat() if row.last_branch_sync_at else None,
        "branch_count": len(branches),
        "active_branch_count": sum(1 for b in branches if b.status == "active"),
        "branches": [_branch_response(b) for b in sorted(branches, key=lambda x: (not x.is_default, x.branch))],
    }


def _branch_response(row: MonitoredBranch) -> dict:
    return {
        "id": row.id,
        "branch": row.branch,
        "is_default": row.is_default,
        "job_id": row.job_id,
        "last_sha": row.last_sha,
        "last_commit_author": row.last_commit_author,
        "last_commit_at": row.last_commit_at.isoformat() if row.last_commit_at else None,
        "status": row.status,
        "first_seen_at": row.first_seen_at.isoformat() if row.first_seen_at else None,
        "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
    }
