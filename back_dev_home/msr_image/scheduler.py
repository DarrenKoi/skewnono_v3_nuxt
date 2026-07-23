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
    # Idempotent + test-safe: create_app() runs many times across a test suite
    # (and under the dev reloader). Starting a fresh BackgroundScheduler each
    # time would accumulate live threads all firing purge_now. Skip under
    # testing, and never start a second one on the same app.
    if app.testing or "msr_image_scheduler" in app.extensions:
        return app.extensions.get("msr_image_scheduler")

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
