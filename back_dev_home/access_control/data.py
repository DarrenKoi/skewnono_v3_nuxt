"""SWAP SURFACE for X-ID access control. Routes and the auth middleware
import only this module.

All six functions — is_blocked, list_exceptions, add_exception,
remove_exception, record_denied, list_denied — read/write ONE shared
exception store (plus the in-memory denied-attempts ring buffer), so they
all dispatch through the same _provider() switch and MUST switch together.
is_blocked/record_denied back the enforcement path in
back_dev_home/_auth/middleware.py::_deny_if_blocked: a grant added via
office add_exception (Redis) has to be visible to an office is_blocked, or
switching SKEWNONO_ACCESS_CONTROL_PROVIDER=office while only the four
admin-CRUD functions were wired to office would silently reblock (or
silently unblock) members depending on which half of the store each
function reads. See MIGRATION.md's "Enforcement path" section.

BLOCKED_PREFIX and StoreUnavailableError are re-exported unswitched —
provider-independent policy/error type shared by both providers.
reset_for_tests and _store_path are mock-only (test support / this
provider's own file location), not part of the switch.
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.access_control.providers.mock import (
    BLOCKED_PREFIX,          # policy constant: provider-independent
    StoreUnavailableError,   # error type shared by both providers
    _store_path,             # test-only: mock's exception-file location
    reset_for_tests,         # dev/test-only: mock-only by design
)


__all__ = [
    "BLOCKED_PREFIX",
    "StoreUnavailableError",
    "is_blocked",
    "list_exceptions",
    "add_exception",
    "remove_exception",
    "record_denied",
    "list_denied",
    "reset_for_tests",
]


def _provider():
    if get_data_provider("access_control") == "office":
        from back_dev_home.access_control.providers import office
        return office
    from back_dev_home.access_control.providers import mock
    return mock


def is_blocked(user_id: str) -> bool:
    return _provider().is_blocked(user_id)


def list_exceptions() -> list[dict]:
    return _provider().list_exceptions()


def add_exception(user_id: str) -> dict:
    return _provider().add_exception(user_id)


def remove_exception(user_id: str) -> bool:
    return _provider().remove_exception(user_id)


def record_denied(user_id: str) -> None:
    return _provider().record_denied(user_id)


def list_denied() -> list[dict]:
    return _provider().list_denied()
