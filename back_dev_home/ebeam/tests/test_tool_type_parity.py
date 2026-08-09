import json
from pathlib import Path

import pytest

from back_dev_home.ebeam._tool_specs import model_to_tool_type


_FIXTURE = Path(__file__).resolve().parent.parent / "__fixtures__" / "tool_type_cases.json"


def _cases():
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["model"] or "<empty>")
def test_backend_classifier_matches_the_shared_fixture(case):
    assert model_to_tool_type(case["model"]) == case["expected"]
