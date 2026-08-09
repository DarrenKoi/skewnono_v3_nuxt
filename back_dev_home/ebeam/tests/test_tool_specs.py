"""Tool-type classification must follow the model-code PREFIX, not a fixed list.

`model_to_tool_type()` decides which tab a tool belongs to, and office
adapters use it to split combined CD-SEM/HV-SEM data (storage's
`get_ppid_unavailable`, lateral_recipe's roster). A code it fails to
classify is dropped from BOTH tabs silently -- the endpoint still returns a
valid, empty result, so the UI shows "no failing tools" rather than an error.

It used to match an exact list of model codes borrowed from `TOOL_SPECS`,
which exists to give the MOCKS plausible ids. Real office tools were
therefore judged against invented data: at the office, 8 unreachable tools
carried CG/GT/TP codes outside that list and vanished from the
"PPID 미접속 장비" panel while the Redis hash had them all along.

The rule is the vendor's series prefix (user-confirmed 2026-07-24), which is
what `classifyToolType()` in `front-dev-home/app/composables/useSemListApi.ts`
has always used:

    CG*, GT* -> cd-sem      TP* -> hv-sem
    VERITYSEM*, VERITY_SEM* -> veritysem      PROVISION* -> provision
    anything else -> None

Home: .venv/bin/pytest back_dev_home/ebeam/tests
"""

import pytest

from back_dev_home.ebeam._tool_specs import (
    SEM_TOOL_TYPES,
    SLUG_TO_ADAPTER,
    SLUG_TO_TOOL_TYPE,
    TOOL_SPECS,
    TOOL_TYPE_TO_VENDOR,
    model_to_tool_type,
    resolve_tool_type_from_slug,
)


# Codes that are NOT in TOOL_SPECS -- the regression this file exists for.
# Any real series member must classify, not just the ones a mock invented.
@pytest.mark.parametrize(
    "eqp_model_cd, expected",
    [
        ("CG5000", "cd-sem"),
        ("CG6350", "cd-sem"),
        ("CG7000", "cd-sem"),
        ("GT3000", "cd-sem"),
        ("GT2100S", "cd-sem"),
        ("TP4600", "hv-sem"),
        ("TP5000", "hv-sem"),
    ],
)
def test_classifies_series_members_absent_from_tool_specs(eqp_model_cd, expected):
    assert model_to_tool_type(eqp_model_cd) == expected


@pytest.mark.parametrize(
    "eqp_model_cd", sorted(TOOL_SPECS["cdsem"]["eqp_models"])
)
def test_known_cdsem_models_still_classify(eqp_model_cd):
    assert model_to_tool_type(eqp_model_cd) == "cd-sem"


@pytest.mark.parametrize(
    "eqp_model_cd", sorted(TOOL_SPECS["hvsem"]["eqp_models"])
)
def test_known_hvsem_models_still_classify(eqp_model_cd):
    assert model_to_tool_type(eqp_model_cd) == "hv-sem"


# AMAT tools are their own tool types (veritysem/provision), not None -- see
# test_tool_specs.py's appended AMAT coverage below. sem_list's CD/HV-scoped
# views must filter on `in SEM_TOOL_TYPES`, not on this returning None.
@pytest.mark.parametrize(
    "eqp_model_cd, expected",
    [
        ("PROVISION_10", "provision"),
        ("PROVISION_20", "provision"),
        ("VERITYSEM_4", "veritysem"),
        ("VERITYSEM_5", "veritysem"),
    ],
)
def test_amat_models_classify_to_their_own_tool_type(eqp_model_cd, expected):
    assert model_to_tool_type(eqp_model_cd) == expected


@pytest.mark.parametrize("eqp_model_cd", ["", "   ", "UNKNOWN", "XG6300", "T P3000"])
def test_unrecognized_codes_are_unclassified(eqp_model_cd):
    assert model_to_tool_type(eqp_model_cd) is None


# Redis/parquet round-trips leave stray whitespace and casing on text cells,
# and an unclassified tool disappears from the UI without an error, so
# normalize rather than drop.
@pytest.mark.parametrize(
    "eqp_model_cd, expected",
    [
        ("  CG6300  ", "cd-sem"),
        ("cg6300", "cd-sem"),
        ("tp4000", "hv-sem"),
        ("Tp4000", "hv-sem"),
    ],
)
def test_classification_tolerates_whitespace_and_case(eqp_model_cd, expected):
    assert model_to_tool_type(eqp_model_cd) == expected


def test_amat_families_resolve_to_their_own_tool_types():
    assert model_to_tool_type("VERITYSEM_4") == "veritysem"
    assert model_to_tool_type("VERITY_SEM_5") == "veritysem"
    assert model_to_tool_type("PROVISION_10") == "provision"


def test_amat_tool_types_carry_no_hyphen():
    """제품명이 한 단어이고, 슬러그·라우트와 같은 문자열을 쓰기 위함."""
    assert SLUG_TO_TOOL_TYPE["veritysem"] == "veritysem"
    assert SLUG_TO_TOOL_TYPE["provision"] == "provision"


def test_unknown_model_is_still_unclassified():
    assert model_to_tool_type("ZZ9000") is None


def test_vendor_is_a_label_not_the_adapter_axis():
    """벤더는 2개, 어댑터 폴더는 3개 -- 같은 것으로 다루지 않는다."""
    assert TOOL_TYPE_TO_VENDOR["cd-sem"] == "HITACHI"
    assert TOOL_TYPE_TO_VENDOR["veritysem"] == "AMAT"
    assert TOOL_TYPE_TO_VENDOR["provision"] == "AMAT"
    assert set(SLUG_TO_ADAPTER.values()) == {"hitachi", "veritysem", "provision"}


def test_hitachi_is_the_only_adapter_covering_two_families():
    assert SLUG_TO_ADAPTER["cdsem"] == "hitachi"
    assert SLUG_TO_ADAPTER["hvsem"] == "hitachi"
    assert SLUG_TO_ADAPTER["veritysem"] == "veritysem"
    assert SLUG_TO_ADAPTER["provision"] == "provision"


def test_sem_tool_types_excludes_amat():
    """CD/HV 전용 화면이 무엇을 담는지 명시적으로 이름 붙인 집합."""
    assert SEM_TOOL_TYPES == frozenset({"cd-sem", "hv-sem"})


def test_amat_slugs_resolve_from_slug():
    assert resolve_tool_type_from_slug("veritysem") == "veritysem"
    assert resolve_tool_type_from_slug("PROVISION") == "provision"
    assert resolve_tool_type_from_slug("nope") is None
