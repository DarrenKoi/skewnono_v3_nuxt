"""Office adapter for access-control policy data — NOT CONNECTED YET.

Implement all six functions here against the office Redis exception store
— is_blocked/list_exceptions/add_exception/remove_exception AND
record_denied/list_denied. All six must read/write the SAME store:
is_blocked must see a grant written by this module's add_exception, or the
enforcement path (back_dev_home/_auth/middleware.py) breaks the moment
SKEWNONO_ACCESS_CONTROL_PROVIDER=office is set. Normalize CRUD results to
access_control/contracts.py shapes; see access_control/MIGRATION.md's
"Enforcement path" section for details.

IMPORTANT: when Redis is unreachable, mutating functions (add_exception,
remove_exception) MUST raise StoreUnavailableError — imported from
providers.mock, not redefined here — so routes.py's existing
`except (StoreUnavailableError, OSError)` handling keeps mapping the
failure to a 503 instead of a raw 500. See MIGRATION.md's "StoreUnavailableError
rule" section.
"""

from back_dev_home.access_control.providers.mock import StoreUnavailableError

__all__ = ["StoreUnavailableError"]


def _not_connected():
    raise NotImplementedError(
        "The access_control office adapter has not been connected yet. "
        "Set SKEWNONO_ACCESS_CONTROL_PROVIDER=mock until it is ready."
    )


def is_blocked(*args, **kwargs):
    return _not_connected()


def list_exceptions(*args, **kwargs):
    return _not_connected()


def add_exception(*args, **kwargs):
    return _not_connected()


def remove_exception(*args, **kwargs):
    return _not_connected()


def record_denied(*args, **kwargs):
    return _not_connected()


def list_denied(*args, **kwargs):
    return _not_connected()
