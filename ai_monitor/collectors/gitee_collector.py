# -*- coding: utf-8 -*-
"""Fetch latest commit from Gitee Open API v5."""

from datetime import datetime, timezone
from typing import Optional, Tuple

import httpx

from ai_monitor.collectors.base import BranchInfo, CommitInfo, RepositoryInfo
from ai_monitor.collectors.github_collector import RepoStats
from ai_monitor.collectors.github_collector import parse_repo, _parse_iso_datetime
from ai_monitor.config.settings import get_settings


class GiteeCollector:
    API_BASE = "https://gitee.com/api/v5"

    def __init__(self, token: Optional[str] = None):
        settings = get_settings()
        self.token = token or settings.GITEE_TOKEN

    def _params(self, extra: Optional[dict] = None) -> dict:
        params = dict(extra or {})
        if self.token:
            params["access_token"] = self.token
        return params

    async def fetch_repo_info(self, repo: str) -> RepositoryInfo:
        owner, name = parse_repo(repo)
        url = f"{self.API_BASE}/repos/{owner}/{name}"
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=self._params())
            response.raise_for_status()
            data = response.json()
        return RepositoryInfo(
            platform="gitee",
            repo=repo,
            default_branch=data.get("default_branch") or "",
            html_url=data.get("html_url") or f"https://gitee.com/{repo}",
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
                    params=self._params({"per_page": 100, "page": page}),
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
        params = {"per_page": 1}
        ref = (branch or "").strip()
        if ref:
            params["sha"] = ref

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=self._params(params))
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

    async def fetch_repo_stats(self, repo):
        """Fetch expanded repository metadata from Gitee API."""
        owner, name = self._parse_gitee_repo(repo)
        url = self.API_BASE + "/repos/" + owner + "/" + name
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers())
            if response.status_code == 403:
                raise ValueError("Gitee API rate limit exceeded.")
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
            topics=[],
            default_branch=data.get("default_branch", ""),
            html_url=data.get("html_url", "https://gitee.com/" + repo),
            created_at=_parse_gitee_datetime(data.get("created_at")),
            updated_at=_parse_gitee_datetime(data.get("updated_at")),
            pushed_at=_parse_gitee_datetime(data.get("pushed_at")),
        )

    async def fetch_recent_commits(self, repo, branch="", count=20):
        """Fetch recent commits from Gitee API."""
        owner, name = self._parse_gitee_repo(repo)
        url = self.API_BASE + "/repos/" + owner + "/" + name + "/commits"
        params = {"per_page": min(count, 100)}
        ref = (branch or "").strip()
        if ref:
            params["sha"] = ref
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers(), params=params)
            if response.status_code == 403:
                raise ValueError("Gitee API rate limit exceeded.")
            response.raise_for_status()
            data = response.json()
        commits = []
        for item in (data if isinstance(data, list) else [data]):
            c = item.get("commit") or {}
            author_block = c.get("author") or {}
            git_author = item.get("author") or {}
            author = git_author.get("login") or author_block.get("name") or "unknown"
            date_str = author_block.get("date") or c.get("committer", {}).get("date")
            sha_val = item.get("sha", "")
            msg = (c.get("message") or "").split("\n")[0]
            commits.append(CommitInfo(sha=sha_val, author=author, committed_at=_parse_gitee_datetime(date_str), message=msg, url=item.get("html_url") or "", branch=ref or ""))
            if len(commits) >= count:
                break
        return commits

    async def fetch_readme(self, repo):
        """Fetch README content from Gitee API."""
        owner, name = self._parse_gitee_repo(repo)
        url = self.API_BASE + "/repos/" + owner + "/" + name + "/readme"
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self._headers())
            if response.status_code == 404:
                return ""
            response.raise_for_status()
            data = response.json()
            content = data.get("content", "")
            if content:
                import base64
                try:
                    return base64.b64decode(content).decode("utf-8")
                except Exception:
                    return content
            return ""

    def _parse_gitee_repo(self, repo):
        """Parse Gitee repo string to owner/name."""
        parts = repo.strip().strip("/").split("/")
        if len(parts) != 2 or not all(parts):
            raise ValueError("Invalid repo format (expected owner/name): " + repr(repo))
        return parts[0], parts[1]

    async def list_branches(self, repo):
        """List branches for a Gitee repository."""
        owner, name = self._parse_gitee_repo(repo)
        url = self.API_BASE + "/repos/" + owner + "/" + name + "/branches"
        branches = []
        page = 1
        import httpx
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                response = await client.get(url, headers=self._headers(), params={"per_page": 100, "page": page})
                response.raise_for_status()
                data = response.json()
                if not data:
                    break
                for item in data:
                    commit = item.get("commit") or {}
                    branches.append(BranchInfo(name=item.get("name") or "", sha=commit.get("sha") or "", protected=bool(item.get("protected"))))
                if len(data) < 100:
                    break
                page += 1
        return [b for b in branches if b.name]


