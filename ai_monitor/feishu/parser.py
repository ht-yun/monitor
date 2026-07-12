# -*- coding: utf-8 -*-
"""Extract repository links from Feishu document blocks."""

import json
from typing import Any, Dict, List, Tuple

from ai_monitor.repo_watch.url_parser import extract_repo_targets

RepoTarget = Tuple[str, str, str]


def extract_repo_targets_from_blocks(blocks: List[Dict[str, Any]]) -> List[RepoTarget]:
    """Return de-duplicated repository targets found in Feishu blocks."""
    text = json.dumps(blocks or [], ensure_ascii=False)
    return extract_repo_targets(text)
