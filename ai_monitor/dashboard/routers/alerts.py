# -*- coding: utf-8 -*-
from typing import List

from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from ai_monitor.dashboard.schemas.jobs import AlertResponse
from ai_monitor.store.database import get_session
from ai_monitor.store.models import Alert

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("", response_model=List[AlertResponse])
async def list_alerts(limit: int = 50, job_id: str = None, acknowledged: bool = None):
    async with get_session() as session:
        q = select(Alert).order_by(Alert.created_at.desc()).limit(limit)
        if job_id:
            q = q.where(Alert.job_id == job_id)
        if acknowledged is not None:
            q = q.where(Alert.acknowledged == acknowledged)
        result = await session.execute(q)
        rows = result.scalars().all()
    return [_to_response(a) for a in rows]


@router.post("/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int):
    async with get_session() as session:
        row = await session.get(Alert, alert_id)
        if not row:
            raise HTTPException(404, "Alert not found")
        row.acknowledged = True
    return {"acknowledged": alert_id}


def _to_response(a: Alert) -> AlertResponse:
    return AlertResponse(
        id=a.id,
        rule_id=a.rule_id,
        rule_name=a.rule_name,
        severity=a.severity or "warning",
        platform=a.platform,
        job_id=a.job_id,
        title=a.title,
        summary=a.summary,
        acknowledged=a.acknowledged,
        created_at=a.created_at.isoformat(),
    )
