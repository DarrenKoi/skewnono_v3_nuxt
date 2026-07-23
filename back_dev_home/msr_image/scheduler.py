"""Nightly cache purge. Home deletes disk files; office sweeps the MinIO cache
prefix by last_modified (MinioImageCache.purge). Duplicate runs are idempotent."""

import logging

from back_dev_home.msr_image import data
from back_dev_home.msr_image.cache import make_cache
from back_dev_home.msr_image.config import ImageConfig, load_config

logger = logging.getLogger(__name__)


def purge_now(cfg: ImageConfig | None = None) -> int:
    cfg = cfg or load_config()
    cache = make_cache(cfg, data.provider_name())
    removed = cache.purge(cfg.ttl_hours)
    logger.info("msr_image cache purge removed %d objects", removed)
    return removed


def start_purge_scheduler(app):
    from apscheduler.schedulers.background import BackgroundScheduler

    cfg = load_config()
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        purge_now,
        trigger="cron",
        hour=cfg.purge_hour,
        id="msr_image_cache_purge",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    app.extensions["msr_image_scheduler"] = scheduler
    return scheduler
