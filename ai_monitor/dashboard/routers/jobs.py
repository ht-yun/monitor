# -*- coding: utf-8 -*-
from datetime import datetime
from typing import List
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from sqlalchemy import func, select

from ai_monitor.dashboard.schemas.jobs import JobCreateRequest, JobResponse, JobUpdateRequest
from ai_monitor.scheduler.base import JobConfig
from ai_monitor.scheduler.jobs import MonitoringJob as JobRunner
from ai_monitor.store.database import get_session
from ai_monitor.store.models import AnalysisResult, MonitoringJob
from ai_monitor.repo_watch.helpers import job_config_from_record, resolve_repo_job
from ai_monitor.repo_watch.url_parser import parse_repo_target
from ai_monitor.repo_watch.service import REPO_PLATFORMS

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("", response_model=List[JobResponse])
async def list_jobs(source_type: str = None):
    async with get_session() as session:
        q = select(MonitoringJob).order_by(MonitoringJob.created_at.desc())
        if source_type:
            q = q.where(MonitoringJob.source_type == source_type)
        result = await session.execute(q)
        rows = list(result.scalars().all())

        social_ids = [r.job_id for r in rows if (r.source_type or "social") == "social"]
        analysis_map = {}
        if social_ids:
            agg = await session.execute(
                select(
                    AnalysisResult.job_id,
                    func.max(AnalysisResult.analyzed_at),
                )
                .where(AnalysisResult.job_id.in_(social_ids))
                .group_by(AnalysisResult.job_id)
            )
            analysis_map = {jid: ts for jid, ts in agg.all() if ts}

    return [_to_response(r, analysis_map.get(r.job_id)) for r in rows]


@router.post("", response_model=JobResponse)
async def create_job(body: JobCreateRequest):
    source = body.source_type or "social"
    platform = body.platform.lower().strip()

    if source in REPO_PLATFORMS:
        raw = (body.repo or body.keywords or "").strip()
        if not raw:
            raise HTTPException(400, "repo or URL required")
        try:
            platform, repo, branch, job_id = resolve_repo_job(
                raw,
                platform_hint=platform if platform in REPO_PLATFORMS else "",
                branch_hint=body.branch or "",
            )
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        cron = body.cron_expression or "0 * * * *"
        async with get_session() as session:
            existing = await session.execute(
                select(MonitoringJob).where(MonitoringJob.job_id == job_id)
            )
            if existing.scalar_one_or_none():
                raise HTTPException(409, f"Job already exists: {job_id}")
            session.add(
                MonitoringJob(
                    job_id=job_id,
                    source_type=platform,
                    platform=platform,
                    repo=repo,
                    branch=branch or None,
                    keywords=repo,
                    crawler_type="commits",
                    cron_expression=cron,
                    save_option="db",
                    enable_comments=False,
                    status="active",
                )
            )
            result = await session.execute(
                select(MonitoringJob).where(MonitoringJob.job_id == job_id)
            )
            row = result.scalar_one()
        return _to_response(row, None)

    if not (body.keywords or "").strip():
        raise HTTPException(400, "keywords required for social jobs")
    job_id = f"{platform}_search_{uuid4().hex[:8]}"
    cron = body.cron_expression or "0 */2 * * *"
    async with get_session() as session:
        session.add(
            MonitoringJob(
                job_id=job_id,
                source_type="social",
                platform=platform,
                keywords=body.keywords.strip(),
                crawler_type=body.crawler_type,
                cron_expression=cron,
                save_option="jsonl",
                enable_comments=body.enable_comments,
                max_notes=body.max_notes,
                rule_set_ids=body.rule_set_ids or ["brand_monitoring"],
                status="active",
            )
        )
        result = await session.execute(
            select(MonitoringJob).where(MonitoringJob.job_id == job_id)
        )
        row = result.scalar_one()
    return _to_response(row, None)


@router.patch("/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, body: JobUpdateRequest):
    async with get_session() as session:
        result = await session.execute(
            select(MonitoringJob).where(MonitoringJob.job_id == job_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            raise HTTPException(404, "Job not found")
        if body.keywords is not None:
            record.keywords = body.keywords
        if body.cron_expression is not None:
            record.cron_expression = body.cron_expression
        if body.status is not None:
            record.status = body.status
        if body.max_notes is not None:
            record.max_notes = body.max_notes
        if body.enable_comments is not None:
            record.enable_comments = body.enable_comments
        if body.rule_set_ids is not None:
            record.rule_set_ids = body.rule_set_ids
        if body.branch is not None and (record.source_type in REPO_PLATFORMS):
            new_branch = body.branch.strip()
            old_branch = (record.branch or "").strip()
            if new_branch != old_branch:
                record.branch = new_branch or None
                record.last_sha = None
        record.updated_at = datetime.utcnow()
    return _to_response(record, None)


@router.post("/{job_id}/run")
async def run_job(job_id: str):
    async with get_session() as session:
        result = await session.execute(
            select(MonitoringJob).where(MonitoringJob.job_id == job_id)
        )
        record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "Job not found")

    config = job_config_from_record(record)
    run = await JobRunner(config).execute()
    return {
        "job_id": job_id,
        "source_type": config.source_type,
        "branch": config.branch or None,
        "status": run.status,
        "items_crawled": run.items_crawled,
        "items_analyzed": run.items_analyzed,
        "alerts_triggered": run.alerts_triggered,
        "repo_updated": run.repo_updated,
        "commit_sha": run.commit_sha,
        "commit_author": run.commit_author,
        "commit_at": run.commit_at.isoformat() if run.commit_at else None,
        "commit_message": run.commit_message,
        "error_message": run.error_message,
    }


@router.post("/run-batch")
async def run_jobs_batch(source_type: str = "all"):
    """Manually run all active jobs (all | social | github | gitee)."""
    async with get_session() as session:
        q = select(MonitoringJob).where(MonitoringJob.status == "active")
        if source_type == "social":
            q = q.where(MonitoringJob.source_type == "social")
        elif source_type == "repo":
            q = q.where(MonitoringJob.source_type.in_(REPO_PLATFORMS))
        elif source_type in REPO_PLATFORMS:
            q = q.where(MonitoringJob.source_type == source_type)
        elif source_type != "all":
            raise HTTPException(400, "source_type must be all, social, repo, github, or gitee")
        result = await session.execute(q)
        rows = list(result.scalars().all())

    results = []
    for record in rows:
        config = job_config_from_record(record)
        run = await JobRunner(config).execute()
        results.append({
            "job_id": record.job_id,
            "status": run.status,
            "repo_updated": run.repo_updated,
            "items_crawled": run.items_crawled,
            "alerts_triggered": run.alerts_triggered,
            "error_message": run.error_message,
        })
    return {"ran": len(results), "results": results}


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    async with get_session() as session:
        result = await session.execute(
            select(MonitoringJob).where(MonitoringJob.job_id == job_id)
        )
        record = result.scalar_one_or_none()
        if not record:
            raise HTTPException(404, "Job not found")
        await session.delete(record)
    return {"deleted": job_id}


def _to_response(r: MonitoringJob, latest_analysis_at=None) -> JobResponse:
    is_repo = (r.source_type or "social") in REPO_PLATFORMS
    latest_update_at = None
    latest_update_label = None

    if is_repo and r.last_commit_at:
        latest_update_at = r.last_commit_at.isoformat()
        latest_update_label = "代码提交"
    elif not is_repo and latest_analysis_at:
        latest_update_at = latest_analysis_at.isoformat()
        latest_update_label = "舆情分析"

    return JobResponse(
        job_id=r.job_id,
        source_type=r.source_type or "social",
        platform=r.platform,
        repo=r.repo,
        branch=(r.branch or "") or None,
        keywords=r.keywords or "",
        cron_expression=r.cron_expression,
        status=r.status,
        last_run_at=r.last_run_at.isoformat() if r.last_run_at else None,
        last_run_status=r.last_run_status,
        last_sha=r.last_sha,
        last_commit_at=r.last_commit_at.isoformat() if r.last_commit_at else None,
        last_commit_author=r.last_commit_author,
        latest_update_at=latest_update_at,
        latest_update_label=latest_update_label,
        rule_set_ids=list(r.rule_set_ids or []),
    )
