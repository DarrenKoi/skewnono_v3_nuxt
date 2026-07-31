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

from typing import Literal, NamedTuple, Optional

from .directory import Probe

# Why a declaration turned out the way it did. Every other property of the
# outcome follows from this one value, so it is the only thing stored.
Reason = Literal["match", "mismatch", "absent", "unavailable", "no_name"]


class Decision(NamedTuple):
    """What to do with a declaration.

    ``accept`` and ``verified`` are DERIVED rather than stored. They are each a
    function of ``reason``, and holding three fields with one degree of freedom
    between them invites a later edit that sets two of them consistently and
    the third not — a bug that would read as "accepted but unverified" or,
    worse, the reverse.

    ``emp_nm`` is the name to STORE: the directory's spelling when we verified
    against it, the entered one when we could not. It is None only on a
    rejection — an accepted employee number with no name attached would be
    exactly the unattributable traffic this feature exists to fix.
    """

    reason: Reason
    emp_nm: Optional[str]

    @property
    def accept(self) -> bool:
        """Only a name that contradicts a real directory row is refused."""
        return self.reason != "mismatch"

    @property
    def verified(self) -> bool:
        """True only when a directory name was present AND agreed."""
        return self.reason == "match"


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
            return Decision("match", directory_name.strip())

        if not directory_name:
            # A partial row: an employee number and nothing to compare
            # against. Accepted like any other unverifiable case, because
            # there was never a name here for the user to get wrong — but it
            # gets its OWN reason rather than borrowing "unavailable", which
            # would claim the directory failed to answer when in fact it
            # answered with an incomplete row.
            return Decision("no_name", entered or None)

        return Decision("mismatch", None)

    # absent | unavailable — nothing to compare against, so nothing to reject.
    return Decision(probe.status, entered or None)
