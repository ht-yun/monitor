# -*- coding: utf-8 -*-
from typing import List, Optional
from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    source_type: str = "social"  # social | github | gitee
    platform: str
    keywords: str = ""
    repo: Optional[str] = None  # owner/name for github | gitee
    branch: str = ""  # git branch/ref; empty = default branch
    crawler_type: str = "search"
    cron_expression: Optional[str] = None
    max_notes: int = 20
    enable_comments: bool = True
    rule_set_ids: List[str] = Field(default_factory=lambda: ["brand_monitoring"])


class JobUpdateRequest(BaseModel):
    keywords: Optional[str] = None
    cron_expression: Optional[str] = None
    status: Optional[str] = None
    max_notes: Optional[int] = None
    enable_comments: Optional[bool] = None
    rule_set_ids: Optional[List[str]] = None
    branch: Optional[str] = None


class JobResponse(BaseModel):
    job_id: str
    source_type: str
    platform: str
    repo: Optional[str] = None
    branch: Optional[str] = None
    keywords: str
    cron_expression: str
    status: str
    last_run_at: Optional[str] = None
    last_run_status: Optional[str] = None
    last_sha: Optional[str] = None
    last_commit_at: Optional[str] = None
    last_commit_author: Optional[str] = None
    latest_update_at: Optional[str] = None
    latest_update_label: Optional[str] = None
    rule_set_ids: List[str] = Field(default_factory=list)


class AlertResponse(BaseModel):
    id: int
    rule_id: Optional[str]
    rule_name: Optional[str]
    severity: str
    platform: Optional[str]
    job_id: Optional[str]
    title: Optional[str]
    summary: Optional[str]
    acknowledged: bool
    created_at: str


class AnalysisResponse(BaseModel):
    id: int
    content_id: str
    platform: str
    job_id: Optional[str]
    sentiment: Optional[str]
    sentiment_score: Optional[float]
    topics: Optional[list]
    summary: Optional[str]
    analyzed_at: str


class DashboardStats(BaseModel):
    active_jobs: int
    total_alerts: int
    unack_alerts: int
    analysis_today: int
    platforms: List[str]
