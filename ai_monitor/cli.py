# -*- coding: utf-8 -*-
"""CLI entry point for AI Monitor."""

import sys
from pathlib import Path

# Ensure MediaCrawler is importable
MEDIACRAWLER_PATH = str(Path(__file__).resolve().parent.parent / "MediaCrawler")
if MEDIACRAWLER_PATH not in sys.path:
    sys.path.insert(0, MEDIACRAWLER_PATH)

import asyncio
import typer
from typing import Optional

cli = typer.Typer(
    name="ai-monitor",
    help="AI-powered social media monitoring platform",
    add_completion=False,
)


@cli.command()
def init_db():
    """Initialize the AI Monitor database tables."""

    async def _init():
        from ai_monitor.store.database import init_db

        await init_db()
        print("[AI Monitor] Database tables created successfully.")

    asyncio.run(_init())


@cli.command()
def init_rules():
    """Import default monitoring rules from YAML into database."""

    async def _init():
        import yaml
        from ai_monitor.store.database import init_db, get_session
        from ai_monitor.store.models import RuleConfig
        from sqlalchemy import select

        await init_db()

        rules_path = Path(__file__).resolve().parent / "config" / "rules.yaml"
        with open(rules_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        imported = 0
        async with get_session() as session:
            for set_name, rule_set in data.get("rule_sets", {}).items():
                for rule in rule_set.get("rules", []):
                    existing = await session.execute(
                        select(RuleConfig).where(RuleConfig.rule_id == rule["rule_id"])
                    )
                    if existing.scalar_one_or_none():
                        continue
                    record = RuleConfig(
                        rule_id=rule["rule_id"],
                        name=rule["name"],
                        rule_type=rule["rule_type"],
                        description=rule.get("description", ""),
                        params=rule.get("params", {}),
                        severity=rule.get("severity", "warning"),
                        notification_channels=rule.get("notification_channels", []),
                        cooldown_minutes=rule.get("cooldown_minutes", 30),
                        is_active=True,
                    )
                    session.add(record)
                    imported += 1

        print(f"[AI Monitor] Imported {imported} default rules from rules.yaml")

    asyncio.run(_init())


@cli.command("init-joyoung")
def init_joyoung_rules():
    """Import 九阳 brand monitoring rules."""

    async def _run():
        from ai_monitor.scripts.init_joyoung_rules import main

        await main()

    asyncio.run(_run())


@cli.command()
def health():
    """Check the health of all components."""

    async def _health():
        from ai_monitor.config.settings import get_settings
        from ai_monitor.store.database import init_db, get_session

        settings = get_settings()
        print(f"  Config: OK (AI Provider: {settings.AI_PROVIDER})")

        try:
            await init_db()
            async with get_session() as session:
                from sqlalchemy import text
                await session.execute(text("SELECT 1"))
            print("  Database: OK")
        except Exception as e:
            print(f"  Database: ERROR - {e}")

        mc_path = Path(settings.MEDIACRAWLER_PATH)
        if mc_path.exists():
            print(f"  MediaCrawler: OK ({mc_path})")
        else:
            print(f"  MediaCrawler: WARN - path not found ({mc_path})")

        if settings.OPENAI_API_KEY:
            print("  AI Analysis: OK (OpenAI key configured)")
        else:
            print("  AI Analysis: WARN - no OPENAI_API_KEY (keyword rules only)")

        if settings.GITHUB_TOKEN:
            print("  GitHub Token: OK")
        else:
            print("  GitHub Token: WARN - not set (rate limits apply)")

    asyncio.run(_health())


job_cli = typer.Typer(help="Social media monitoring jobs (MediaCrawler + rules).")
cli.add_typer(job_cli, name="job")


@job_cli.command("add")
def job_add(
    platform: str = typer.Option(..., help="Platform: xhs, dy, wb, bili, zhihu, ..."),
    keywords: str = typer.Option(..., help="Search keywords"),
    cron: str = typer.Option("0 */2 * * *", help="Cron schedule"),
    max_notes: int = typer.Option(20, help="Max items per crawl"),
):
    """Register a social media monitoring job."""

    async def _add():
        from uuid import uuid4
        from ai_monitor.store.database import init_db, get_session
        from ai_monitor.store.models import MonitoringJob
        from sqlalchemy import select

        await init_db()
        job_id = f"{platform}_search_{uuid4().hex[:8]}"
        async with get_session() as session:
            session.add(
                MonitoringJob(
                    job_id=job_id,
                    source_type="social",
                    platform=platform,
                    keywords=keywords,
                    crawler_type="search",
                    cron_expression=cron,
                    save_option="jsonl",
                    enable_comments=True,
                    max_notes=max_notes,
                    status="active",
                )
            )
        print(f"[job] Added {platform} keywords={keywords!r} (job_id={job_id}, cron={cron})")
        print(f"[job] Run once: python -m ai_monitor.cli job run --job-id {job_id}")

    asyncio.run(_add())


@job_cli.command("list")
def job_list():
    """List social monitoring jobs."""

    async def _list():
        from ai_monitor.store.database import init_db, get_session
        from ai_monitor.store.models import MonitoringJob
        from sqlalchemy import select

        await init_db()
        async with get_session() as session:
            result = await session.execute(
                select(MonitoringJob).where(MonitoringJob.source_type == "social")
            )
            rows = list(result.scalars().all())

        if not rows:
            print("[job] No social jobs. Use: job add --platform xhs --keywords '品牌名'")
            return
        for r in rows:
            print(
                f"  {r.job_id} | {r.platform} | keywords={r.keywords!r} | "
                f"status={r.status} | last_run={r.last_run_at or '-'}"
            )

    asyncio.run(_list())


@job_cli.command("run")
def job_run(job_id: str = typer.Option(..., help="Job ID")):
    """Run a social monitoring job immediately (crawl + analyze + rules)."""

    async def _run():
        from ai_monitor.store.database import init_db, get_session
        from ai_monitor.store.models import MonitoringJob
        from ai_monitor.scheduler.base import JobConfig
        from ai_monitor.scheduler.jobs import MonitoringJob as JobRunner
        from sqlalchemy import select

        await init_db()
        async with get_session() as session:
            result = await session.execute(
                select(MonitoringJob).where(MonitoringJob.job_id == job_id)
            )
            record = result.scalar_one_or_none()
        if not record:
            print(f"[job] Not found: {job_id}")
            raise typer.Exit(1)

        from ai_monitor.repo_watch.helpers import job_config_from_record

        config = job_config_from_record(record)
        print(f"[job] Running {job_id} ({record.platform})...")
        run = await JobRunner(config).execute()
        print(
            f"  status={run.status} crawled={run.items_crawled} "
            f"analyzed={run.items_analyzed} alerts={run.alerts_triggered}"
        )
        if run.error_message:
            print(f"  note: {run.error_message}")
        if run.status == "failed":
            raise typer.Exit(1)

    asyncio.run(_run())


@cli.command()
def daemon(
    interval: int = typer.Option(0, help="Cycle interval seconds (0 = use config default)"),
):
    """Run unified daemon: repo watch + social jobs on schedule."""

    async def _daemon():
        from ai_monitor.daemon.unified import daemon_loop

        await daemon_loop(interval if interval > 0 else None)

    try:
        asyncio.run(_daemon())
    except KeyboardInterrupt:
        print("\n[daemon] Stopped.")


@cli.command()
def start(
    host: str = typer.Option("0.0.0.0", help="Host to bind"),
    port: int = typer.Option(8081, help="Port to bind"),
):
    """Start the AI Monitor dashboard server."""
    import uvicorn

    uvicorn.run("ai_monitor.main:app", host=host, port=port, reload=True)


repo_cli = typer.Typer(help="Monitor GitHub/Gitee repos for new commits (hourly).")
cli.add_typer(repo_cli, name="watch-repo")


@repo_cli.command("add")
def watch_repo_add(
    platform: str = typer.Option(..., help="github or gitee"),
    repo: str = typer.Option(..., help="Repository as owner/name"),
    branch: str = typer.Option("", help="Branch name (empty = default branch)"),
    cron: str = typer.Option("0 * * * *", help="Cron expression (default: every hour)"),
):
    """Register a repository to watch."""

    async def _add():
        from ai_monitor.repo_watch.service import REPO_CRON_HOURLY, REPO_PLATFORMS
        from ai_monitor.store.database import init_db, get_session
        from ai_monitor.store.models import MonitoringJob
        from sqlalchemy import select

        platform_l = platform.lower().strip()
        if platform_l not in REPO_PLATFORMS:
            raise typer.BadParameter(f"platform must be one of: {', '.join(REPO_PLATFORMS)}")

        from ai_monitor.repo_watch.helpers import branch_label, resolve_repo_job

        try:
            platform_l, repo, branch_s, job_id = resolve_repo_job(
                repo,
                platform_hint=platform_l,
                branch_hint=branch,
            )
        except ValueError as e:
            raise typer.BadParameter(str(e)) from e

        cron_expr = cron or REPO_CRON_HOURLY

        await init_db()
        async with get_session() as session:
            existing = await session.execute(
                select(MonitoringJob).where(MonitoringJob.job_id == job_id)
            )
            if existing.scalar_one_or_none():
                print(f"[repo_watch] Job already exists: {job_id}")
                return

            session.add(
                MonitoringJob(
                    job_id=job_id,
                    source_type=platform_l,
                    platform=platform_l,
                    repo=repo,
                    branch=branch_s or None,
                    keywords=repo,
                    crawler_type="commits",
                    cron_expression=cron_expr,
                    save_option="db",
                    enable_comments=False,
                    status="active",
                )
            )

        print(
            f"[repo_watch] Added {platform_l}/{repo}@{branch_label(branch_s)} "
            f"(job_id={job_id}, cron={cron_expr})"
        )
        print("[repo_watch] Run: python -m ai_monitor.cli watch-repo check --job-id", job_id)
        print("[repo_watch] Run daemon: python -m ai_monitor.cli watch-repo daemon")

    asyncio.run(_add())


@repo_cli.command("list")
def watch_repo_list():
    """List registered repository watch jobs."""

    async def _list():
        from ai_monitor.store.database import init_db, get_session
        from ai_monitor.store.models import MonitoringJob
        from ai_monitor.repo_watch.service import REPO_PLATFORMS
        from sqlalchemy import select

        await init_db()
        async with get_session() as session:
            result = await session.execute(
                select(MonitoringJob).where(MonitoringJob.source_type.in_(REPO_PLATFORMS))
            )
            rows = list(result.scalars().all())

        if not rows:
            print("[repo_watch] No repository watch jobs. Use: watch-repo add --platform github --repo owner/name")
            return

        from ai_monitor.repo_watch.helpers import branch_label

        for r in rows:
            br = branch_label(getattr(r, "branch", None) or "")
            print(
                f"  {r.job_id} | {r.platform}/{r.repo}@{br} | status={r.status} | "
                f"last_sha={ (r.last_sha or '-')[:8] } | "
                f"author={r.last_commit_author or '-'} | "
                f"commit_at={r.last_commit_at or '-'}"
            )

    asyncio.run(_list())


@repo_cli.command("check")
def watch_repo_check(
    job_id: str = typer.Option(..., help="Job ID from watch-repo list"),
):
    """Run a single check immediately."""

    async def _check():
        from ai_monitor.store.database import init_db, get_session
        from ai_monitor.store.models import MonitoringJob
        from ai_monitor.scheduler.base import JobConfig
        from ai_monitor.scheduler.jobs import MonitoringJob as JobRunner
        from sqlalchemy import select

        await init_db()
        async with get_session() as session:
            result = await session.execute(
                select(MonitoringJob).where(MonitoringJob.job_id == job_id)
            )
            record = result.scalar_one_or_none()
        if not record:
            print(f"[repo_watch] Job not found: {job_id}")
            raise typer.Exit(1)

        from ai_monitor.repo_watch.helpers import branch_label, job_config_from_record

        config = job_config_from_record(record)
        run = await JobRunner(config).execute()
        br = branch_label(config.branch)
        if run.status == "failed":
            print(f"[repo_watch] FAILED: {run.error_message}")
            raise typer.Exit(1)
        if run.repo_updated:
            print(
                f"[repo_watch] NEW COMMIT on {record.platform}/{record.repo}@{br}\n"
                f"  author: {run.commit_author}\n"
                f"  time:   {run.commit_at}\n"
                f"  sha:    {run.commit_sha}\n"
                f"  msg:    {run.commit_message}"
            )
        else:
            print(
                f"[repo_watch] No new commits (current sha {run.commit_sha[:8]}, "
                f"author={run.commit_author}, time={run.commit_at})"
            )

    asyncio.run(_check())


@repo_cli.command("history")
def watch_repo_history(
    job_id: Optional[str] = typer.Option(None, help="Filter by job ID"),
    limit: int = typer.Option(20, help="Max events to show"),
):
    """Show recorded repository update events."""

    async def _history():
        from ai_monitor.store.database import init_db, get_session
        from ai_monitor.store.models import RepoUpdateEvent
        from sqlalchemy import select

        await init_db()
        async with get_session() as session:
            q = select(RepoUpdateEvent)
            if job_id:
                q = q.where(RepoUpdateEvent.job_id == job_id)
            q = q.order_by(RepoUpdateEvent.detected_at.desc()).limit(limit)
            result = await session.execute(q)
            rows = list(result.scalars().all())

        if not rows:
            print("[repo_watch] No update events recorded yet.")
            return

        for e in rows:
            print(
                f"  {e.detected_at} | {e.platform}/{e.repo} | "
                f"{e.commit_author} @ {e.committed_at} | {e.commit_sha[:8]} | {e.commit_message[:60]}"
            )

    asyncio.run(_history())


@repo_cli.command("daemon")
def watch_repo_daemon():
    """Run hourly checks for all registered repo watch jobs (blocks)."""

    async def _daemon():
        from ai_monitor.repo_watch.daemon import daemon_loop

        await daemon_loop()

    try:
        asyncio.run(_daemon())
    except KeyboardInterrupt:
        print("\n[repo_watch] Daemon stopped.")


if __name__ == "__main__":
    cli()
