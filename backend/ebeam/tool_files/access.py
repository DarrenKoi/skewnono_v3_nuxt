"""Who may browse tool files: the spec's verdict table as one pure function.

Kept free of Flask and of the store so the recipe bulk-copy program can ask
the same question (see .scratch/recipe-bulk-copy/handoff.md).
"""

from collections import Counter
from collections.abc import Callable, Iterable, Mapping

from backend._auth.admin import TRUSTED_SOURCES, is_admin
from backend._auth.directory import Probe
from backend.ebeam.tool_files.contracts import Grant, Request, Teams, Verdict


def norm_empno(empno: str) -> str:
    return empno.strip().upper()


def emp_key(empno: str) -> str:
    return f"emp:{norm_empno(empno)}"


def team_key(dept_nm: str) -> str:
    return f"team:{dept_nm.strip()}"


def team_counts(depts: Iterable[str | None], complete: bool) -> Teams:
    """Members per team from every member's dept_nm (blank ones skipped)."""
    counts = Counter(d for d in depts if d)
    return {
        "teams": [{"dept_nm": d, "members": n} for d, n in sorted(counts.items())],
        "complete": complete,
    }


def cleared_by_team(request: Request, dept_nm: str) -> bool:
    """Does granting ``dept_nm`` settle this request? Pending ones of that team only."""
    return request.get("status") == "pending" and request.get("dept_nm") == dept_nm


def decide(
    source: str | None,
    empno: str | None,
    grants: Callable[[], Mapping[str, Grant] | None],
    probe: Callable[[], Probe],
    requests: Callable[[], Mapping[str, Request] | None],
) -> Verdict:
    """Every lookup is lazy, called only when an earlier row has not decided:
    an admin keeps access through a store outage, an empno grant never costs a
    directory round trip, and nobody granted reads the requests. ``grants()``
    and ``requests()`` return None when the store cannot be read; requests are
    keyed by the normalised empno."""
    if source not in TRUSTED_SOURCES or not empno:
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
    pending = requests()
    if pending is None:
        return "store_unavailable"
    own = pending.get(norm_empno(empno))
    return own["status"] if own else "none"
