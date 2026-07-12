# -*- coding: utf-8 -*-
"""Database engine, session factory, and init utilities."""

from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from ai_monitor.config.settings import get_settings
from ai_monitor.store.models import Base

_engine = None
_session_factory = None


def _get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.DATABASE_URL, echo=False)
    return _engine


def _get_session_factory() -> async_sessionmaker:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            _get_engine(), class_=AsyncSession, expire_on_commit=False
        )
    return _session_factory


async def init_db():
    """Create all tables and apply lightweight SQLite migrations."""
    engine = _get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_migrate_sqlite_columns)


def _migrate_sqlite_columns(conn):
    """Add repo-watch columns to existing monitoring_jobs tables (SQLite)."""
    from sqlalchemy import inspect, text

    inspector = inspect(conn)
    if "monitoring_jobs" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("monitoring_jobs")}
    additions = [
        ("source_type", "VARCHAR(16) DEFAULT 'social'"),
        ("repo", "VARCHAR(256)"),
        ("last_sha", "VARCHAR(64)"),
        ("last_commit_author", "VARCHAR(128)"),
        ("last_commit_at", "DATETIME"),
    ]
    for name, ddl in additions:
        if name not in existing:
            conn.execute(text(f"ALTER TABLE monitoring_jobs ADD COLUMN {name} {ddl}"))

    if "rule_configs" in inspector.get_table_names():
        rc_cols = {col["name"] for col in inspector.get_columns("rule_configs")}
        if "rule_set" not in rc_cols:
            conn.execute(text("ALTER TABLE rule_configs ADD COLUMN rule_set VARCHAR(64) DEFAULT ''"))

    mj_cols = {col["name"] for col in inspector.get_columns("monitoring_jobs")}
    if "historical_stats" not in mj_cols:
        conn.execute(text("ALTER TABLE monitoring_jobs ADD COLUMN historical_stats JSON"))
    if "rule_set_ids" not in mj_cols:
        conn.execute(text("ALTER TABLE monitoring_jobs ADD COLUMN rule_set_ids JSON"))
    if "branch" not in mj_cols:
        conn.execute(text("ALTER TABLE monitoring_jobs ADD COLUMN branch VARCHAR(256)"))

    if "repo_update_events" in inspector.get_table_names():
        ev_cols = {col["name"] for col in inspector.get_columns("repo_update_events")}
        if "branch" not in ev_cols:
            conn.execute(text("ALTER TABLE repo_update_events ADD COLUMN branch VARCHAR(256) DEFAULT ''"))

    if "monitored_repositories" in inspector.get_table_names():
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "ux_monitored_repositories_platform_repo "
            "ON monitored_repositories(platform, repo)"
        ))

    if "monitored_branches" in inspector.get_table_names():
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS "
            "ux_monitored_branches_repository_branch "
            "ON monitored_branches(repository_id, branch)"
        ))


async def close_db():
    """Dispose engine."""
    global _engine, _session_factory
    if _engine:
        await _engine.dispose()
        _engine = None
        _session_factory = None


@asynccontextmanager
async def get_session():
    """Async context manager for database sessions."""
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()
