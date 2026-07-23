"""Environment-driven config for msr_image (both phases read the same keys)."""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    raw = env.get(key, "").strip()
    return int(raw) if raw.lstrip("-").isdigit() else default


@dataclass(frozen=True)
class ImageConfig:
    ftp_user: str = "hitachi"
    ftp_password: str = "hid"
    ftp_port: int = 21
    ftp_concurrency: int = 6
    ftp_timeout: float = 8.0
    allowed_subnets: list[str] = field(default_factory=list)
    cache_dir: str = "var/image_cache"
    cache_bucket: str | None = None
    cache_prefix: str = "image_cache/"
    ttl_hours: int = 72
    purge_hour: int = 3
    job_ttl: int = 3600
    max_jobs: int = 2


def load_config(env: Mapping[str, str] | None = None) -> ImageConfig:
    env = os.environ if env is None else env
    subnets_raw = env.get("SKEWNONO_TOOL_SUBNETS", "").strip()
    subnets = [s.strip() for s in subnets_raw.split(",") if s.strip()]
    return ImageConfig(
        ftp_user=env.get("SKEWNONO_TOOL_FTP_USER", "").strip() or "hitachi",
        ftp_password=env.get("SKEWNONO_TOOL_FTP_PASSWORD", "").strip() or "hid",
        ftp_port=_int(env, "SKEWNONO_TOOL_FTP_PORT", 21),
        ftp_concurrency=_int(env, "SKEWNONO_TOOL_FTP_CONCURRENCY", 6),
        ftp_timeout=float(env.get("SKEWNONO_TOOL_FTP_TIMEOUT", "8") or 8),
        allowed_subnets=subnets,
        cache_dir=env.get("IMAGE_CACHE_DIR", "").strip() or "var/image_cache",
        cache_bucket=env.get("SKEWNONO_IMAGE_CACHE_BUCKET", "").strip() or None,
        cache_prefix=env.get("SKEWNONO_IMAGE_CACHE_PREFIX", "").strip() or "image_cache/",
        ttl_hours=_int(env, "IMAGE_CACHE_TTL_HOURS", 72),
        purge_hour=_int(env, "IMAGE_CACHE_PURGE_HOUR", 3),
        job_ttl=_int(env, "SKEWNONO_MSR_IMAGE_JOB_TTL", 3600),
        max_jobs=_int(env, "SKEWNONO_MSR_IMAGE_MAX_JOBS", 2),
    )
