# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter
from sqlalchemy import select, func

from ai_monitor.dashboard.schemas.jobs import AnalysisResponse, DashboardStats
from ai_monitor.store.database import get_session
from ai_monitor.store.models import Alert, AnalysisResult, MonitoringJob

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/analysis", response_model=List[AnalysisResponse])
async def list_analysis(limit: int = 50, job_id: str = None, platform: str = None):
    async with get_session() as session:
        q = select(AnalysisResult).order_by(AnalysisResult.analyzed_at.desc()).limit(limit)
        if job_id:
            q = q.where(AnalysisResult.job_id == job_id)
        if platform:
            q = q.where(AnalysisResult.platform == platform)
        result = await session.execute(q)
        rows = result.scalars().all()
    return [
        AnalysisResponse(
            id=r.id,
            content_id=r.content_id,
            platform=r.platform,
            job_id=r.job_id,
            sentiment=r.sentiment,
            sentiment_score=r.sentiment_score,
            topics=r.topics,
            summary=r.summary,
            analyzed_at=r.analyzed_at.isoformat(),
        )
        for r in rows
    ]


@router.get("/dashboard/stats", response_model=DashboardStats)
async def dashboard_stats():
    since = datetime.utcnow() - timedelta(days=1)
    async with get_session() as session:
        jobs = await session.execute(
            select(MonitoringJob).where(MonitoringJob.status == "active")
        )
        job_rows = jobs.scalars().all()
        alert_count = await session.scalar(select(func.count(Alert.id)))
        unack = await session.scalar(
            select(func.count(Alert.id)).where(Alert.acknowledged == False)
        )
        analysis_today = await session.scalar(
            select(func.count(AnalysisResult.id)).where(AnalysisResult.analyzed_at >= since)
        )
    return DashboardStats(
        active_jobs=len(job_rows),
        total_alerts=alert_count or 0,
        unack_alerts=unack or 0,
        analysis_today=analysis_today or 0,
        platforms=sorted({j.platform for j in job_rows}),
    )
