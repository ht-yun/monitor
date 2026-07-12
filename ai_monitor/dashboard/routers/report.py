# -*- coding: utf-8 -*-
"""API router for project report generation."""
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select

from ai_monitor.config.settings import get_settings
from ai_monitor.store.database import get_session
from ai_monitor.store.models import MonitoredRepository

router = APIRouter(prefix="/api/report", tags=["report"])

REPORTS_DIR = Path(__file__).resolve().parent.parent.parent / "generated_reports"


@router.post("/generate")
async def generate_project_report(
    repository_id: int = Query(..., description="MonitoredRepository ID"),
    branch: str = Query("", description="Branch name"),
    include_ai: bool = Query(True, description="Include AI analysis"),
):
    """Generate a project report for a monitored repository."""
    from ai_monitor.report_generator.generator import generate_report

    async with get_session() as session:
        repo = await session.get(MonitoredRepository, repository_id)
        if not repo:
            return {"status": "error", "message": f"Repository not found: {repository_id}"}
        platform = repo.platform
        repo_name = repo.repo

    settings = get_settings()
    token = settings.GITHUB_TOKEN if platform == "github" else settings.GITEE_TOKEN

    result = await generate_report(
        platform=platform,
        repo=repo_name,
        token=token,
        openai_api_key=settings.OPENAI_API_KEY if include_ai else None,
        openai_base=settings.OPENAI_API_BASE,
        openai_model=settings.OPENAI_MODEL,
    )

    return {
        "status": "ok",
        "filename": result["filename"],
        "file_path": result["file_path"],
        "repo": result["repo"],
        "html_content": result["html_content"],
        "generated_at": result["generated_at"],
        "has_ai": result["has_ai"],
        "lang_count": result["lang_count"],
    }


@router.get("/download/{filename}")
async def download_report(filename: str):
    """Download a generated report HTML file."""
    file_path = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {filename}"}
    content = open(file_path, "r", encoding="utf-8").read()
    return HTMLResponse(content=content, status_code=200)


@router.get("/files")
async def list_reports():
    """List all generated report files."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    files = []
    for f in sorted(os.listdir(REPORTS_DIR), reverse=True):
        if f.endswith(".html"):
            fp = os.path.join(REPORTS_DIR, f)
            stat = os.stat(fp)
            files.append({
                "filename": f,
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
    return {"files": files}


@router.delete("/files/{filename}")
async def delete_report(filename: str):
    """Delete a generated report file."""
    file_path = os.path.join(REPORTS_DIR, filename)
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {filename}"}
    abs_path = os.path.abspath(file_path)
    abs_dir = os.path.abspath(REPORTS_DIR)
    if not abs_path.startswith(abs_dir):
        return {"status": "error", "message": "Invalid file path"}
    os.remove(file_path)
    return {"status": "ok", "deleted": filename}
