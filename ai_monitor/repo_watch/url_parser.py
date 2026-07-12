# -*- coding: utf-8 -*-
"""Parse GitHub/Gitee repository links into monitor job parameters."""

import re
from urllib.parse import unquote, urlparse

GITHUB_HOSTS = frozenset({"github.com", "www.github.com"})
GITEE_HOSTS = frozenset({"gitee.com", "www.gitee.com"})

REPO_URL_RE = re.compile(
    r"(?:"
    r"https?://[^\s<>'\")]+(?:github|gitee)\.com/[^\s<>'\")]+"
    r"|git@(?:github|gitee)\.com:[^\s<>'\")]+"
    r"|(?:github|gitee)\.com/[^\s<>'\")]+"
    r")",
    re.I,
)


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

    Supports owner/name, GitHub/Gitee HTTP URLs, tree/blob URLs, and SSH URLs.
    """
    text = (raw or "").strip()
    if not text:
        raise ValueError("repository address cannot be empty")

    branch = (branch_hint or "").strip()
    platform = (platform_hint or "").lower().strip()

    ssh = re.match(r"^git@([^:]+):(.+?)/?$", text)
    if ssh:
        host = ssh.group(1).lower()
        path = ssh.group(2).strip("/")
        plat = _platform_from_host(host) or platform
        return _finalize(plat, _clean_repo_path(path), branch)

    if "://" in text or re.match(r"^(www\.)?(github|gitee)\.com/", text, re.I):
        url = text if "://" in text else f"https://{text}"
        parsed = urlparse(url)
        plat = _platform_from_host(parsed.netloc) or platform
        segments = [unquote(p) for p in parsed.path.strip("/").split("/") if p]
        if len(segments) < 2:
            raise ValueError(f"cannot parse repository URL: {text}")

        repo = _clean_repo_path(f"{segments[0]}/{segments[1]}")
        if len(segments) >= 4 and segments[2] in ("tree", "blob"):
            branch = "/".join(segments[3:])
        return _finalize(plat, repo, branch)

    path = text.strip("/")
    if "/" in path:
        parts = path.split("/")
        if len(parts) == 2:
            return _finalize(platform, _clean_repo_path(f"{parts[0]}/{parts[1]}"), branch)
        if len(parts) >= 4 and parts[2] in ("tree", "blob"):
            branch = "/".join(parts[3:])
            return _finalize(platform, _clean_repo_path(f"{parts[0]}/{parts[1]}"), branch)
        if len(parts) >= 2:
            return _finalize(platform, _clean_repo_path(f"{parts[0]}/{parts[1]}"), branch)

    raise ValueError("use owner/name or a full GitHub/Gitee repository URL")


def extract_repo_targets(text: str) -> list[tuple[str, str, str]]:
    """Extract de-duplicated GitHub/Gitee targets from arbitrary text."""
    targets = []
    seen = set()
    for match in REPO_URL_RE.finditer(text or ""):
        raw = match.group(0).rstrip(".,;:，。；：、")
        try:
            target = parse_repo_target(raw)
        except ValueError:
            continue
        key = (target[0], target[1], target[2])
        if key in seen:
            continue
        seen.add(key)
        targets.append(target)
    return targets


def _clean_repo_path(path: str) -> str:
    parts = (path or "").strip().strip("/").split("/")
    if len(parts) >= 2 and parts[1].endswith(".git"):
        parts[1] = parts[1][:-4]
    return "/".join(parts[:2])


def _finalize(platform: str, repo: str, branch: str) -> tuple[str, str, str]:
    platform = (platform or "").lower().strip()
    if platform not in ("github", "gitee"):
        raise ValueError("platform must be github or gitee")
    repo = repo.strip().strip("/")
    if repo.count("/") != 1 or not all(repo.split("/")):
        raise ValueError(f"invalid repository name: {repo}; expected owner/name")
    return platform, repo, (branch or "").strip()
