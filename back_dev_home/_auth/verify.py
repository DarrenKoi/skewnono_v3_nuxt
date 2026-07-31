"""Does the name this person typed match the one the directory holds?

Deliberately pure — no Flask, no Redis, no request. Home fabricates member
rows, so verification would never execute here if it lived in the route, and
would meet a real ``members`` hash for the first time on the cloud. That is the
mock blind spot ``CLAUDE.md`` warns about, closed by making the logic testable
without the thing that is missing.

**Exactly one outcome rejects**: the directory knew this person and the name
was wrong. "Cannot check" and "checked and wrong" are opposite answers, and
collapsing them would deny access on the strength of our own outage — or, for
``absent``, on the strength of a row ``directory.py`` itself documents as
ordinarily missing for contractors and service accounts.
"""

from __future__ import annotations

from typing import NamedTuple, Optional

from .directory import Probe


class Decision(NamedTuple):
    """What to do with a declaration.

    ``emp_nm`` is the name to STORE: the directory's spelling when we verified
    against it, the entered one when we could not. It is None only on a
    rejection — an accepted employee number with no name attached would be
    exactly the unattributable traffic this feature exists to fix.
    """

    accept: bool
    verified: bool
    emp_nm: Optional[str]
    reason: str  # "match" | "mismatch" | "absent" | "unavailable"


def names_match(entered: str, directory: Optional[str]) -> bool:
    """Exact match after trimming the ends.

    Korean names have no case, so there is no case normalization to do.
    Internal spacing is NOT collapsed: two different people can differ by
    exactly that, and forgiving it would let one of them verify as the other.

    A missing directory name never matches. Otherwise empty input would sail
    through a partial row into a verified identity.
    """
    if not directory:
        return False
    return entered.strip() == directory.strip()


def decide(probe: Probe, entered_name: str) -> Decision:
    """Map a directory probe plus the entered name onto an outcome."""
    entered = entered_name.strip()

    if probe.status == "found":
        directory_name = probe.member["emp_nm"] if probe.member else None

        if names_match(entered, directory_name):
            return Decision(True, True, directory_name.strip(), "match")

        if not directory_name:
            # A partial row: an employee number and nothing to compare
            # against. Treated as an unverifiable directory rather than a
            # mismatch, because there was never a name here for the user to
            # get wrong.
            return Decision(True, False, entered or None, "unavailable")

        return Decision(False, False, None, "mismatch")

    # absent | unavailable — nothing to compare against, so nothing to reject.
    return Decision(True, False, entered or None, probe.status)
