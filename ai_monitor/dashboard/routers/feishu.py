# -*- coding: utf-8 -*-
from fastapi import APIRouter, HTTPException

from ai_monitor.config.settings import get_settings
from ai_monitor.feishu.sync import sync_repositories_from_feishu

router = APIRouter(prefix="/api/feishu", tags=["feishu"])


@router.get("/status")
async def feishu_status():
    settings = get_settings()
    return {
        "app_configured": bool(settings.FEISHU_APP_ID and settings.FEISHU_APP_SECRET),
        "repo_doc_configured": bool(settings.FEISHU_REPO_DOC_TOKEN),
        "sync_interval_seconds": settings.FEISHU_SYNC_INTERVAL_SECONDS,
        "branch_sync_interval_seconds": settings.REPO_BRANCH_SYNC_INTERVAL_SECONDS,
    }


@router.post("/sync")
async def feishu_sync(reconcile: bool = True):
    settings = get_settings()
    if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET or not settings.FEISHU_REPO_DOC_TOKEN:
        raise HTTPException(
            status_code=400,
            detail="Feishu app credentials or repository document token are not configured."
        )
    return await sync_repositories_from_feishu(run_reconcile=reconcile)
