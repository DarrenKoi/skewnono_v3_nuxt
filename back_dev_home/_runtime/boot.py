"""Startup reporting for provider resolution.

With presence detection there is no .env line and no tracked set to read, so
this table is the moment-of-truth record of which pages are serving 사내 data.
The logger itself lives in ``_logging/providers.py`` — see that module for why
it carries its own handler.
"""

from back_dev_home._logging.providers import install_provider_logging, logger
from back_dev_home._runtime.data_provider import get_mode, resolve_all
from back_dev_home._runtime.office_template import stale_adapters
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
    _warn_about_stale_adapters(office)


def _warn_about_stale_adapters(office: int) -> None:
    """Name any office.py that is provably an out-of-date copy.

    The table above says which features serve 사내 data; it cannot say that
    one of them is running last week's adapter. A stale copy is invisible by
    construction — office.py is gitignored, so `git pull` moves the template
    and leaves the running code behind, and the feature keeps answering 200.

    Only checked when this process actually serves office data somewhere.
    A home instance runs mock no matter how old its copies are, so warning
    there would be noise — and it would pay the git cost of the check on
    every boot to say nothing. `scripts/adapters/sync_office_adapters` is the home-side
    way to ask the same question, on purpose rather than at startup.

    Best-effort by design: this is a diagnostic, and a diagnostic that can
    stop the app from booting is worse than no diagnostic at all.
    """
    if not office:
        return

    try:
        stale = stale_adapters()
    except Exception:  # noqa: BLE001 — never let a warning break startup
        logger.debug("stale-adapter check skipped", exc_info=True)
        return

    for adapter, note in stale:
        logger.warning(
            "  STALE office.py: %s (%s) — this instance serves office data, "
            "and a stale copy runs OLD adapter code against it. Refresh with: "
            "python -m scripts.adapters.sync_office_adapters %s",
            adapter.slug,
            note,
            adapter.name,
        )
