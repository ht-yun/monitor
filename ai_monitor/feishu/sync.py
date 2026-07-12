# -*- coding: utf-8 -*-
"""Synchronize repository links from a Feishu cloud document."""

from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy import select

from ai_monitor.config.settings import get_settings
from ai_monitor.feishu.client import FeishuClient, parse_feishu_source
from ai_monitor.feishu.parser import extract_repo_targets_from_blocks
from ai_monitor.store.database import get_session
from ai_monitor.store.models import MonitoredRepository


async def sync_repositories_from_feishu(
    doc_token: Optional[str] = None,
    run_reconcile: bool = False,
) -> Dict:
    """Read Feishu doc blocks, discover repositories, and upsert local rows."""
    settings = get_settings()
    token = (doc_token or settings.FEISHU_REPO_DOC_TOKEN or "").strip()
    if not token:
        raise ValueError("AIMONITOR_FEISHU_REPO_DOC_TOKEN is not configured")

    client = FeishuClient()
    source_kind, source_token = parse_feishu_source(token)
    document_id = await client.resolve_document_id(token)
    blocks = await client.list_doc_blocks(document_id)
    targets = extract_repo_targets_from_blocks(blocks)
    result = await upsert_feishu_repositories(targets, token)
    result["source_type"] = source_kind
    result["source_token"] = source_token
    result["document_id"] = document_id

    if run_reconcile:
        from ai_monitor.repo_watch.reconciler import reconcile_repositories

        result["reconcile"] = await reconcile_repositories()

    return result


async def upsert_feishu_repositories(targets: List[tuple[str, str, str]], doc_token: str) -> Dict:
    now = datetime.utcnow()
    created = 0
    updated = 0
    repositories = []

    async with get_session() as session:
        for platform, repo, _branch in targets:
            owner, name = repo.split("/", 1)
            existing = await session.execute(
                select(MonitoredRepository).where(
                    MonitoredRepository.platform == platform,
                    MonitoredRepository.repo == repo,
                )
            )
            row = existing.scalar_one_or_none()
            repo_url = f"https://{'github.com' if platform == 'github' else 'gitee.com'}/{repo}"

            if row:
                row.owner = owner
                row.name = name
                row.repo_url = row.repo_url or repo_url
                row.source = row.source or "feishu_doc"
                row.source_doc_token = doc_token
                row.status = "active"
                row.error_message = ""
                row.last_seen_at = now
                row.updated_at = now
                updated += 1
            else:
                row = MonitoredRepository(
                    platform=platform,
                    owner=owner,
                    name=name,
                    repo=repo,
                    repo_url=repo_url,
                    source="feishu_doc",
                    source_doc_token=doc_token,
                    status="active",
                    first_seen_at=now,
                    last_seen_at=now,
                )
                session.add(row)
                created += 1
            repositories.append({"platform": platform, "repo": repo})

    return {
        "doc_token": doc_token,
        "found": len(targets),
        "created": created,
        "updated": updated,
        "repositories": repositories,
    }
