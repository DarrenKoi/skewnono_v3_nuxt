"""Stable contracts for the chat scope gate."""

from typing import Literal, TypedDict


class ScopeDecision(TypedDict):
    """Whether this query is one SKEWNONO chat answers.

    Three states, not four. ``mixed`` was removed on 2026-09-01 along with the
    clause extraction behind it — see ``policy.py``. A query carrying both a
    work topic and an off-topic one is now simply ``in_scope``: the work part
    gets answered and the rest finds no evidence, which is a better outcome
    than the mangled question the extractor used to forward.
    """

    status: Literal["in_scope", "out_of_scope", "unsafe"]
    reason_code: str
