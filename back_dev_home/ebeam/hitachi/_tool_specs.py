"""Per-tool constants for Hitachi e-beam shared features.

CD-SEM and HV-SEM share the same backend logic but differ in equipment
pools. `eqp_models` is the single source of truth for which models belong to
each tool family — `classifyToolType()` in
`front-dev-home/app/composables/useSemListApi.ts` mirrors the same split.

`eqp_prefixes` is NOT a classifier (user-confirmed 2026-07-22). A real
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
# The `eqp_prefixes` below are mock-id fodder, not a family signal — see the
# module docstring. They are grouped here purely for the mocks' convenience.
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

_TOOL_TYPE_BY_MODEL: dict[str, ToolType] = {
    model: SLUG_TO_TOOL_TYPE[slug]
    for slug, spec in TOOL_SPECS.items()
    for model in spec["eqp_models"]
}


def model_to_tool_type(eqp_model_cd: str) -> ToolType | None:
    return _TOOL_TYPE_BY_MODEL.get(eqp_model_cd)


def resolve_tool_type_from_slug(tool_slug: str) -> ToolType | None:
    slug = tool_slug.strip().lower()
    if slug in VALID_TOOL_SLUGS:
        return SLUG_TO_TOOL_TYPE[slug]  # type: ignore[index]
    return None
