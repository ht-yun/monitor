# -*- coding: utf-8 -*-
"""Parse owner/name or full GitHub/Gitee URLs into monitor job parameters."""

import re
from urllib.parse import unquote, urlparse

GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})
GITEE_HOSTS = frozenset({"gitee.com", "www.gitee.com"})


def _platform_from_host(host: str) -> str:
    host = (host or "").lower()
    if host in GITHUB_HOSTS:
        return "github"
    if host in GITEE_HOSTS:
        return "gitee"
    return ""


def parse_repo_target(
    raw: str,
    platform_hint: str = "",
    branch_hint: str = "",
) -> tuple[str, str, str]:
    """Parse input into (platform, owner/name, branch).

    Supports:
    - owner/name
    - https://github.com/owner/repo
    - https://github.com/owner/repo/tree/branch
    - https://github.com/owner/repo/blob/branch/path
    - git@github.com:owner/repo.git
    - gitee.com/owner/repo (with or without https)
    """
    text = (raw or "").strip()
    if not text:
        raise ValueError("仓库地址不能为空")

    branch = (branch_hint or "").strip()
    platform = (platform_hint or "").lower().strip()

    ssh = re.match(r"^git@([^:]+):(.+?)(?:\.git)?/?$", text)
    if ssh:
        host, path = ssh.group(1).lower(), ssh.group(2).strip("/")
        plat = _platform_from_host(host) or platform
        return _finalize(plat, path, branch)

    if "://" in text or re.match(r"^(www\.)?(github|gitee)\.com/", text, re.I):
        url = text if "://" in text else f"https://{text}"
        parsed = urlparse(url)
        plat = _platform_from_host(parsed.netloc) or platform
        segments = [unquote(p) for p in parsed.path.strip("/").split("/") if p]
        if len(segments) < 2:
            raise ValueError(f"无法从 URL 解析仓库: {text}")
        repo = f"{segments[0]}/{segments[1]}"
        if len(segments) >= 4 and segments[2] in ("tree", "blob"):
            branch = "/".join(segments[3:])
        return _finalize(plat, repo, branch)

    path = text.strip("/")
    if "/" in path:
        parts = path.split("/")
        if len(parts) == 2:
            return _finalize(platform, f"{parts[0]}/{parts[1]}", branch)
        if len(parts) >= 4 and parts[2] in ("tree", "blob"):
            branch = "/".join(parts[3:])
            return _finalize(platform, f"{parts[0]}/{parts[1]}", branch)
        if len(parts) >= 2:
            return _finalize(platform, f"{parts[0]}/{parts[1]}", branch)

    raise ValueError(
        "请填写 owner/name，或完整的 GitHub/Gitee 仓库链接"
        "（如 https://github.com/owner/repo/tree/branch）"
    )


def _finalize(platform: str, repo: str, branch: str) -> tuple[str, str, str]:
    platform = (platform or "").lower().strip()
    if platform not in ("github", "gitee"):
        raise ValueError("请指定平台为 github 或 gitee，或使用带 github.com / gitee.com 的完整 URL")
    repo = repo.strip().strip("/")
    if repo.count("/") != 1 or not all(repo.split("/")):
        raise ValueError(f"无效仓库名: {repo}，应为 owner/name")
    return platform, repo, (branch or "").strip()
