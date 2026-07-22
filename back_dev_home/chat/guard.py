"""Office egress guard for the chat LLM client.

In office mode the app must fail closed: a request whose resolved host is a
known public LLM gateway is refused before any byte leaves the process, so the
company's network monitor is never the thing that catches the leak. Home/mock
mode is unaffected — OpenRouter stays reachable, which is the point of the
offline home phase.

The policy is a blocklist: known public gateways are blocked by name, any other
host is allowed. ``CHAT_BLOCKED_HOSTS`` can only add hosts, never remove them,
so configuration can only tighten the guard.
"""

import logging
import os
from urllib.parse import urlparse

from back_dev_home._runtime.data_provider import get_mode

logger = logging.getLogger(__name__)

DEFAULT_BLOCKED_HOSTS: frozenset[str] = frozenset(
    {
        "openrouter.ai",
        "api.openai.com",
        "api.anthropic.com",
        "generativelanguage.googleapis.com",
        "api.groq.com",
        "api.mistral.ai",
        "api.together.ai",
        "api.cohere.com",
        "api.perplexity.ai",
        "api.deepseek.com",
        "api.x.ai",
    }
)


class ChatEgressBlocked(Exception):
    """Raised when office mode refuses an outbound call to a public gateway.

    Defined here (not in ``llm.py``) so ``guard`` never imports ``llm`` and no
    import cycle forms.
    """

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def get_blocked_hosts() -> set[str]:
    """Return the default blocklist merged with ``CHAT_BLOCKED_HOSTS``, lowercased."""
    hosts = {h.lower() for h in DEFAULT_BLOCKED_HOSTS}
    raw = os.environ.get("CHAT_BLOCKED_HOSTS")
    if raw:
        hosts |= {h.strip().lower() for h in raw.split(",") if h.strip()}
    return hosts


def host_is_blocked(host: str, blocked: set[str]) -> bool:
    """True when ``host`` equals a blocked host or is a subdomain of one."""
    host = host.lower()
    return any(host == b or host.endswith("." + b) for b in blocked)


def enforce_egress_policy(base_url: str) -> None:
    """In office mode, raise ``ChatEgressBlocked`` if ``base_url``'s host is blocked.

    Keyed on the MODE, not on ``get_data_provider("chat")``. Egress is a
    network question — am I on the company network? — not an adapter-readiness
    question. Those were conflated before providers split the two, and the
    conflation made this guard inert exactly where it matters: chat is parked,
    so it was never in the old ``OFFICE_READY`` set, so at the office
    ``get_data_provider("chat")`` returned ``mock`` and this function returned
    early without checking anything. The mode is ``office`` on an office host
    whether or not chat has a storage adapter.
    """
    if get_mode() != "office":
        return
    host = (urlparse(base_url).hostname or "").lower()
    if host and host_is_blocked(host, get_blocked_hosts()):
        message = (
            f"Outbound chat request to {host!r} is blocked in office mode. "
            "Configure an approved internal LLM gateway via CHAT_BASE_URL."
        )
        logger.warning("chat egress blocked: %s", host)
        raise ChatEgressBlocked(message)
