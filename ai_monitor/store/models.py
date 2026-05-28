# -*- coding: utf-8 -*-
"""SQLAlchemy ORM models for AI Monitor."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON, Boolean, Enum as SAEnum
from sqlalchemy.orm import DeclarativeBase
import enum


class Base(DeclarativeBase):
    pass


# ==================== Enums ====================

class SeverityEnum(str, enum.Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class JobStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


# ==================== Monitoring Jobs ====================

class MonitoringJob(Base):
    """Persistent monitoring job configuration."""
    __tablename__ = "monitoring_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(128), unique=True, index=True, nullable=False)
    source_type = Column(String(16), default="social")  # social | github | gitee
    platform = Column(String(16), nullable=False)
    repo = Column(String(256), nullable=True)  # owner/name for github | gitee
    branch = Column(String(256), nullable=True)  # empty = repository default branch
    keywords = Column(Text, default="")
    crawler_type = Column(String(16), default="search")
    cron_expression = Column(String(64), nullable=False)
    save_option = Column(String(16), default="jsonl")
    enable_comments = Column(Boolean, default=True)
    max_notes = Column(Integer, default=20)
    start_page = Column(Integer, default=1)
    rule_set_ids = Column(JSON, default=list)
    status = Column(String(16), default=JobStatusEnum.ACTIVE.value)
    last_sha = Column(String(64), nullable=True)
    last_commit_author = Column(String(128), nullable=True)
    last_commit_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_run_at = Column(DateTime, nullable=True)
    last_run_status = Column(String(16), nullable=True)
    historical_stats = Column(JSON, default=list)  # rolling stats for trend rules


class RepoUpdateEvent(Base):
    """Recorded when a monitored repository receives a new commit."""
    __tablename__ = "repo_update_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(128), index=True, nullable=False)
    platform = Column(String(16), nullable=False)
    repo = Column(String(256), nullable=False)
    branch = Column(String(256), default="")
    commit_sha = Column(String(64), nullable=False)
    commit_author = Column(String(128), nullable=False)
    committed_at = Column(DateTime, nullable=False)
    commit_message = Column(Text, default="")
    commit_url = Column(String(512), default="")
    detected_at = Column(DateTime, default=datetime.utcnow)


# ==================== AI Analysis Results ====================

class AnalysisResult(Base):
    """AI analysis results for crawled content."""
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content_id = Column(String(128), index=True, nullable=False)
    platform = Column(String(16), nullable=False)
    job_id = Column(String(128), index=True)
    content_type = Column(String(16), default="note")  # note | comment
    sentiment = Column(String(16))  # positive | negative | neutral
    sentiment_score = Column(Float)
    topics = Column(JSON)  # list of extracted keywords
    summary = Column(Text)
    entities = Column(JSON)  # named entities
    risk_score = Column(Float, default=0.0)
    raw_content = Column(Text)  # original text for reference
    analyzed_at = Column(DateTime, default=datetime.utcnow)


# ==================== Alerts ====================

class Alert(Base):
    """Triggered monitoring alerts."""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(128), index=True)
    rule_name = Column(String(128))
    severity = Column(String(16), default=SeverityEnum.WARNING.value)
    platform = Column(String(16))
    job_id = Column(String(128), index=True)
    title = Column(String(255))
    summary = Column(Text)
    matched_items = Column(JSON)  # list of matched content items
    channels_sent = Column(JSON)  # list of channels notified
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


# ==================== Rule Configurations ====================

class RuleConfig(Base):
    """Persistent rule configuration."""
    __tablename__ = "rule_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    rule_id = Column(String(128), unique=True, index=True, nullable=False)
    name = Column(String(128), nullable=False)
    rule_type = Column(String(32), nullable=False)  # keyword | sentiment | anomaly | trend
    description = Column(Text, default="")
    params = Column(JSON, nullable=False)
    severity = Column(String(16), default=SeverityEnum.WARNING.value)
    notification_channels = Column(JSON, default=list)  # ["email", "dingtalk"]
    cooldown_minutes = Column(Integer, default=30)
    rule_set = Column(String(64), default="")  # brand_monitoring | joyoung_brand | ...
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ==================== Notification Configurations ====================

class NotificationConfig(Base):
    """Persistent notification channel configuration."""
    __tablename__ = "notification_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_name = Column(String(32), unique=True, index=True, nullable=False)
    display_name = Column(String(64))
    is_enabled = Column(Boolean, default=False)
    config = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
