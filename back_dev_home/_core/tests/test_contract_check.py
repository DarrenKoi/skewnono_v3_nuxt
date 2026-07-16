from typing import Literal, NotRequired, TypedDict

import pytest

from back_dev_home._core.contract_check import ContractViolation, assert_matches


class Row(TypedDict):
    eqp_id: str
    version: int
    available: Literal["On", "Off"]
    note: NotRequired[str]


class Nested(TypedDict):
    rows: list[Row]
    total: int


GOOD_ROW: Row = {"eqp_id": "EQ-01", "version": 3, "available": "On"}


def test_valid_payload_passes():
    assert_matches(GOOD_ROW, Row)


def test_extra_keys_are_allowed():
    assert_matches({**GOOD_ROW, "office_only_field": 123}, Row)


def test_missing_required_key_fails_with_path():
    with pytest.raises(ContractViolation, match=r"\$\.version: required key missing"):
        assert_matches({"eqp_id": "EQ-01", "available": "On"}, Row)


def test_wrong_type_fails_with_path():
    with pytest.raises(ContractViolation, match=r"\$\.version: expected int"):
        assert_matches({**GOOD_ROW, "version": "3"}, Row)


def test_bad_literal_fails():
    with pytest.raises(ContractViolation, match=r"\$\.available"):
        assert_matches({**GOOD_ROW, "available": "Maybe"}, Row)


def test_not_required_key_checked_when_present():
    with pytest.raises(ContractViolation, match=r"\$\.note: expected str"):
        assert_matches({**GOOD_ROW, "note": 42}, Row)


def test_nested_list_paths():
    bad = {"rows": [GOOD_ROW, {"eqp_id": 7, "version": 1, "available": "On"}], "total": 2}
    with pytest.raises(ContractViolation, match=r"\$\.rows\[1\]\.eqp_id: expected str"):
        assert_matches(bad, Nested)


def test_optional_none_passes():
    assert_matches(None, str | None)
    assert_matches("x", str | None)


def test_union_no_arm_fails():
    with pytest.raises(ContractViolation, match=r"no union arm matched"):
        assert_matches(3.5, str | int)


def test_bool_is_not_int():
    with pytest.raises(ContractViolation, match=r"expected int"):
        assert_matches({**GOOD_ROW, "version": True}, Row)


def test_int_accepted_for_float():
    class P(TypedDict):
        value: float

    assert_matches({"value": 3}, P)


def test_plain_dict_value_type_checked():
    with pytest.raises(ContractViolation, match=r"\$\['b'\]: expected int"):
        assert_matches({"a": 1, "b": "x"}, dict[str, int])


def test_non_dict_for_typeddict_fails():
    with pytest.raises(ContractViolation, match=r"\$: expected Row"):
        assert_matches(["not", "a", "dict"], Row)


def test_literal_rejects_bool_for_int_literal():
    class Flag(TypedDict):
        state: Literal[0, 1]

    with pytest.raises(ContractViolation, match=r"\$\.state"):
        assert_matches({"state": True}, Flag)
    assert_matches({"state": 1}, Flag)


def test_missing_key_error_is_deterministic():
    class Multi(TypedDict):
        alpha: str
        beta: str

    # both keys missing -> the alphabetically first is always reported
    with pytest.raises(ContractViolation, match=r"\$\.alpha: required key missing"):
        assert_matches({}, Multi)
