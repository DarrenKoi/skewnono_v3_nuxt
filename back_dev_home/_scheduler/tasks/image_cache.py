"""Nightly image-cache purge.

A thin call-through: home deletes disk files, office sweeps the MinIO cache
prefix by ``last_modified`` (``MinioImageCache.purge``). The deletion logic
itself stays in ``msr_image`` -- this module only names the job. Duplicate runs
are idempotent.

Relocated from ``msr_image/scheduler.py``, which mixed this body with its own
BackgroundScheduler. Scheduling policy now lives in ``_scheduler/registry.py``.
"""

import logging

from back_dev_home.msr_image import data
from back_dev_home.msr_image.cache import make_cache
from back_dev_home.msr_image.config import ImageConfig, load_config

logger = logging.getLogger("skewnono.scheduler")


def purge_image_cache(cfg: ImageConfig | None = None) -> int:
    cfg = cfg or load_config()
    cache = make_cache(cfg, data.provider_name())
    removed = cache.purge(cfg.ttl_hours)
    logger.info("image_cache purge removed %d objects", removed)
    return removed
