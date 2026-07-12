# -*- coding: utf-8 -*-
"""Small Feishu OpenAPI client for reading repository source documents."""

import time
from typing import Any, Dict, List
from urllib.parse import urlparse

import httpx

from ai_monitor.config.settings import get_settings


class FeishuClient:
    """Read Feishu docx blocks using tenant access token auth."""

    API_BASE = "https://open.feishu.cn/open-apis"

    def __init__(self):
        settings = get_settings()
        self.app_id = settings.FEISHU_APP_ID
        self.app_secret = settings.FEISHU_APP_SECRET
        self._tenant_token = ""
        self._token_expires_at = 0.0

    def configured(self) -> bool:
        return bool(self.app_id and self.app_secret)

    async def tenant_access_token(self) -> str:
        if self._tenant_token and time.time() < self._token_expires_at:
            return self._tenant_token
        if not self.configured():
            raise ValueError("Feishu app id/secret are not configured")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.API_BASE}/auth/v3/tenant_access_token/internal",
                json={"app_id": self.app_id, "app_secret": self.app_secret},
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 0:
            raise ValueError(f"Feishu token request failed: {data.get('msg') or data}")

        self._tenant_token = data["tenant_access_token"]
        self._token_expires_at = time.time() + int(data.get("expire", 7200)) - 60
        return self._tenant_token

    async def resolve_document_id(self, source: str) -> str:
        kind, token = parse_feishu_source(source)
        if kind in ("docx", "docs"):
            return token
        if kind == "wiki":
            return await self.resolve_wiki_document_id(token)
        raise ValueError(f"Unsupported Feishu source type: {kind}")

    async def resolve_wiki_document_id(self, wiki_token: str) -> str:
        token = await self.tenant_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.API_BASE}/wiki/v2/spaces/get_node",
                headers=headers,
                params={"token": wiki_token},
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 0:
            raise ValueError(f"Feishu wiki node request failed: {data.get('msg') or data}")

        node = (data.get("data") or {}).get("node") or {}
        obj_type = node.get("obj_type") or node.get("node_type") or ""
        obj_token = node.get("obj_token") or node.get("document_id") or ""
        if obj_type and obj_type not in ("docx", "doc"):
            raise ValueError(f"Feishu wiki node is not a docx document: {obj_type}")
        if not obj_token:
            raise ValueError(f"Feishu wiki node has no document token: {wiki_token}")
        return obj_token

    async def list_doc_blocks(self, document_id: str) -> List[Dict[str, Any]]:
        document_id = await self.resolve_document_id(document_id)
        token = await self.tenant_access_token()
        headers = {"Authorization": f"Bearer {token}"}
        items: List[Dict[str, Any]] = []
        page_token = ""

        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                params = {"page_size": 500}
                if page_token:
                    params["page_token"] = page_token
                response = await client.get(
                    f"{self.API_BASE}/docx/v1/documents/{document_id}/blocks",
                    headers=headers,
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                if data.get("code") != 0:
                    raise ValueError(f"Feishu block request failed: {data.get('msg') or data}")
                payload = data.get("data") or {}
                items.extend(payload.get("items") or [])
                if not payload.get("has_more"):
                    break
                page_token = payload.get("page_token") or ""
                if not page_token:
                    break

        return items


def parse_feishu_source(source: str) -> tuple[str, str]:
    """Parse a Feishu URL or token into (kind, token)."""
    text = (source or "").strip()
    if not text:
        raise ValueError("Feishu document source cannot be empty")

    if "://" in text:
        parsed = urlparse(text)
        segments = [p for p in parsed.path.strip("/").split("/") if p]
        for kind in ("docx", "docs", "wiki"):
            if kind in segments:
                idx = segments.index(kind)
                if idx + 1 < len(segments):
                    return kind, segments[idx + 1]
        raise ValueError(f"Unsupported Feishu document URL: {source}")

    return "docx", text
