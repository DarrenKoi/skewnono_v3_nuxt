"""Per-tool constants for e-beam shared features across four tool families.

CD-SEM and HV-SEM (Hitachi) share the same backend logic but differ in
equipment pools. Tool family comes from the model code's SERIES PREFIX --
CG/GT are CD-SEM, TP is HV-SEM (user-confirmed 2026-07-24), VERITYSEM/
VERITY_SEM is AMAT VeritySEM, PROVISION is AMAT Provision -- which is what
`model_to_tool_type()` below and `classifyToolType()` in
`front-dev-home/app/composables/useSemListApi.ts` both apply.

Neither list in `TOOL_SPECS` is a classifier. `eqp_models` used to be one,
and that was a bug: it holds codes invented so the mocks could fabricate
plausible rows, so real office tools were being judged against made-up data.
Any genuine series member absent from it resolved to None and was dropped
from both tabs -- silently, because a filtered-to-empty result is still a
valid response. That emptied the office "PPID 미접속 장비" panel for 8 tools
(2026-07-24). Add codes here freely for mock realism; classification no
longer depends on the list being complete.

`eqp_prefixes` is NOT a classifier either (user-confirmed 2026-07-22). A real
eqp_id does carry information -- in the M-fabs a leading number in front of
`MCD` identifies the fab -- but tool FAMILY is not part of it: `MCD` alone
spans CD-SEM, HV-SEM, VeritySEM, and Provision. The lists below exist only
so the mocks can fabricate plausible-looking ids.

This is precisely why `sem_list` is the roster of record. An eqp_id is a
lookup key, not a description: resolve a tool through its sem_list row and
classify from that row's `eqp_model_cd` (`model_to_tool_type()`, mirrored by
`classifyToolType()` in useSemListApi.ts). Never parse the id itself -- see
`lateral_recipe/providers/office_example.py`, which takes versions from its
own index but the tool roster from `sem_list.data.get_sem_list()` for the
same reason.

Vendor (2: HITACHI, AMAT) and adapter folder (3: hitachi, veritysem,
provision) are separate axes -- see `TOOL_TYPE_TO_VENDOR` and
`SLUG_TO_ADAPTER`. They coincide for Hitachi only because CD-SEM and HV-SEM
happen to share one adapter; that is convenience, not a rule.
"""

from typing import Literal, TypedDict


ToolSlug = Literal["cdsem", "hvsem", "veritysem", "provision"]
ToolType = Literal["cd-sem", "hv-sem", "veritysem", "provision"]
Vendor = Literal["HITACHI", "AMAT"]


class ToolSpec(TypedDict):
    eqp_models: list[str]
    eqp_prefixes: list[str]


# CD-SEM scope: Hitachi CG-series and GT-series.
# HV-SEM scope: Hitachi TP-series only.
# VeritySEM / Provision scope: AMAT, OFFICE-VERIFY below.
# ALL lists below are mock fodder, not a family signal -- see the module
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
    # OFFICE-VERIFY: AMAT 모델 코드는 sem_list mock 의 AMAT_MODELS 와 같은
    # 추정값입니다. 사무실에서 v3_df_sem_list 의 eqp_model_cd 를 확인해
    # 실제 코드로 교체하고 `office 확인 <날짜>` 로 표기를 올립니다.
    "veritysem": {
        "eqp_models": ["VERITYSEM_4", "VERITYSEM_5"],
        "eqp_prefixes": ["VCD", "MCD"],
    },
    "provision": {
        "eqp_models": ["PROVISION_10", "PROVISION_20"],
        "eqp_prefixes": ["ACD", "MCD"],
    },
}

VALID_TOOL_SLUGS: frozenset[str] = frozenset(TOOL_SPECS.keys())

SLUG_TO_TOOL_TYPE: dict[ToolSlug, ToolType] = {
    "cdsem": "cd-sem",
    "hvsem": "hv-sem",
    "veritysem": "veritysem",
    "provision": "provision",
}

TOOL_TYPE_TO_VENDOR: dict[ToolType, Vendor] = {
    "cd-sem": "HITACHI",
    "hv-sem": "HITACHI",
    "veritysem": "AMAT",
    "provision": "AMAT",
}

# providers/<이 이름>/ 하위 폴더. 기본은 항등 매핑이고, cdsem/hvsem 만
# "hitachi" 로 합쳐지는 예외입니다 -- 두 계열이 마침 겹치는 부분이 많아 하나의
# 어댑터로 처리할 수 있었을 뿐이며, 규칙이 아니라 우연입니다. 갈라지면
# "cdsem"/"hvsem" 으로 쪼갭니다.
SLUG_TO_ADAPTER: dict[ToolSlug, str] = {
    "cdsem": "hitachi",
    "hvsem": "hitachi",
    "veritysem": "veritysem",
    "provision": "provision",
}

# CD/HV 전용 화면이 담는 범위. `model_to_tool_type() is not None` 으로 이
# 집합을 흉내내던 코드가 있었는데, 분류기가 AMAT 을 해석하기 시작하면 그
# 표현은 조용히 의미가 바뀝니다. 의도를 이름으로 고정합니다.
SEM_TOOL_TYPES: frozenset[ToolType] = frozenset({"cd-sem", "hv-sem"})

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
    ("VERITYSEM", "veritysem"),
    ("VERITY_SEM", "veritysem"),
    ("PROVISION", "provision"),
)


def model_to_tool_type(eqp_model_cd: str) -> ToolType | None:
    """Classify a model code, or None when it belongs to no known family.

    Its frontend counterpart is `classifyToolType()` in
    front-dev-home/app/utils/toolType.ts. The two must agree, and it is
    enforced: both read the same `back_dev_home/ebeam/__fixtures__/
    tool_type_cases.json`, via `back_dev_home/ebeam/tests/
    test_tool_type_parity.py` on this side and `front-dev-home/app/utils/
    toolTypeParity.test.ts` on the frontend side. Add a case there, not just
    a prefix here, when a new series shows up.

    None now means genuinely unknown. It used to double as "an AMAT tool",
    and callers that wanted "CD/HV only" wrote `is not None` -- those must
    say `in SEM_TOOL_TYPES` instead.

    Normalizes case and surrounding whitespace first -- parquet/Redis text
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
