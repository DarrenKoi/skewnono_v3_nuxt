"""Who may browse tool files: the spec's verdict table as one pure function.

Kept free of Flask and of the store so the recipe bulk-copy program can ask
the same question (see .scratch/recipe-bulk-copy/handoff.md).
"""

from collections.abc import Callable, Mapping

from backend._auth.admin import is_admin
from backend._auth.directory import Probe
from backend._auth.provider import SOURCE_COOKIE, SOURCE_LOCAL
from backend.ebeam.tool_files.contracts import Grant, Verdict

_TRUSTED_SOURCES = frozenset({SOURCE_COOKIE, SOURCE_LOCAL})


def emp_key(empno: str) -> str:
    return f"emp:{empno.strip().upper()}"


def team_key(dept_nm: str) -> str:
    return f"team:{dept_nm.strip()}"


def decide(
    source: str | None,
    empno: str | None,
    grants: Callable[[], Mapping[str, Grant] | None],
    probe: Callable[[], Probe],
) -> Verdict:
    """Both lookups are lazy, called only when an earlier row has not decided:
    an admin keeps access through a store outage, and an empno grant never
    costs a directory round trip. ``grants()`` returns None when the store
    cannot be read."""
    if source not in _TRUSTED_SOURCES or not empno:
        return "untrusted_identity"
    if is_admin(empno):
        return "granted"
    stored = grants()
    if stored is None:
        return "store_unavailable"
    if emp_key(empno) in stored:
        return "granted"
    found = probe()
    if found.status == "unavailable":
        return "directory_unavailable"
    dept_nm = found.member["dept_nm"] if found.member else None
    if dept_nm and team_key(dept_nm) in stored:
        return "granted"
    return "none"
