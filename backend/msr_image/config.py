"""Environment-driven config for msr_image (both phases read the same keys)."""

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass, field


_LOG = logging.getLogger(__name__)


def _accounts(env: Mapping[str, str], key: str) -> dict[str, tuple[str, str]]:
    """Parse ``KEY=user:password`` pairs into a per-tool credential map.

    ``SKEWNONO_TOOL_FTP_ACCOUNTS=M16=svc:pw,MCD1234=other:pw2``

    A KEY is a ``fab_name`` or an ``eqp_id`` -- the account varies by fab and by
    tool, never by vendor family (user-confirmed 2026-08-28), so there is no
    family axis here. Keys are upper-cased on both sides of the match: a case
    slip would otherwise resolve to the fleet default silently, which is the
    same wrong-account-not-an-error failure this whole mechanism exists to stop.

    A password may contain ``:`` (only the first splits); a KEY may not contain
    ``=``. Malformed entries are logged and skipped rather than raising -- a
    typo in one tool's entry must not take the whole feature down at import.
    """
    accounts: dict[str, tuple[str, str]] = {}
    for entry in env.get(key, "").split(","):
        entry = entry.strip()
        if not entry:
            continue
        name, sep, credential = entry.partition("=")
        user, colon, password = credential.partition(":")
        if not (sep and colon and name.strip() and user.strip()):
            _LOG.warning("%s: ignoring malformed entry %r", key, entry)
            continue
        accounts[name.strip().upper()] = (user.strip(), password)
    return accounts


def _int(env: Mapping[str, str], key: str, default: int) -> int:
    try:
        return int(env.get(key, "").strip())
    except ValueError:
        return default


def _float(env: Mapping[str, str], key: str, default: float) -> float:
    try:
        return float(env.get(key, "").strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class ImageConfig:
    ftp_user: str = "hitachi"
    ftp_password: str = "hid"
    ftp_port: int = 21
    ftp_concurrency: int = 6
    ftp_timeout: float = 8.0
    # Backstop for a tool that connects and then stalls mid-transfer. NOT the
    # dead-tool knob -- ftp_timeout bounds every socket op, so an offline tool
    # still fails in seconds no matter how large this is. It only has to be
    # bigger than a healthy connection's real work, which is why download_all
    # scales it by the number of files on the connection instead of using this
    # value flat (see providers/office_example.py:_host_timeout).
    ftp_host_timeout: float = 60.0
    # Ceiling for that scaling, because the HTTP-proxy transport has a hard one:
    # the proxy host's uWSGI kills a request at harakiri (75s in
    # ftp_handler/proxy/wsgi.ini, whose own comment says to raise it in lockstep
    # with host_timeout). A budget above harakiri gets the whole BATCH of specs
    # killed by uWSGI -- strictly worse than the single-host timeout it was
    # meant to avoid. 0 means uncapped, which is right for the direct transport.
    ftp_host_timeout_max: float = 0.0
    allowed_subnets: list[str] = field(default_factory=list)
    cache_dir: str = "var/image_cache"
    cache_bucket: str | None = None
    cache_prefix: str = "image_cache/"
    ttl_hours: int = 72
    purge_hour: int = 3
    job_ttl: int = 3600
    max_jobs: int = 2
    # fab_name or eqp_id -> (user, password). Empty means one account serves
    # the fleet, which is the state until AMAT tools land; see _accounts().
    ftp_accounts: dict[str, tuple[str, str]] = field(default_factory=dict)


def load_config(env: Mapping[str, str] | None = None) -> ImageConfig:
    env = os.environ if env is None else env
    subnets_raw = env.get("SKEWNONO_TOOL_SUBNETS", "").strip()
    subnets = [s.strip() for s in subnets_raw.split(",") if s.strip()]
    return ImageConfig(
        ftp_user=env.get("SKEWNONO_TOOL_FTP_USER", "").strip() or "hitachi",
        ftp_password=env.get("SKEWNONO_TOOL_FTP_PASSWORD", "").strip() or "hid",
        ftp_port=_int(env, "SKEWNONO_TOOL_FTP_PORT", 21),
        ftp_concurrency=_int(env, "SKEWNONO_TOOL_FTP_CONCURRENCY", 6),
        ftp_timeout=_float(env, "SKEWNONO_TOOL_FTP_TIMEOUT", 8.0),
        ftp_host_timeout=_float(env, "SKEWNONO_TOOL_FTP_HOST_TIMEOUT", 60.0),
        ftp_host_timeout_max=_float(env, "SKEWNONO_TOOL_FTP_HOST_TIMEOUT_MAX", 0.0),
        allowed_subnets=subnets,
        cache_dir=env.get("IMAGE_CACHE_DIR", "").strip() or "var/image_cache",
        cache_bucket=env.get("SKEWNONO_IMAGE_CACHE_BUCKET", "").strip() or None,
        cache_prefix=env.get("SKEWNONO_IMAGE_CACHE_PREFIX", "").strip() or "image_cache/",
        ttl_hours=_int(env, "IMAGE_CACHE_TTL_HOURS", 72),
        purge_hour=_int(env, "IMAGE_CACHE_PURGE_HOUR", 3),
        job_ttl=_int(env, "SKEWNONO_MSR_IMAGE_JOB_TTL", 3600),
        max_jobs=_int(env, "SKEWNONO_MSR_IMAGE_MAX_JOBS", 2),
        ftp_accounts=_accounts(env, "SKEWNONO_TOOL_FTP_ACCOUNTS"),
    )
