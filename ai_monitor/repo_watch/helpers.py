# -*- coding: utf-8 -*-
"""Repository watch job ID and config helpers."""

import hashlib
import re

from ai_monitor.scheduler.base import JobConfig
from ai_monitor.repo_watch.url_parser import parse_repo_target


def resolve_repo_job(
    raw: str,
    platform_hint: str = "",
    branch_hint: str = "",
) -> tuple[str, str, str, str]:
    """Return (platform, repo, branch, job_id) from URL or owner/name."""
    platform, repo, branch = parse_repo_target(raw, platform_hint, branch_hint)
    job_id = make_repo_job_id(platform, repo, branch)
    return platform, repo, branch, job_id


def make_repo_job_id(platform: str, repo: str, branch: str = "") -> str:
    """Build stable job_id; branch suffix allows same repo on multiple branches."""
    repo = repo.strip().strip("/")
    base = f"{platform.lower()}_{repo.replace('/', '_')}"
    branch = (branch or "").strip()
    if branch:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", branch).strip("_") or "branch"
        digest = hashlib.sha1(f"{platform}:{repo}:{branch}".encode("utf-8")).hexdigest()[:8]
        return f"{base}__{safe}__{digest}"
    return base


def branch_label(branch: str) -> str:
    return branch.strip() if branch and branch.strip() else "默认分支"


def job_config_from_record(record) -> JobConfig:
    """Build JobConfig from a MonitoringJob ORM row."""
    return JobConfig(
        job_id=record.job_id,
        source_type=record.source_type or "social",
        platform=record.platform,
        repo=record.repo or "",
        branch=getattr(record, "branch", None) or "",
        keywords=record.keywords or "",
        crawler_type=record.crawler_type,
        cron_expression=record.cron_expression,
        save_option=record.save_option or "jsonl",
        enable_comments=record.enable_comments,
        max_notes=record.max_notes or 20,
        start_page=record.start_page or 1,
        rule_set_ids=record.rule_set_ids or [],
    )
