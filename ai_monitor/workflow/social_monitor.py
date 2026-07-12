# -*- coding: utf-8 -*-
"""End-to-end social monitoring: analyze content, evaluate rules, persist, notify."""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from ai_monitor.ai.factory import AIProviderFactory
from ai_monitor.ai.pipeline import AIPipeline
from ai_monitor.config.settings import get_settings
from ai_monitor.notification.dispatcher import NotificationDispatcher
from ai_monitor.rules.rule_engine import RuleEngine
from ai_monitor.scheduler.base import JobConfig, JobRunResult
from ai_monitor.store.database import get_session
from ai_monitor.store.models import Alert, AnalysisResult, MonitoringJob
from sqlalchemy import select

logger = logging.getLogger("ai_monitor")


async def run_social_monitor_pipeline(
    config: JobConfig,
    content_items: List[Dict],
    run_result: JobRunResult,
) -> JobRunResult:
    """Run AI analysis (if configured), rules, DB persistence, and notifications."""
    if not content_items:
        run_result.items_crawled = 0
        run_result.status = "success"
        await _touch_job_run(config.job_id, "success", 0, 0)
        return run_result

    run_result.items_crawled = len(content_items)
    settings = get_settings()
    analysis_results: List[Dict] = []

    # --- AI analysis (optional when API key present) ---
    if settings.OPENAI_API_KEY:
        try:
            provider = AIProviderFactory.create(settings.AI_PROVIDER)
            pipeline = AIPipeline(provider)
            engine_rules = RuleEngine()
            await engine_rules.load_rules_for_job(config.job_id)
            historical = engine_rules.get_historical_stats(config.job_id, lookback_hours=24)
            baseline = _baseline_from_history(historical)
            output = await pipeline.process(
                content_items,
                config.platform,
                config.job_id,
                historical_baseline=baseline if historical else None,
            )
            analysis_results = output.get("items", [])
            run_result.items_analyzed = output.get("total_analyzed", 0)
        except Exception as e:
            logger.warning("[social_monitor] AI pipeline skipped: %s", e)
            analysis_results = _fallback_analysis(content_items, config)
    else:
        logger.info("[social_monitor] No OPENAI_API_KEY — using keyword-only analysis")
        analysis_results = _fallback_analysis(content_items, config)

    # --- Rules ---
    rule_engine = RuleEngine()
    await rule_engine.load_rules_for_job(config.job_id)
    triggered = await rule_engine.evaluate_all(
        content_items,
        analysis_results,
        config.job_id,
        config.platform,
    )
    run_result.alerts_triggered = len(triggered)

    # --- Persist ---
    await _save_analysis_results(config, analysis_results)
    alert_ids = await _save_alerts(config, triggered)

    # --- Notify ---
    dispatcher = NotificationDispatcher()
    for result in triggered:
        await dispatcher.send_alert(
            rule_name=result.rule_name,
            severity=result.severity,
            platform=config.platform,
            job_id=config.job_id,
            summary=result.summary,
            matched_count=len(result.matched_items),
            channels=await _resolve_channels(result.rule_id),
            sample=_sample_text(result.matched_items),
        )
        if alert_ids:
            await _mark_channels_sent(alert_ids[-1], dispatcher.last_channels_used)

    await _touch_job_run(
        config.job_id,
        "success",
        run_result.items_crawled,
        run_result.alerts_triggered,
    )
    return run_result


def _fallback_analysis(items: List[Dict], config: JobConfig) -> List[Dict]:
    results = []
    for i, item in enumerate(items):
        content_id = (
            item.get("note_id")
            or item.get("video_id")
            or item.get("aweme_id")
            or item.get("content_id")
            or f"item_{i}"
        )
        title = item.get("title") or item.get("content") or ""
        desc = item.get("desc") or item.get("content_text") or ""
        results.append({
            "content_id": content_id,
            "platform": config.platform,
            "job_id": config.job_id,
            "content_type": "note",
            "sentiment": "neutral",
            "sentiment_score": 0.5,
            "topics": [],
            "entities": [],
            "risk_score": 0.0,
            "raw_content": f"{title} {desc}"[:2000],
            "analyzed_at": datetime.utcnow().isoformat(),
        })
    return results


def _baseline_from_history(historical: List[Dict]) -> Dict:
    if not historical:
        return {}
    counts = [h.get("count", 0) for h in historical]
    avg = sum(counts) / len(counts)
    variance = sum((c - avg) ** 2 for c in counts) / max(len(counts), 1)
    return {
        "avg_count": avg,
        "std_count": variance ** 0.5,
        "avg_sentiment": sum(h.get("avg_sentiment", 0.5) for h in historical) / len(historical),
    }


async def _save_analysis_results(config: JobConfig, results: List[Dict]) -> None:
    async with get_session() as session:
        for r in results:
            session.add(
                AnalysisResult(
                    content_id=r.get("content_id", ""),
                    platform=config.platform,
                    job_id=config.job_id,
                    content_type=r.get("content_type", "note"),
                    sentiment=r.get("sentiment"),
                    sentiment_score=r.get("sentiment_score"),
                    topics=r.get("topics"),
                    summary=r.get("summary"),
                    entities=r.get("entities"),
                    risk_score=r.get("risk_score", 0.0),
                    raw_content=r.get("raw_content"),
                )
            )


async def _save_alerts(config: JobConfig, triggered) -> List[int]:
    ids = []
    async with get_session() as session:
        for t in triggered:
            row = Alert(
                rule_id=t.rule_id,
                rule_name=t.rule_name,
                severity=t.severity,
                platform=config.platform,
                job_id=config.job_id,
                title=f"[{t.severity}] {t.rule_name}",
                summary=t.summary,
                matched_items=t.matched_items[:20],
                channels_sent=[],
            )
            session.add(row)
            await session.flush()
            ids.append(row.id)
    return ids


async def _resolve_channels(rule_id: str) -> List[str]:
    from ai_monitor.store.models import RuleConfig

    channels: List[str] = []
    async with get_session() as session:
        result = await session.execute(
            select(RuleConfig).where(RuleConfig.rule_id == rule_id)
        )
        row = result.scalar_one_or_none()
        if row and row.notification_channels:
            channels = list(row.notification_channels)
    if not channels:
        channels = ["console"]
    if await _feishu_notification_enabled() and "feishu" not in channels:
        channels.append("feishu")
    return channels


async def _feishu_notification_enabled() -> bool:
    from ai_monitor.config.settings import get_settings
    from ai_monitor.store.models import NotificationConfig

    async with get_session() as session:
        result = await session.execute(
            select(NotificationConfig).where(NotificationConfig.channel_name == "feishu")
        )
        row = result.scalar_one_or_none()
        if row and row.is_enabled:
            return True

    return bool(get_settings().FEISHU_WEBHOOK_URL)


async def _mark_channels_sent(alert_id: int, channels: List[str]) -> None:
    async with get_session() as session:
        row = await session.get(Alert, alert_id)
        if row:
            row.channels_sent = channels


async def _touch_job_run(
    job_id: str,
    status: str,
    items_crawled: int,
    alerts: int,
) -> None:
    async with get_session() as session:
        result = await session.execute(
            select(MonitoringJob).where(MonitoringJob.job_id == job_id)
        )
        job = result.scalar_one_or_none()
        if job:
            job.last_run_at = datetime.utcnow()
            job.last_run_status = status


def _sample_text(matched_items: List[Dict]) -> str:
    if not matched_items:
        return ""
    item = matched_items[0]
    title = item.get("title") or item.get("content") or ""
    desc = item.get("desc") or item.get("content") or ""
    return f"{title} {desc}"[:200]
