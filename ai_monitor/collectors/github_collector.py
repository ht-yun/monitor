# -*- coding: utf-8 -*-
"""Fetch latest commit from GitHub REST API."""

from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx

from ai_monitor.collectors.base import CommitInfo
from ai_monitor.config.settings import get_settings


def parse_repo(repo: str) -> Tuple[str, str]:
    parts = repo.strip().strip("/").split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"Invalid repo format (expected owner/name): {repo!r}")
    return parts[0], parts[1]


class GitHubCollector:
    API_BASE = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        settings = get_settings()
        self.token = token or settings.GITHUB_TOKEN

    async def fetch_latest_commit(self, repo: str, branch: str = "") -> CommitInfo:
        owner, name = parse_repo(repo)
        url = f"{self.API_BASE}/repos/{owner}/{name}/commits"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-monitor",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        params = {"per_page": 1}
        ref = (branch or "").strip()
        if ref:
            params["sha"] = ref

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=headers, params=params)
            if response.status_code == 403 and not self.token:
                raise ValueError(
                    "GitHub API rate limit exceeded. Set AIMONITOR_GITHUB_TOKEN in .env "
                    "(see https://github.com/settings/tokens)."
                ) from None
            if response.status_code == 409:
                try:
                    msg = response.json().get("message", "")
                except Exception:
                    msg = ""
                if "empty" in msg.lower():
                    raise ValueError(
                        f"仓库 {repo} 尚无提交（空仓库）。首次 push 后将自动检测新提交。"
                    ) from None
            response.raise_for_status()
            data = response.json()

        if not data:
            raise ValueError(f"No commits found for repository: {repo}")

        item = data[0] if isinstance(data, list) else data
        commit = item.get("commit") or {}
        author_block = commit.get("author") or {}
        committer_block = commit.get("committer") or {}
        gh_author = item.get("author") or {}

        author = (
            gh_author.get("login")
            or author_block.get("name")
            or committer_block.get("name")
            or "unknown"
        )
        date_str = (
            author_block.get("date")
            or committer_block.get("date")
            or item.get("committer", {}).get("date")
        )
        committed_at = _parse_iso_datetime(date_str)
        sha = item.get("sha", "")
        message = (commit.get("message") or "").split("\n")[0]
        html_url = item.get("html_url") or f"https://github.com/{owner}/{name}/commit/{sha}"

        return CommitInfo(
            sha=sha,
            author=author,
            committed_at=committed_at,
            message=message,
            url=html_url,
            branch=ref,
        )


def _parse_iso_datetime(value: Optional[str]) -> datetime:
    if not value:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
