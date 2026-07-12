# -*- coding: utf-8 -*-
"""Generate structured PPT prompt files from monitored repository data."""

import base64
import io
import logging
import os
from PIL import Image
from datetime import datetime, timezone, timedelta

from ai_monitor.collectors.github_collector import GitHubCollector, RepoStats
from ai_monitor.collectors.gitee_collector import GiteeCollector
from ai_monitor.config.settings import get_settings
from ai_monitor.ppt_generator.prompt_templates import (
    PPT_PROMPT_TEMPLATE,
    STYLE_PROMPT_SECTION,
    ELEMENTS_PROMPT_SECTION,
    SINGLE_BRANCH_TEMPLATE,
    COMMIT_HISTORY_ROW,
)
from ai_monitor.ppt_generator.visual_styles import CYBERPPT_STYLES, SLIDE_ELEMENTS, TYPOGRAPHY_SCALE

logger = logging.getLogger("ai_monitor")

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "generated_ppts")


def _get_collector(platform: str):
    """Return the appropriate collector for the platform."""
    if platform == "github":
        return GitHubCollector()
    elif platform == "gitee":
        return GiteeCollector()
    else:
        raise ValueError(f"Unsupported platform: {platform}")


def _fmt(val):
    """Format a value for display."""
    if val is None:
        return "-"
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d %H:%M UTC")
    return str(val)


async def generate_ppt_prompt(
    platform: str,
    repo: str,
    branches_data: list = None,
    commit_count: int = 20,
    style_id: int = 1,
    selected_elements: list = None,
    selected_charts: list = None,
) -> dict:
    """
    Gather repository data and generate a structured PPT prompt file.

    Args:
        platform: "github" or "gitee"
        repo: Repository in "owner/name" format
        branches_data: Optional list of branch dicts from DB (to avoid extra API calls)
        commit_count: Number of recent commits to fetch
        style_id: CyberPPT visual style ID (1-8)
        selected_elements: List of slide element IDs to include
        selected_charts: List of chart type IDs to use

    Returns:
        dict with keys:
            - prompt_markdown: The full generated markdown prompt
            - file_path: Path to the saved file
            - repo_stats: The RepoStats object (or None if fetch failed)
            - commits: The fetched commits
            - generated_at: Timestamp string
    """
    collector = _get_collector(platform)
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Fetch repo stats with fallback
    stats = None
    stats_dict = {}
    try:
        stats = await collector.fetch_repo_stats(repo)
        logger.info("Fetched stats for %s/%s: %d stars, %d forks", platform, repo, stats.stars, stats.forks)
        stats_dict = {
            "stars": stats.stars,
            "forks": stats.forks,
            "open_issues": stats.open_issues,
            "language": stats.language or "-",
            "description": stats.description or "-",
            "default_branch": stats.default_branch or "",
            "html_url": stats.html_url,
            "created_at": _fmt(stats.created_at),
            "updated_at": _fmt(stats.updated_at),
            "pushed_at": _fmt(stats.pushed_at),
            "topics": ", ".join(stats.topics) if stats.topics else "-",
        }
    except Exception as e:
        logger.warning("Failed to fetch repo stats for %s/%s: %s", platform, repo, e)
        # Build minimal stats from branches_data if available
        default_branch = ""
        if branches_data and len(branches_data) > 0:
            for b in branches_data:
                if b.get("is_default"):
                    default_branch = b.get("branch", "")
                    break
            if not default_branch:
                default_branch = branches_data[0].get("branch", "")
        stats_dict = {
            "stars": "-",
            "forks": "-",
            "open_issues": "-",
            "language": "-",
            "description": "-",
            "default_branch": default_branch or "",
            "html_url": f"https://{platform}.com/{repo}",
            "created_at": "-",
            "updated_at": "-",
            "pushed_at": "-",
            "topics": "-",
        }

    # Determine which branch to fetch commits for
    branches_to_fetch = []
    if branches_data and len(branches_data) > 1:
        # Multiple branches: fetch latest commits from each
        for b in branches_data:
            b_name = b.get("branch", "") if isinstance(b, dict) else str(b)
            if b_name:
                branches_to_fetch.append(b_name)
    elif branches_data and len(branches_data) > 0:
        first = branches_data[0]
        b_name = first.get("branch", "") if isinstance(first, dict) else str(first)
        if b_name:
            branches_to_fetch.append(b_name)
    if not branches_to_fetch:
        branches_to_fetch = [stats_dict["default_branch"]]

    # Fetch recent commits with fallback
    commits = []
    for branch_name in branches_to_fetch:
        try:
            per_branch = max(1, commit_count // len(branches_to_fetch))
            branch_commits = await collector.fetch_recent_commits(repo, branch_name, per_branch)
            for c in branch_commits:
                c.branch = branch_name  # Tag branch name
            commits.extend(branch_commits)
            logger.info("Fetched %d commits for %s/%s branch=%s", len(branch_commits), platform, repo, branch_name)
        except Exception as e:
            logger.warning("Failed to fetch commits for %s/%s @ %s: %s", platform, repo, branch_name, e)
    # Sort all commits by date descending
    commits.sort(key=lambda c: c.committed_at or datetime(1970, 1, 1), reverse=True)
    commits = commits[:commit_count]

    # Try to fetch README (dynamic truncation)
    readme_text = ""
    try:
        readme_text = await collector.fetch_readme(repo)
        if readme_text:
            # Dynamically allocate: target total ~12KB, subtract known parts
            prompt_base_est = 4000  # fixed template overhead
            if commit_count > 0:
                prompt_base_est += commit_count * 100  # ~100 chars per commit row
            max_readme_chars = max(200, min(15000 - prompt_base_est, 5000))
            if len(readme_text) > max_readme_chars:
                readme_text = readme_text[:max_readme_chars] + "\n[... truncated ...]"
    except Exception as e:
        logger.warning("Failed to fetch README for %s/%s: %s", platform, repo, e)

    # Build branch info section (from DB data)
    branch_section = ""
    if branches_data:
        branch_table_rows = []
        branch_details_list = []
        for b in branches_data:
            b_name = b.get("branch", "") if isinstance(b, dict) else str(b)
            b_sha = b.get("last_sha", "")[:8] if isinstance(b, dict) and b.get("last_sha") else "-"
            b_author = b.get("last_commit_author", "-") if isinstance(b, dict) else "-"
            b_at = _fmt(b.get("last_commit_at")) if isinstance(b, dict) else "-"
            is_default = b.get("is_default", False) if isinstance(b, dict) else False
            label = " (default)" if is_default else ""
            branch_table_rows.append(f"| {b_name}{label} | `{b_sha}` | {b_author} | {b_at} |")
        branch_section = f"### Branches Overview ({len(branches_data)} branches)\n\n"
        branch_section += "| Branch | SHA | Author | Last Commit |\n|---|---|---|---|\n"
        branch_section += "\n".join(branch_table_rows)

    # Build commit table (with branch column for multi-branch)
    has_multiple_branches = len(set(c.branch for c in commits if c.branch)) > 1
    if has_multiple_branches:
        commit_table = "| # | Date | Branch | Author | SHA | Message |\n|---|---|---|---|---|---|\n"
        for i, c in enumerate(commits, 1):
            date_str = _fmt(c.committed_at)
            sha_short = c.sha[:8] if c.sha else "-"
            msg = (c.message or "")[:70]
            branch_label = c.branch or "-"
            commit_table += f"| {i} | {date_str} | `{branch_label}` | {c.author} | `{sha_short}` | {msg} |\n"
    else:
        commit_table = "| # | Date | Author | SHA | Message |\n|---|---|---|---|---|\n"
        for i, c in enumerate(commits, 1):
            date_str = _fmt(c.committed_at)
            sha_short = c.sha[:8] if c.sha else "-"
            msg = (c.message or "")[:80]
            commit_table += f"| {i} | {date_str} | {c.author} | `{sha_short}` | {msg} |\n"

    # Build README summary
    readme_summary = "No README content available."
    if readme_text:
        readme_summary = "```\n" + readme_text + "\n```"

    # Also add commits info to branch section if available
    if commits and branch_section:
        branch_section += "\n\n### Recent Commits\n"
        branch_section += f"Showing the latest {len(commits)} commits{f' across {len(branches_to_fetch)} branches' if len(branches_to_fetch) > 1 else ' on branch `{branches_to_fetch[0]}`'}:\n\n"

    # Build style section (with base64 embedded image)
    selected_style = CYBERPPT_STYLES[0]
    for s in CYBERPPT_STYLES:
        if s["id"] == style_id:
            selected_style = s
            break

    # Base64 embed the palette image
    preview_data = ""
    palette_img = selected_style.get("palette_img", "")
    if palette_img:
        img_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "static", "ppt-styles", palette_img
        )
        if os.path.exists(img_path):
            img = Image.open(img_path)
            # Resize to thumbnail for reasonable file size
            max_w = 600
            if img.width > max_w:
                ratio = max_w / img.width
                new_h = int(img.height * ratio)
                img = img.resize((max_w, new_h), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG", optimize=True)
            buf.seek(0)
            img_b64 = base64.b64encode(buf.read()).decode("ascii")
            preview_data = f"data:image/png;base64,{img_b64}"
    style_section = STYLE_PROMPT_SECTION.format(
        style_name=selected_style["name"],
        preview_data=preview_data,
        bg=selected_style["bg"],
        title=selected_style["title"],
        body=selected_style["body"],
        secondary=selected_style["secondary"],
        line=selected_style["line"],
        accent=selected_style["accent"],
        mood=selected_style["mood"],
        suitable_for=selected_style["suitable_for"],
        typography_scale=TYPOGRAPHY_SCALE,
    )

    # Build elements section
    if selected_elements is None:
        selected_elements = [e["id"] for e in SLIDE_ELEMENTS["element_options"] if e["default"]]
    if selected_charts is None:
        selected_charts = [c["id"] for c in SLIDE_ELEMENTS["chart_types"]]

    element_names = [e["name"] for e in SLIDE_ELEMENTS["element_options"] if e["id"] in selected_elements]
    chart_names = [c["name"] for c in SLIDE_ELEMENTS["chart_types"] if c["id"] in selected_charts]

    elements_section = ELEMENTS_PROMPT_SECTION.format(
        selected_elements="\n".join(f"- {n}" for n in element_names),
        selected_charts="\n".join(f"- {n}" for n in chart_names),
    )

    # Fill template
    # Assemble full prompt
    prompt = PPT_PROMPT_TEMPLATE.format(
        repo_full_name=f"{platform}/{repo}",
        platform=platform,
        repo_url=stats_dict["html_url"],
        description=stats_dict["description"],
        language=stats_dict["language"],
        stars=stats_dict["stars"],
        forks=stats_dict["forks"],
        open_issues=stats_dict["open_issues"],
        topics=stats_dict["topics"],
        default_branch=stats_dict["default_branch"],
        created_at=stats_dict["created_at"],
        updated_at=stats_dict["updated_at"],
        pushed_at=stats_dict["pushed_at"],
        recent_commits_section=branch_section,
        commit_count=len(commits),
        commit_table=commit_table,
        readme_summary=readme_summary,
        generated_at=generated_at,
    ) + "\n\n" + style_section + "\n\n" + elements_section

    # Save to file
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    safe_repo = repo.replace("/", "_").replace("\\", "_")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"ppt_prompt_{platform}_{safe_repo}_{timestamp}.md"
    file_path = os.path.join(OUTPUT_DIR, filename)
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(prompt)

    logger.info("PPT prompt saved to %s", file_path)

    return {
        "prompt_markdown": prompt,
        "file_path": file_path,
        "filename": filename,
        "repo_stats": stats,
        "commits_count": len(commits),
        "generated_at": generated_at,
        "style": selected_style["name"],
        "elements_count": len(element_names),
    }