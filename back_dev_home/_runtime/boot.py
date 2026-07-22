"""Startup reporting for provider resolution.

With presence detection there is no .env line and no tracked set to read, so
this table is the moment-of-truth record of which pages are serving 사내 data.
It carries its own handler and level, copying the ``skewnono.activity``
pattern in ``_logging/activity.py``: ``app.logger`` inherits WARNING from the
root logger, so an INFO table would be invisible in exactly the deployment
where someone needs it.
"""

import logging

from back_dev_home._runtime.data_provider import get_mode, resolve_all
from back_dev_home._runtime.site import detect_site


logger = logging.getLogger("skewnono.providers")

if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def log_provider_table() -> None:
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
