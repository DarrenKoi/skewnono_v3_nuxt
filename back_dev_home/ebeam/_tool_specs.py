"""Per-tool constants for Hitachi e-beam shared features.

CD-SEM and HV-SEM share the same backend logic but differ in equipment
pools. Tool family comes from the model code's SERIES PREFIX — CG/GT are
CD-SEM, TP is HV-SEM (user-confirmed 2026-07-24) — which is what
`model_to_tool_type()` below and `classifyToolType()` in
`front-dev-home/app/composables/useSemListApi.ts` both apply.

Neither list in `TOOL_SPECS` is a classifier. `eqp_models` used to be one,
and that was a bug: it holds codes invented so the mocks could fabricate
plausible rows, so real office tools were being judged against made-up data.
Any genuine series member absent from it resolved to None and was dropped
from both tabs — silently, because a filtered-to-empty result is still a
valid response. That emptied the office "PPID 미접속 장비" panel for 8 tools
(2026-07-24). Add codes here freely for mock realism; classification no
longer depends on the list being complete.

`eqp_prefixes` is NOT a classifier either (user-confirmed 2026-07-22). A real
eqp_id does carry information — in the M-fabs a leading number in front of
`MCD` identifies the fab — but tool FAMILY is not part of it: `MCD` alone
spans CD-SEM, HV-SEM, VeritySEM, and Provision. The lists below exist only
so the mocks can fabricate plausible-looking ids.

This is precisely why `sem_list` is the roster of record. An eqp_id is a
lookup key, not a description: resolve a tool through its sem_list row and
classify from that row's `eqp_model_cd` (`model_to_tool_type()`, mirrored by
`classifyToolType()` in useSemListApi.ts). Never parse the id itself — see
`lateral_recipe/providers/office_example.py`, which takes versions from its
own index but the tool roster from `sem_list.data.get_sem_list()` for the
same reason.
"""

from typing import Literal, TypedDict


ToolSlug = Literal["cdsem", "hvsem"]
ToolType = Literal["cd-sem", "hv-sem"]


class ToolSpec(TypedDict):
    eqp_models: list[str]
    eqp_prefixes: list[str]


# CD-SEM scope: Hitachi CG-series and GT-series.
# HV-SEM scope: Hitachi TP-series only. Both families in scope today are
# Hitachi; AMAT enters only with PROVISION_*/VERITYSEM_*, deferred to 2027.
# BOTH lists below are mock fodder, not a family signal — see the module
# docstring. They are a sample of each series, never an exhaustive roster,
# and nothing classifies against them.
TOOL_SPECS: dict[ToolSlug, ToolSpec] = {
    "cdsem": {
        "eqp_models": ["CG6300", "CG6320", "CG6340", "CG6360", "CG6380", "GT2000", "GT2000S"],
        "eqp_prefixes": ["ECXDX", "ECDX", "HCDX"],
    },
    "hvsem": {
        "eqp_models": ["TP3000", "TP3500", "TP4000", "TP4500"],
        "eqp_prefixes": ["PCD", "MCD", "ACD", "VCD"],
    },
}

VALID_TOOL_SLUGS: frozenset[str] = frozenset(TOOL_SPECS.keys())

SLUG_TO_TOOL_TYPE: dict[ToolSlug, ToolType] = {
    "cdsem": "cd-sem",
    "hvsem": "hv-sem",
}

# Tool family is the model code's SERIES PREFIX, not a fixed list of codes.
# `eqp_models` above is mock fodder, so classifying against it judged real
# office tools by invented data: any real series member the mock never
# imagined resolved to None and was dropped from both tabs. Prefixes are the
# vendor's own series split (user-confirmed 2026-07-24) and match
# `classifyToolType()` in front-dev-home/app/composables/useSemListApi.ts.
_TOOL_TYPE_BY_PREFIX: tuple[tuple[str, ToolType], ...] = (
    ("CG", "cd-sem"),
    ("GT", "cd-sem"),
    ("TP", "hv-sem"),
)


def model_to_tool_type(eqp_model_cd: str) -> ToolType | None:
    """Classify a model code, or None when it is not a CD/HV-SEM tool.

    None is load-bearing: AMAT VeritySEM/Provision are their own tool types
    (deferred to 2027) and every CD/HV-scoped view filters on this returning
    None for them.

    Normalizes case and surrounding whitespace first — parquet/Redis text
    cells carry both, and an unclassified tool vanishes from the UI without
    raising, so a stray space must not silently delete a row.
    """
    code = str(eqp_model_cd).strip().upper()
    for prefix, tool_type in _TOOL_TYPE_BY_PREFIX:
        if code.startswith(prefix):
            return tool_type
    return None


def resolve_tool_type_from_slug(tool_slug: str) -> ToolType | None:
    slug = tool_slug.strip().lower()
    if slug in VALID_TOOL_SLUGS:
        return SLUG_TO_TOOL_TYPE[slug]  # type: ignore[index]
    return None
