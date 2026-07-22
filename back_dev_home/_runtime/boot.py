"""Startup reporting for provider resolution.

With presence detection there is no .env line and no tracked set to read, so
this table is the moment-of-truth record of which pages are serving 사내 data.
The logger itself lives in ``_logging/providers.py`` — see that module for why
it carries its own handler.
"""

from back_dev_home._logging.providers import install_provider_logging, logger
from back_dev_home._runtime.data_provider import get_mode, resolve_all
from back_dev_home._runtime.site import detect_site


def log_provider_table() -> None:
    install_provider_logging()
    rows = resolve_all()
    office = sum(1 for row in rows if row.provider == "office")
    logger.info(
        "data providers: site=%s mode=%s — %d/%d features on office",
        detect_site() or "unknown",
        get_mode(),
        office,
        len(rows),
    )
    width = max((len(row.feature) for row in rows), default=0)
    for row in rows:
        logger.info(
            "  %-*s  %-6s  %s", width, row.feature, row.provider, row.reason
        )
