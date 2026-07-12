# -*- coding: utf-8 -*-
"""Fetch latest commit from GitHub REST API."""

from datetime import datetime, timezone
from typing import Optional, Tuple
from dataclasses import dataclass

import httpx

from ai_monitor.collectors.base import BranchInfo, CommitInfo, RepositoryInfo
from ai_monitor.config.settings import get_settings


def parse_repo(repo: str) -> Tuple[str, str]:
    parts = repo.strip().strip("/").split("/")
    if len(parts) != 2 or not all(parts):
        raise ValueError(f"Invalid repo format (expected owner/name): {repo!r}")
    return parts[0], parts[1]



@dataclass
class RepoStats:
    """Expanded repository metadata for PPT generation."""
    owner: str = ""
    name: str = ""
    description: str = ""
    language: str = ""
    stars: int = 0
    forks: int = 0
    open_issues: int = 0
    topics: list = None
    default_branch: str = ""
    html_url: str = ""
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    pushed_at: Optional[datetime] = None


class GitHubCollector:
    API_BASE = "https://api.github.com"

    def __init__(self, token: Optional[str] = None):
        settings = get_settings()
        self.token = token or settings.GITHUB_TOKEN

    def _headers(self) -> dict:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ai-monitor",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def fetch_repo_info(self, repo: str) -> RepositoryInfo:
        owner, name = parse_repo(repo)
        url = f"{self.API_BASE}/repos/{owner}/{name}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            data = response.json()
        return RepositoryInfo(
            platform="github",
            repo=repo,
            default_branch=data.get("default_branch") or "",
            html_url=data.get("html_url") or f"https://github.com/{repo}",
        )

    async def list_branches(self, repo: str) -> list[BranchInfo]:
        owner, name = parse_repo(repo)
        url = f"{self.API_BASE}/repos/{owner}/{name}/branches"
        branches: list[BranchInfo] = []
        page = 1
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                response = await client.get(
                    url,
                    headers=self._headers(),
                    params={"per_page": 100, "page": page},
                )
                response.raise_for_status()
                data = response.json()
                if not data:
                    break
                for item in data:
                    commit = item.get("commit") or {}
                    branches.append(
                        BranchInfo(
                            name=item.get("name") or "",
                            sha=commit.get("sha") or "",
                            protected=bool(item.get("protected")),
                        )
                    )
                if len(data) < 100:
                    break
                page += 1
        return [b for b in branches if b.name]

    async def fetch_latest_commit(self, repo: str, branch: str = "") -> CommitInfo:
        owner, name = parse_repo(repo)
        url = f"{self.API_BASE}/repos/{owner}/{name}/commits"
        headers = self._headers()

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



    async def fetch_repo_stats(self, repo):
        """Fetch expanded repository metadata from GitHub API."""
        owner, name = parse_repo(repo)
        url = self.API_BASE + "/repos/" + owner + "/" + name
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            data = response.json()
        return RepoStats(
            owner=data.get("owner", {}).get("login", owner),
            name=data.get("name", name),
            description=data.get("description") or "",
            language=data.get("language") or "",
            stars=data.get("stargazers_count", 0),
            forks=data.get("forks_count", 0),
            open_issues=data.get("open_issues_count", 0),
            topics=data.get("topics") or [],
            default_branch=data.get("default_branch", ""),
            html_url=data.get("html_url", "https://github.com/" + repo),
            created_at=_parse_iso_datetime(data.get("created_at")),
            updated_at=_parse_iso_datetime(data.get("updated_at")),
            pushed_at=_parse_iso_datetime(data.get("pushed_at")),
        )

    async def fetch_recent_commits(self, repo, branch="", count=20):
        """Fetch recent commits from GitHub API."""
        owner, name = parse_repo(repo)
        url = self.API_BASE + "/repos/" + owner + "/" + name + "/commits"
        params = {"per_page": min(count, 100)}
        ref = (branch or "").strip()
        if ref:
            params["sha"] = ref
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers(), params=params)
            if response.status_code == 403 and not self.token:
                raise ValueError("GitHub API rate limit exceeded.")
            response.raise_for_status()
            data = response.json()
        commits = []
        for item in (data if isinstance(data, list) else [data]):
            c = item.get("commit") or {}
            author_block = c.get("author") or {}
            gh_author = item.get("author") or {}
            author = gh_author.get("login") or author_block.get("name") or "unknown"
            date_str = author_block.get("date") or c.get("committer", {}).get("date")
            sha_val = item.get("sha", "")
            msg = (c.get("message") or "").split("\n")[0]
            html_url = item.get("html_url") or ""
            commits.append(CommitInfo(sha=sha_val, author=author, committed_at=_parse_iso_datetime(date_str), message=msg, url=html_url, branch=ref or ""))
            if len(commits) >= count:
                break
        return commits

    async def fetch_readme(self, repo):
        """Fetch README content from GitHub API."""
        owner, name = parse_repo(repo)
        url = self.API_BASE + "/repos/" + owner + "/" + name + "/readme"
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers={**self._headers(), "Accept": "application/vnd.github.raw"})
            if response.status_code == 404:
                return ""
            response.raise_for_status()
            return response.text

def _parse_iso_datetime(value: Optional[str]) -> datetime:
    if not value:
        return datetime.now(timezone.utc).replace(tzinfo=None)
    text = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt
