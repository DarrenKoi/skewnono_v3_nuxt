"""SWAP SURFACE for short_links. Routes import only this module.

Both functions read/write ONE shared store, so they dispatch through the same
_provider() switch and MUST switch together: a link minted by office
create_short_link (Redis) has to be resolvable by office resolve_short_link, or
every link handed out after the switch 404s on open.
"""

from back_dev_home._runtime.data_provider import get_data_provider

from back_dev_home.short_links.contracts import ShortLink


__all__ = ["create_short_link", "resolve_short_link"]


def _provider():
    if get_data_provider("short_links") == "office":
        from back_dev_home.short_links.providers import office
        return office
    from back_dev_home.short_links.providers import mock
    return mock


def create_short_link(target: str) -> ShortLink:
    """Mint (or re-find) the short link for an ALREADY-VALIDATED target.

    Callers must pass the output of ``targets.normalize_target``; this layer
    does not re-check, because the store is the one place a target is trusted
    and a second gate here could drift out of step with the first.

    Idempotent: the same target always yields the same code.
    """
    return _provider().create_short_link(target)


def resolve_short_link(code: str) -> ShortLink | None:
    """Resolve a code, or ``None`` when it was never minted or has expired.

    ``None`` rather than an exception: a stale link is a routine outcome the
    route turns into a 404, not a server error.
    """
    return _provider().resolve_short_link(code)
