"""Structural validation of provider payloads against TypedDict contracts.

Shared by every feature's tests/test_contract.py (spec section 4). Policy:
extra dict keys are ALLOWED (office sources may return more fields; the
frontend ignores them). Missing required keys or wrong types FAIL with the
full path to the offending value, so the office LLM can self-correct from
pytest output alone.
"""

from __future__ import annotations

import types
import typing
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints


class ContractViolation(AssertionError):
    """A payload does not structurally match its contract."""


def assert_matches(value: Any, contract: Any, path: str = "$") -> None:
    origin = get_origin(contract)

    if contract is Any:
        return
    if contract is None or contract is type(None):
        if value is not None:
            _fail(path, "None", value)
    elif typing.is_typeddict(contract):
        _check_typeddict(value, contract, path)
    elif origin in (Union, types.UnionType):
        _check_union(value, contract, path)
    elif origin is Literal:
        if value not in get_args(contract):
            _fail(path, f"one of {get_args(contract)!r}", value)
    elif origin is list:
        if not isinstance(value, list):
            _fail(path, "list", value)
        item_type = (get_args(contract) or (Any,))[0]
        for i, item in enumerate(value):
            assert_matches(item, item_type, f"{path}[{i}]")
    elif origin is dict:
        if not isinstance(value, dict):
            _fail(path, "dict", value)
        key_type, value_type = get_args(contract) or (Any, Any)
        for key, item in value.items():
            assert_matches(key, key_type, f"{path} key {key!r}")
            assert_matches(item, value_type, f"{path}[{key!r}]")
    elif isinstance(contract, type):
        _check_scalar(value, contract, path)
    else:
        raise TypeError(f"Unsupported contract annotation at {path}: {contract!r}")


def _check_typeddict(value: Any, contract: Any, path: str) -> None:
    if not isinstance(value, dict):
        _fail(path, contract.__name__, value)
    hints = get_type_hints(contract)
    for key in contract.__required_keys__:
        if key not in value:
            raise ContractViolation(
                f"{path}.{key}: required key missing ({contract.__name__})"
            )
        assert_matches(value[key], hints[key], f"{path}.{key}")
    for key in contract.__optional_keys__:
        if key in value:
            assert_matches(value[key], hints[key], f"{path}.{key}")
    # Extra keys: allowed by policy.


def _check_union(value: Any, contract: Any, path: str) -> None:
    errors: list[str] = []
    for arm in get_args(contract):
        try:
            assert_matches(value, arm, path)
            return
        except ContractViolation as exc:
            errors.append(str(exc))
    raise ContractViolation(
        f"{path}: no union arm matched {type(value).__name__} — " + " | ".join(errors)
    )


def _check_scalar(value: Any, contract: type, path: str) -> None:
    if contract is int:
        if isinstance(value, bool) or not isinstance(value, int):
            _fail(path, "int", value)
    elif contract is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            _fail(path, "float", value)
    elif not isinstance(value, contract):
        _fail(path, contract.__name__, value)


def _fail(path: str, expected: str, value: Any) -> None:
    shown = repr(value)
    if len(shown) > 120:
        shown = shown[:117] + "..."
    raise ContractViolation(
        f"{path}: expected {expected}, got {type(value).__name__} ({shown})"
    )
