# -*- coding: utf-8 -*-
"""MonitoringJob - wraps MediaCrawler's CrawlerFactory for scheduled execution."""

import os
import sys
from pathlib import Path

MEDIACRAWLER_PATH = str(Path(__file__).resolve().parent.parent.parent / "MediaCrawler")
if MEDIACRAWLER_PATH not in sys.path:
	sys.path.insert(0, MEDIACRAWLER_PATH)

import asyncio
import importlib
from datetime import datetime

from ai_monitor.scheduler.base import JobConfig, JobRunResult


class MonitoringJob:
	"""Wraps a MediaCrawler crawler in a scheduled job.

	Sets MediaCrawler's module-level config before each run,
	then calls CrawlerFactory.create_crawler().start().
	"""

	def __init__(self, config: JobConfig):
		self.config = config

	async def execute(self) -> JobRunResult:
		if self.config.source_type in ("github", "gitee"):
			from ai_monitor.repo_watch.service import check_repo_update

			return await check_repo_update(self.config)

		# Change to MediaCrawler directory so relative paths (libs/, data/) resolve correctly
		_mc_dir = Path(MEDIACRAWLER_PATH)
		_orig_cwd = Path.cwd()
		os.chdir(str(_mc_dir))
		try:
			# Reload config module to get fresh state
			import config as mc_config
			importlib.reload(mc_config)

			# Override MediaCrawler module-level config
			mc_config.PLATFORM = self.config.platform
			mc_config.KEYWORDS = self.config.keywords
			mc_config.CRAWLER_TYPE = self.config.crawler_type
			mc_config.START_PAGE = self.config.start_page
			mc_config.CRAWLER_MAX_NOTES_COUNT = self.config.max_notes
			mc_config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = self.config.max_comments
			mc_config.ENABLE_GET_COMMENTS = self.config.enable_comments
			mc_config.ENABLE_GET_SUB_COMMENTS = self.config.enable_sub_comments
			mc_config.SAVE_DATA_OPTION = self.config.save_option
			mc_config.HEADLESS = self.config.headless
			mc_config.CDP_HEADLESS = self.config.headless
			mc_config.LOGIN_TYPE = self.config.login_type
			if self.config.cookies:
				mc_config.COOKIES = self.config.cookies

			result = JobRunResult(
				job_id=self.config.job_id,
				platform=self.config.platform,
				status="success",
			)

			# Directly import target crawler to avoid triggering all platform imports
			_PLATFORM_CRAWLERS = {
				"xhs": ("media_platform.xhs", "XiaoHongShuCrawler"),
				"dy": ("media_platform.douyin", "DouYinCrawler"),
				"ks": ("media_platform.kuaishou", "KuaishouCrawler"),
				"bili": ("media_platform.bilibili", "BilibiliCrawler"),
				"wb": ("media_platform.weibo", "WeiboCrawler"),
				"tieba": ("media_platform.tieba", "TieBaCrawler"),
				"zhihu": ("media_platform.zhihu", "ZhihuCrawler"),
			}
			_mod_path, _cls_name = _PLATFORM_CRAWLERS[self.config.platform]
			_mod = importlib.import_module(_mod_path)
			_crawler_cls = getattr(_mod, _cls_name)
			crawler = _crawler_cls()
			try:
				await crawler.start()
			except Exception as e:
				# Crawler may be blocked by platform (e.g. comment rate limit)
				# but content JSONL may already be written — don't fail yet
				print(f"[jobs] Crawler warning (non-fatal): {e}")

			# _crawled_count is not set by MediaCrawler, always read from JSONL

			from ai_monitor.config.settings import get_settings
			from ai_monitor.crawler.jsonl_loader import load_crawled_contents
			from ai_monitor.workflow.social_monitor import run_social_monitor_pipeline

			settings = get_settings()
			mc_root = Path(settings.MEDIACRAWLER_PATH)
			from ai_monitor.crawler.jsonl_loader import load_crawled_with_comments

			items = load_crawled_with_comments(
				self.config.platform,
				self.config.crawler_type,
				mc_root,
				include_comments=self.config.enable_comments,
			)
			if not items:
				result.status = "success"
				result.error_message = (
					"Crawler finished but no JSONL content found for today. "
					"Check MediaCrawler login/cookies and data output path."
				)
			else:
				result.items_crawled = len(items)
				result = await run_social_monitor_pipeline(
					self.config, items, result
				)

		except Exception as e:
			result.status = "failed"
			result.error_message = str(e)
		finally:
			os.chdir(str(_orig_cwd))

		return result
