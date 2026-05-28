# -*- coding: utf-8 -*-
"""Load MediaCrawler JSONL output into normalized content dicts."""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional


def get_crawl_data_dir(mediacrawler_root: Path, save_data_path: str = "") -> Path:
    base = Path(save_data_path) if save_data_path else mediacrawler_root / "data"
    return base.resolve()


def load_crawled_contents(
    platform: str,
    crawler_type: str,
    mediacrawler_root: Path,
    save_data_path: str = "",
    day: Optional[str] = None,
) -> List[dict]:
    """Read contents JSONL for a platform crawl (today or recent days)."""
    base = get_crawl_data_dir(mediacrawler_root, save_data_path)
    days_to_try = []
    if day:
        days_to_try.append(day)
    else:
        today = date.today()
        for offset in range(3):
            days_to_try.append((today - timedelta(days=offset)).isoformat())

    for d in days_to_try:
        path = base / platform / "jsonl" / f"{crawler_type}_contents_{d}.jsonl"
        if path.exists():
            return _read_jsonl(path)

    # Fallback: newest matching file in platform jsonl dir
    jsonl_dir = base / platform / "jsonl"
    if jsonl_dir.is_dir():
        pattern = f"{crawler_type}_contents_*.jsonl"
        candidates = sorted(jsonl_dir.glob(pattern), reverse=True)
        if candidates:
            return _read_jsonl(candidates[0])

    return []


def load_crawled_with_comments(
    platform: str,
    crawler_type: str,
    mediacrawler_root: Path,
    save_data_path: str = "",
    day: Optional[str] = None,
    include_comments: bool = True,
) -> List[dict]:
    """Load note/video contents and optional comments JSONL."""
    items = load_crawled_contents(
        platform, crawler_type, mediacrawler_root, save_data_path, day
    )
    if not include_comments or not items:
        return items

    base = get_crawl_data_dir(mediacrawler_root, save_data_path)
    days_to_try = [day] if day else []
    if not days_to_try:
        today = date.today()
        days_to_try = [(today - timedelta(days=o)).isoformat() for o in range(3)]

    comments = []
    for d in days_to_try:
        path = base / platform / "jsonl" / f"{crawler_type}_comments_{d}.jsonl"
        if path.exists():
            comments = _read_jsonl(path)
            break
    if not comments:
        jsonl_dir = base / platform / "jsonl"
        if jsonl_dir.is_dir():
            candidates = sorted(jsonl_dir.glob(f"{crawler_type}_comments_*.jsonl"), reverse=True)
            if candidates:
                comments = _read_jsonl(candidates[0])

    for c in comments:
        c.setdefault("content_type", "comment")
    return items + comments


def _read_jsonl(path: Path) -> List[dict]:
    items = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return items
