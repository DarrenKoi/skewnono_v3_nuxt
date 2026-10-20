"""Who may browse tool files: admins, plus members of the allowed teams.

Kept free of Flask so the recipe bulk-copy program can ask the same question
(see .scratch/recipe-bulk-copy/handoff.md).
"""

from collections.abc import Callable

from backend._auth.admin import TRUSTED_SOURCES, is_admin
from backend._auth.directory import Probe
from backend.ebeam.tool_files.contracts import Verdict

# user-confirmed 2026-10-20. Matched exactly against the directory's dept_nm;
# OFFICE-VERIFY that these are its spellings (no "팀" suffix, spacing, case).
ALLOWED_TEAMS = (
    "DRAM MI개발",
    "NAND MI개발",
    "DRAM Metrology기술",
    "NAND Metrology기술",
    "기반기술전략",
)


def decide(source: str | None, empno: str | None, probe: Callable[[], Probe]) -> Verdict:
    """``probe`` is lazy: an admin never costs a directory round trip."""
    if source not in TRUSTED_SOURCES or not empno:
        return "untrusted_identity"
    if is_admin(empno):
        return "granted"
    found = probe()
    if found.status == "unavailable":
        return "directory_unavailable"
    dept_nm = found.member["dept_nm"] if found.member else None
    return "granted" if dept_nm and dept_nm.strip() in ALLOWED_TEAMS else "none"
