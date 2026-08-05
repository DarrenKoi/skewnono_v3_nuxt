"""What `_parse_idp` HANDS the 사내 IDP parser — bytes, not a path.

Until 2026-08-05 the adapter wrote every downloaded `.idp` to a temp file
because the parser was documented as path-only. It is not: `combined_idp_info`
accepts a path, bytes or a str, the same as the five raw readers in
`idp_amp_reader` (user-confirmed). The write was the only thing recipe_search
ever put on the Flask host's disk, and it existed for a constraint that never
held.

That fact cannot be checked from home — the parser here is a gitignored
stand-in and the office one has never run against bytes. So this file pins the
two things home CAN prove: the default call passes bytes, and the escape hatch
puts the exact same bytes back on disk if the office turns out to disagree.

The parser is injected into `sys.modules` rather than imported for the reason
`test_align_readers.py` gives: `office_utils` is absent from a clean checkout,
and injecting is also what makes the argument observable.
"""

import sys
import types
from pathlib import Path

import pandas as pd
import pytest

from back_dev_home.ebeam.hitachi.recipe_search.providers import office_example

from .test_idp_parse_shape import (
    ALIGN_COLUMNS,
    IMAGE_COLUMNS,
    MP_COLUMNS,
    _frame,
)


IDP_BYTES = b"\x00\x01raw idp payload"


@pytest.fixture
def parser(monkeypatch):
    """Fake `combined_idp_info`, recording exactly what it was handed."""
    seen: list[object] = []

    def combined_idp_info(source):
        seen.append(source)
        return {
            "wafer_mp_info": _frame(MP_COLUMNS, "mp"),
            "wafer_align_info": _frame(ALIGN_COLUMNS, "align"),
            "idp_image_info": _frame(IMAGE_COLUMNS, "image"),
        }

    module = types.ModuleType("office_utils.read_idp_info")
    module.combined_idp_info = combined_idp_info
    monkeypatch.setitem(sys.modules, "office_utils", types.ModuleType("office_utils"))
    monkeypatch.setitem(sys.modules, "office_utils.read_idp_info", module)
    return seen


def test_the_parser_is_handed_bytes_and_nothing_is_written(parser, monkeypatch, tmp_path):
    monkeypatch.delenv("SKEWNONO_RECIPE_IDP_VIA_TEMPFILE", raising=False)
    monkeypatch.chdir(tmp_path)

    frames = office_example._parse_idp(IDP_BYTES, "A_RECIPE.idp")

    assert parser == [IDP_BYTES]
    assert set(frames) == {"wafer_mp_info", "wafer_align_info", "idp_image_info"}
    # Not a proof that no temp dir was made anywhere, but it does catch the
    # obvious regression of writing beside the process's cwd.
    assert list(tmp_path.iterdir()) == []


def test_the_label_never_reaches_the_parser(parser, monkeypatch):
    """It names the source in error messages only.

    Passing it as a second argument would raise TypeError at the office against
    a parser that takes one — and only at the office.
    """
    monkeypatch.delenv("SKEWNONO_RECIPE_IDP_VIA_TEMPFILE", raising=False)

    office_example._parse_idp(IDP_BYTES, "A_RECIPE.idp")

    assert parser == [IDP_BYTES]


def test_the_escape_hatch_writes_the_same_bytes_to_a_readable_path(parser, monkeypatch):
    """SKEWNONO_RECIPE_IDP_VIA_TEMPFILE=1 restores the pre-2026-08-05 path.

    This branch exists because the bytes claim has never been executed at the
    office and this file cannot be tested from home. It has to work the first
    time it is switched on, in the middle of an outage, so it is tested now
    rather than then: the parser must receive a path that EXISTS and holds the
    downloaded bytes, not a path to a file the temp dir already cleaned up.
    """
    monkeypatch.setenv("SKEWNONO_RECIPE_IDP_VIA_TEMPFILE", "1")
    landed: list[bytes] = []

    def combined_idp_info(source):
        assert isinstance(source, Path), f"expected a path, got {type(source).__name__}"
        landed.append(source.read_bytes())
        assert source.name == "A_RECIPE.idp"
        return {
            "wafer_mp_info": _frame(MP_COLUMNS, "mp"),
            "wafer_align_info": _frame(ALIGN_COLUMNS, "align"),
            "idp_image_info": _frame(IMAGE_COLUMNS, "image"),
        }

    sys.modules["office_utils.read_idp_info"].combined_idp_info = combined_idp_info

    office_example._parse_idp(IDP_BYTES, "A_RECIPE.idp")

    assert landed == [IDP_BYTES]


@pytest.mark.parametrize("value", ["", "0", "no", "true", " 1 "])
def test_only_an_exact_1_switches_the_hatch_on(parser, monkeypatch, value):
    """Anything else keeps the bytes path.

    A hatch that a stray `SKEWNONO_RECIPE_IDP_VIA_TEMPFILE=false` turned ON
    would put the disk write back while the log says nothing is wrong. `" 1 "`
    passes because the value is stripped — .env files carry trailing spaces.
    """
    monkeypatch.setenv("SKEWNONO_RECIPE_IDP_VIA_TEMPFILE", value)

    office_example._parse_idp(IDP_BYTES, "A_RECIPE.idp")

    if value.strip() == "1":
        assert isinstance(parser[0], Path)
    else:
        assert parser == [IDP_BYTES]


def test_a_missing_parser_is_a_runtime_error_not_an_import_error(monkeypatch):
    """The one endpoint that needs office_utils 503s; the rest keep working.

    A module-scope import would make its absence a collection-time failure for
    everything that imports this adapter, including these tests.
    """
    monkeypatch.setitem(sys.modules, "office_utils.read_idp_info", None)

    with pytest.raises(RuntimeError, match="office_utils.read_idp_info"):
        office_example._parse_idp(IDP_BYTES, "A_RECIPE.idp")


def test_a_parser_that_returns_junk_names_the_recipe(parser, monkeypatch):
    """`label` earns its place: the LookupError has to say WHICH recipe."""
    monkeypatch.delenv("SKEWNONO_RECIPE_IDP_VIA_TEMPFILE", raising=False)

    def combined_idp_info(source):
        return {"something_else": pd.DataFrame([{"nope": 1}])}

    sys.modules["office_utils.read_idp_info"].combined_idp_info = combined_idp_info

    with pytest.raises(LookupError, match="A_RECIPE.idp"):
        office_example._parse_idp(IDP_BYTES, "A_RECIPE.idp")
