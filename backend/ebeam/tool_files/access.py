"""Who may browse tool files: admins, members of the allowed teams, and people
an admin granted by empno.

The teams are the default and live in code. A person grant covers whoever
works on tool files from outside them, typically someone dispatched to another
team whose directory dept_nm no longer matches.

Kept free of Flask and of the store so the recipe bulk-copy program can ask
the same question (see .scratch/recipe-bulk-copy/handoff.md).
"""

from collections.abc import Callable, Mapping

from backend._auth.admin import TRUSTED_SOURCES, is_admin
from backend._auth.directory import Probe
from backend.ebeam.tool_files.contracts import Grant, Request, Verdict

# user-confirmed 2026-10-20. Matched exactly against the directory's dept_nm;
# OFFICE-VERIFY that these are its spellings (no "팀" suffix, spacing, case).
ALLOWED_TEAMS = (
    "DRAM MI개발",
    "NAND MI개발",
    "DRAM Metrology기술",
    "NAND Metrology기술",
    "기반기술전략",
)


def norm_empno(empno: str) -> str:
    return empno.strip().upper()


def decide(
    source: str | None,
    empno: str | None,
    probe: Callable[[], Probe],
    grants: Callable[[], Mapping[str, Grant] | None],
    requests: Callable[[], Mapping[str, Request] | None],
) -> Verdict:
    """Every lookup is lazy, called only when an earlier row has not decided:
    an admin costs no round trip and a team member never reads the store, so
    a store outage shuts out only the people who need it. ``grants()`` and
    ``requests()`` return None when the store cannot be read; both are keyed
    by the normalised empno. A person grant still lets its holder in while
    the directory is down."""
    if source not in TRUSTED_SOURCES or not empno:
        return "untrusted_identity"
    if is_admin(empno):
        return "granted"
    found = probe()
    dept_nm = found.member["dept_nm"] if found.member else None
    if dept_nm and dept_nm.strip() in ALLOWED_TEAMS:
        return "granted"
    stored = grants()
    if stored is None:
        return "directory_unavailable" if found.status == "unavailable" else "store_unavailable"
    if norm_empno(empno) in stored:
        return "granted"
    if found.status == "unavailable":
        return "directory_unavailable"
    pending = requests()
    if pending is None:
        return "store_unavailable"
    own = pending.get(norm_empno(empno))
    return own["status"] if own else "none"
