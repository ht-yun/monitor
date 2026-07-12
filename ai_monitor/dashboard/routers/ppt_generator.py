# -*- coding: utf-8 -*-
"""API router for generating PPT prompts from monitored repositories."""

import os
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select

from ai_monitor.config.settings import get_settings
from ai_monitor.store.database import get_session
from ai_monitor.store.models import MonitoredBranch, MonitoredRepository, MonitoringJob
from ai_monitor.ppt_generator.generator import generate_ppt_prompt, OUTPUT_DIR
from ai_monitor.ppt_generator.visual_styles import CYBERPPT_STYLES, SLIDE_ELEMENTS

logger = logging.getLogger("ai_monitor")

router = APIRouter(prefix="/api/ppt-generator", tags=["ppt-generator"])


@router.get("/styles")
async def get_ppt_styles():
    """Get available CyberPPT visual styles and slide elements."""
    return {
        "styles": CYBERPPT_STYLES,
        "elements": SLIDE_ELEMENTS,
    }


@router.get("/repositories")
async def list_repos_for_ppt():
    """List monitored repositories available for PPT generation."""
    async with get_session() as session:
        result = await session.execute(
            select(MonitoredRepository).order_by(MonitoredRepository.platform, MonitoredRepository.repo)
        )
        repos = list(result.scalars().all())
        branch_result = await session.execute(select(MonitoredBranch))
        branches = list(branch_result.scalars().all())

    by_repo = {}
    for branch in branches:
        by_repo.setdefault(branch.repository_id, []).append({
            "id": branch.id,
            "branch": branch.branch,
            "is_default": branch.is_default,
            "job_id": branch.job_id,
            "last_sha": branch.last_sha,
            "last_commit_author": branch.last_commit_author,
            "last_commit_at": branch.last_commit_at.isoformat() if branch.last_commit_at else None,
            "status": branch.status,
        })
    
    # If MonitoredBranch is empty, fall back to MonitoringJob
    if not branches:
        job_result = await session.execute(
            select(MonitoringJob).where(
                MonitoringJob.source_type.in_(["github", "gitee"])
            )
        )
        from ai_monitor.repo_watch.helpers import make_repo_job_id
        for j in job_result.scalars().all():
            if j.repo and j.repo in [r.repo for r in repos]:
                repo_obj = [r for r in repos if r.repo == j.repo][0]
                br = j.branch or repo_obj.default_branch or "main"
                by_repo.setdefault(repo_obj.id, []).append({
                    "id": 0,
                    "branch": br,
                    "is_default": True,
                    "job_id": j.job_id or "",
                    "last_sha": j.last_sha,
                    "last_commit_author": j.last_commit_author,
                    "last_commit_at": j.last_commit_at.isoformat() if j.last_commit_at else None,
                    "status": "active",
                })

    return [
        {
            "id": r.id,
            "platform": r.platform,
            "owner": r.owner,
            "name": r.name,
            "repo": r.repo,
            "repo_url": r.repo_url,
            "default_branch": r.default_branch,
            "status": r.status,
            "active_branch_count": sum(1 for b in by_repo.get(r.id, []) if b["status"] == "active"),
            "branches": by_repo.get(r.id, []),
        }
        for r in repos
    ]


@router.post("/generate")
async def generate_ppt(
    repository_id: int = Query(..., description="MonitoredRepository ID"),
    branch: str = Query("", description="Branch name (empty = all branches / default)"),
    commit_count: int = Query(20, description="Number of recent commits to fetch"),
    style_id: int = Query(4, description="CyberPPT visual style ID (1-8)"),
    elements: str = Query("", description="Comma-separated slide element IDs"),
    charts: str = Query("line,bar,table,timeline", description="Comma-separated chart type IDs"),
):
    """Generate a PPT prompt file for a monitored repository."""
    branch_list = []
    platform = ""
    repo_name = ""

    async with get_session() as session:
        repo = await session.get(MonitoredRepository, repository_id)
        if not repo:
            raise HTTPException(404, f"Repository not found: {repository_id}")

        platform = repo.platform
        repo_name = repo.repo

        # Try MonitoredBranch first
        branch_result = await session.execute(
            select(MonitoredBranch).where(MonitoredBranch.repository_id == repository_id)
        )
        repo_branches = list(branch_result.scalars().all())

        if repo_branches:
            # Filter branches based on user selection
            for b in repo_branches:
                bd = {
                    "branch": b.branch,
                    "is_default": b.is_default,
                    "last_sha": b.last_sha,
                    "last_commit_author": b.last_commit_author,
                    "last_commit_at": b.last_commit_at,
                }
                if branch and b.branch == branch:
                    branch_list = [bd]
                    break
                elif not branch:
                    branch_list.append(bd)
        else:
            # Fallback: construct branch data from MonitoringJob table
            job_result = await session.execute(
                select(MonitoringJob).where(
                    MonitoringJob.source_type == platform,
                    MonitoringJob.repo == repo_name,
                )
            )
            repo_jobs = list(job_result.scalars().all())

            # Build unique branch entries from jobs
            seen_branches = set()
            for j in repo_jobs:
                br = j.branch or repo.default_branch or ""
                if not br or br in seen_branches:
                    continue
                seen_branches.add(br)
                bd = {
                    "branch": br,
                    "is_default": (br == (repo.default_branch or "")),
                    "last_sha": j.last_sha,
                    "last_commit_author": j.last_commit_author,
                    "last_commit_at": j.last_commit_at,
                }
                if branch and br == branch:
                    branch_list = [bd]
                    break
                elif not branch:
                    branch_list.append(bd)

            # If still empty, create a placeholder for default branch
            if not branch_list:
                branch_list = [{
                    "branch": repo.default_branch or "main",
                    "is_default": True,
                    "last_sha": None,
                    "last_commit_author": None,
                    "last_commit_at": None,
                }]

    try:
        # Parse elements and charts
        elem_list = [e.strip() for e in elements.split(",") if e.strip()] if elements else None
        chart_list = [c.strip() for c in charts.split(",") if c.strip()] if charts else None

        result = await generate_ppt_prompt(
            platform=platform,
            repo=repo_name,
            branches_data=branch_list,
            commit_count=commit_count,
            style_id=style_id,
            selected_elements=elem_list,
            selected_charts=chart_list,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("PPT generation failed for %s/%s", platform, repo_name)
        raise HTTPException(500, f"PPT generation failed: {e}")

    return {
        "status": "ok",
        "filename": result["filename"],
        "file_path": result["file_path"],
        "repo": f"{platform}/{repo_name}",
        "commits_fetched": result["commits_count"],
        "branches_included": len(branch_list),
        "generated_at": result["generated_at"],
        "style": result.get("style", ""),
        "elements_count": result.get("elements_count", 0),
    }


@router.get("/download/{filename}")
async def download_ppt_prompt(filename: str):
    """Download a generated PPT prompt file."""
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, f"File not found: {filename}")
    return FileResponse(
        file_path,
        media_type="text/markdown; charset=utf-8",
        filename=filename,
    )


@router.get("/files")
async def list_generated_files():
    """List all generated PPT prompt files."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    files = []
    for f in sorted(os.listdir(OUTPUT_DIR), reverse=True):
        if f.endswith(".md"):
            fp = os.path.join(OUTPUT_DIR, f)
            stat = os.stat(fp)
            files.append({
                "filename": f,
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            })
    return {"files": files}


from datetime import datetime, timezone
import json


@router.delete("/files/{filename}")
async def delete_ppt_file(filename: str):
    """Delete a generated PPT prompt file."""
    file_path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(404, detail=f"File not found: {filename}")
    # Security: ensure the filename doesn't escape the generated_ppts directory
    abs_path = os.path.abspath(file_path)
    abs_dir = os.path.abspath(OUTPUT_DIR)
    if not abs_path.startswith(abs_dir):
        raise HTTPException(400, detail="Invalid file path")
    os.remove(file_path)
    return {"status": "ok", "deleted": filename}


@router.post("/generate-all")
async def generate_all_ppts(
    style_id: int = Query(4, description="CyberPPT visual style ID (1-8)"),
    commit_count: int = Query(10, description="Number of recent commits to fetch per repo"),
):
    """Generate PPT prompts for ALL monitored repositories."""
    from ai_monitor.ppt_generator.generator import generate_ppt_prompt

    async with get_session() as session:
        repos = await session.execute(
            select(MonitoredRepository).where(MonitoredRepository.status == "active")
        )
        active_repos = list(repos.scalars().all())

    results = []
    for repo in active_repos:
        # Build branch data for this repo
        branch_list = []
        async with get_session() as session:
            branch_result = await session.execute(
                select(MonitoredBranch).where(MonitoredBranch.repository_id == repo.id)
            )
            repo_branches = list(branch_result.scalars().all())
            if repo_branches:
                for b in repo_branches:
                    branch_list.append({
                        "branch": b.branch,
                        "is_default": b.is_default,
                        "last_sha": b.last_sha,
                        "last_commit_author": b.last_commit_author,
                        "last_commit_at": b.last_commit_at,
                    })
            else:
                # Fallback to MonitoringJob
                job_result = await session.execute(
                    select(MonitoringJob).where(
                        MonitoringJob.source_type == repo.platform,
                        MonitoringJob.repo == repo.repo,
                    )
                )
                seen = set()
                for j in job_result.scalars().all():
                    br = j.branch or repo.default_branch or "main"
                    if br in seen:
                        continue
                    seen.add(br)
                    branch_list.append({
                        "branch": br,
                        "is_default": (br == (repo.default_branch or "")),
                        "last_sha": j.last_sha,
                        "last_commit_author": j.last_commit_author,
                        "last_commit_at": j.last_commit_at,
                    })

        try:
            result = await generate_ppt_prompt(
                platform=repo.platform,
                repo=repo.repo,
                branches_data=branch_list,
                commit_count=commit_count,
                style_id=style_id,
            )
            results.append({
                "repo": f"{repo.platform}/{repo.repo}",
                "filename": result["filename"],
                "status": "ok",
                "commits": result["commits_count"],
                "style": result.get("style", ""),
            })
        except Exception as e:
            logger.exception("Batch generation failed for %s/%s", repo.platform, repo.repo)
            results.append({
                "repo": f"{repo.platform}/{repo.repo}",
                "status": "error",
                "error": str(e),
            })

    return {
        "status": "ok",
        "total": len(active_repos),
        "succeeded": sum(1 for r in results if r["status"] == "ok"),
        "failed": sum(1 for r in results if r["status"] == "error"),
        "results": results,
    }
