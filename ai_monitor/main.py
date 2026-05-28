# -*- coding: utf-8 -*-
"""FastAPI application entry point for AI Monitor."""

import sys
from pathlib import Path

# Ensure MediaCrawler is importable
MEDIACRAWLER_PATH = str(Path(__file__).resolve().parent.parent / "MediaCrawler")
if MEDIACRAWLER_PATH not in sys.path:
    sys.path.insert(0, MEDIACRAWLER_PATH)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from ai_monitor.config.settings import get_settings
from ai_monitor.store.database import init_db, close_db
from ai_monitor.dashboard.routers import alerts, analysis, jobs, rules, system


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    settings = get_settings()
    await init_db()
    from ai_monitor.config.notification_loader import sync_notifications_from_yaml

    try:
        await sync_notifications_from_yaml()
    except Exception:
        pass
    app.state.settings = settings
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title="AI Monitor",
    description="AI-powered social media monitoring platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(alerts.router)
app.include_router(rules.router)
app.include_router(analysis.router)
app.include_router(system.router)

STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "ai-monitor"}


@app.get("/api/config/platforms")
async def get_platforms():
    return {
        "platforms": [
            {"value": "xhs", "label": "小红书", "icon": "book-open"},
            {"value": "dy", "label": "抖音", "icon": "music"},
            {"value": "ks", "label": "快手", "icon": "video"},
            {"value": "bili", "label": "B站", "icon": "tv"},
            {"value": "wb", "label": "微博", "icon": "message-circle"},
            {"value": "tieba", "label": "百度贴吧", "icon": "messages-square"},
            {"value": "zhihu", "label": "知乎", "icon": "help-circle"},
            {"value": "github", "label": "GitHub", "icon": "github"},
            {"value": "gitee", "label": "Gitee", "icon": "git-branch"},
        ]
    }


@app.get("/api/repo-watch/jobs")
async def list_repo_watch_jobs():
    from sqlalchemy import select

    from ai_monitor.store.database import get_session
    from ai_monitor.store.models import MonitoringJob
    from ai_monitor.repo_watch.service import REPO_PLATFORMS

    async with get_session() as session:
        result = await session.execute(
            select(MonitoringJob).where(MonitoringJob.source_type.in_(REPO_PLATFORMS))
        )
        rows = result.scalars().all()

    return {
        "jobs": [
            {
                "job_id": r.job_id,
                "platform": r.platform,
                "repo": r.repo,
                "branch": r.branch or "",
                "status": r.status,
                "cron": r.cron_expression,
                "last_sha": r.last_sha,
                "last_commit_author": r.last_commit_author,
                "last_commit_at": r.last_commit_at.isoformat() if r.last_commit_at else None,
                "last_run_at": r.last_run_at.isoformat() if r.last_run_at else None,
            }
            for r in rows
        ]
    }


@app.get("/api/repo-watch/events")
async def list_repo_update_events(job_id: str = None, limit: int = 50):
    from sqlalchemy import select

    from ai_monitor.store.database import get_session
    from ai_monitor.store.models import RepoUpdateEvent

    async with get_session() as session:
        q = select(RepoUpdateEvent).order_by(RepoUpdateEvent.detected_at.desc()).limit(limit)
        if job_id:
            q = q.where(RepoUpdateEvent.job_id == job_id)
        result = await session.execute(q)
        rows = result.scalars().all()

    return {
        "events": [
            {
                "job_id": e.job_id,
                "platform": e.platform,
                "repo": e.repo,
                "branch": getattr(e, "branch", None) or "",
                "commit_sha": e.commit_sha,
                "commit_author": e.commit_author,
                "committed_at": e.committed_at.isoformat(),
                "commit_message": e.commit_message,
                "commit_url": e.commit_url,
                "detected_at": e.detected_at.isoformat(),
            }
            for e in rows
        ]
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8081)
