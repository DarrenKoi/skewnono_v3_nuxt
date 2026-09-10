"""The identity a user typed in for themselves.

This is the third step of the identity chain: weaker than a cookie the company
infrastructure set, stronger than nothing at all. It lives in Flask's signed
session so the `verified` flag cannot be flipped by the person it describes.

The signature protects the flag, not the fact. That an identity is *declared*
is guaranteed structurally — it came out of the session rather than out of a
`LASTUSER` cookie — and structure is not forgeable by editing a value. Only
`verified` needs the signature, because it is a claim about a check that
happened somewhere else.

**Every read is defensive.** A session written by an older version of this
code, a half-written row, or a payload of the wrong type must read as "nobody
declared". Two reasons: `read_declared` runs inside the app's first
`before_request`, where a raised exception answers index.html and every bundle
with it; and its result names a person in the activity log, where a
half-identity is worse than no identity because it looks like a real one.
"""

from __future__ import annotations

from typing import Optional, TypedDict

from flask import session

# The session key. Deliberately the only place this string appears — callers go
# through the three functions below, so the storage can change without a grep
# across the app.
SESSION_KEY = "declared"


class Declared(TypedDict):
    """An identity its own subject typed in.

    `emp_nm` is the directory's name when `verified` is True and the name the
    user entered when it is False — see `verify.decide`. `declared_from` is the
    IP the declaration was made from, recorded so that one employee number
    declared from many addresses (or many numbers from one) is visible.
    """

    empno: str
    emp_nm: Optional[str]
    verified: bool
    declared_from: Optional[str]


def _clean(value: object) -> Optional[str]:
    """Session value to trimmed str, or None when there is nothing there.

    None rather than "" because the SPA renders these directly: an empty string
    shows as a blank name, where None lets the UI fall back to the employee
    number.
    """
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def read_declared() -> Optional[Declared]:
    """The declared identity on this request's session, or None."""
    raw = session.get(SESSION_KEY)
    if not isinstance(raw, dict):
        return None

    empno = _clean(raw.get("empno"))
    if not empno:
        return None

    return {
        "empno": empno,
        "emp_nm": _clean(raw.get("emp_nm")),
        # `is True`, not bool(): the value round-trips through the session's
        # JSON serializer, and a leftover string like "no" is truthy. This flag
        # gates a security-relevant display, so only a real boolean counts.
        "verified": raw.get("verified") is True,
        "declared_from": _clean(raw.get("declared_from")),
    }


def write_declared(
    *,
    empno: str,
    emp_nm: Optional[str],
    verified: bool,
    declared_from: Optional[str],
) -> Declared:
    """Record a declared identity and return the stored shape.

    `session.permanent` is set here rather than in the app factory because it
    is a property of *this* session: the 30-day lifetime the factory configures
    applies only to sessions marked permanent, so setting it there alone would
    leave the configuration inert and the declaration would evaporate when the
    tab closed.
    """
    declared: Declared = {
        "empno": (empno or "").strip(),
        "emp_nm": _clean(emp_nm),
        "verified": verified is True,
        "declared_from": _clean(declared_from),
    }
    session[SESSION_KEY] = declared
    session.permanent = True
    return declared


def clear_declared() -> None:
    """Forget the declared identity. Safe when there is none."""
    session.pop(SESSION_KEY, None)
