"""Office adapter for api_tokens — NOT CONNECTED YET.

Implement create_token/list_tokens/revoke_token in api_tokens/MIGRATION.md
against the office Redis token store. Normalize every result to
api_tokens/contracts.py shapes.

find_by_plaintext and touch_last_used are NOT part of this seam: the
bearer-token auth path (back_dev_home/_auth/middleware.py) always calls the
mock module's versions directly via api_tokens/data.py, regardless of
SKEWNONO_API_TOKENS_PROVIDER — see the note in data.py and MIGRATION.md.
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
