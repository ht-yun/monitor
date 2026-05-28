# -*- coding: utf-8 -*-
"""Shared types for repository collectors."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class CommitInfo:
    """Latest commit snapshot from GitHub or Gitee."""

    sha: str
    author: str
    committed_at: datetime
    message: str = ""
    url: str = ""
    branch: str = ""
