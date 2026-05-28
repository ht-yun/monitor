# -*- coding: utf-8 -*-
"""Fetch latest commit from Gitee Open API v5."""

from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx

from ai_monitor.collectors.base import CommitInfo
from ai_monitor.collectors.github_collector import parse_repo, _parse_iso_datetime
from ai_monitor.config.settings import get_settings


class GiteeCollector:
    API_BASE = "https://gitee.com/api/v5"

    def __init__(self, token: Optional[str] = None):
        settings = get_settings()
        self.token = token or settings.GITEE_TOKEN

    async def fetch_latest_commit(self, repo: str, branch: str = "") -> CommitInfo:
        owner, name = parse_repo(repo)
        url = f"{self.API_BASE}/repos/{owner}/{name}/commits"
        params = {"per_page": 1}
        ref = (branch or "").strip()
        if ref:
            params["sha"] = ref
        if self.token:
            params["access_token"] = self.token

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        if not data:
            raise ValueError(f"No commits found for repository: {repo}")

        item = data[0] if isinstance(data, list) else data
        commit = item.get("commit") or item
        author_info = item.get("author") or {}
        author_block = commit.get("author") if isinstance(commit, dict) else {}
        if not isinstance(author_block, dict):
            author_block = {}

        author = (
            author_info.get("login")
            or author_info.get("name")
            or author_block.get("name")
            or "unknown"
        )
        date_str = author_block.get("date") or item.get("created_at")
        committed_at = _parse_iso_datetime(date_str)
        sha = item.get("sha", "")
        message = ""
        if isinstance(commit, dict):
            message = (commit.get("message") or "").split("\n")[0]
        html_url = item.get("html_url") or f"https://gitee.com/{owner}/{name}/commit/{sha}"

        return CommitInfo(
            sha=sha,
            author=author,
            committed_at=committed_at,
            message=message,
            url=html_url,
            branch=ref,
        )
