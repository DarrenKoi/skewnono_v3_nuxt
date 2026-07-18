# TEMPLATE — copy to office.py at the office, then implement the function body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office adapter for api_tokens — NOT CONNECTED YET.

Implement all five functions here against the office Redis token store —
create_token/list_tokens/revoke_token AND find_by_plaintext/
touch_last_used. All five must read/write the SAME store: find_by_plaintext
must be able to resolve a token created by this module's create_token, or
bearer-token auth (back_dev_home/_auth/middleware.py) breaks the moment
SKEWNONO_API_TOKENS_PROVIDER=office is set. Normalize CRUD results to
api_tokens/contracts.py shapes; see api_tokens/MIGRATION.md's "Auth path"
section for find_by_plaintext's required return shape.
"""


def _not_connected():
    raise NotImplementedError(
        "The api_tokens office adapter has not been connected yet. "
        "Set SKEWNONO_API_TOKENS_PROVIDER=mock until it is ready."
    )


def create_token(*args, **kwargs):
    return _not_connected()


def list_tokens(*args, **kwargs):
    return _not_connected()


def revoke_token(*args, **kwargs):
    return _not_connected()


def find_by_plaintext(*args, **kwargs):
    return _not_connected()


def touch_last_used(*args, **kwargs):
    return _not_connected()