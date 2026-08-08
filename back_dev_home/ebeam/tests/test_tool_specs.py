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

    CG*, GT* -> cd-sem      TP* -> hv-sem      anything else -> None

Home: .venv/bin/pytest back_dev_home/ebeam/tests
"""

import pytest

from back_dev_home.ebeam._tool_specs import TOOL_SPECS, model_to_tool_type


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


# AMAT tools are their own tool types, deferred to 2027. sem_list's mock
# relies on them classifying as None so every CD/HV-scoped view filters them
# out -- widening the prefix rule must not sweep them in.
@pytest.mark.parametrize(
    "eqp_model_cd",
    ["PROVISION_10", "PROVISION_20", "VERITYSEM_4", "VERITYSEM_5"],
)
def test_amat_models_stay_unclassified(eqp_model_cd):
    assert model_to_tool_type(eqp_model_cd) is None


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
