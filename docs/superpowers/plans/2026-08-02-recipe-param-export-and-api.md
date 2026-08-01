# Recipe-open parameter export and tiered read API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user download the selected parameter on `recipe-search/open` as an `.xlsx` with real embedded images, and let a script read the same data through three documented, cost-tiered `GET` endpoints.

**Architecture:** Three new read endpoints compose existing `data.py` functions in a new `recipe_search/param_info.py`; `routes.py` stays validate-and-dispatch. No `providers/` file changes — `include=` controls FTP cost by trimming the `slots` dict both adapters already plan reads from. The frontend export is a new `utils/recipeParamExport.ts` with a pure builder plus an `exceljs` writer, wired to a button in `RecipeOpenView.vue`.

**Tech Stack:** Flask blueprints + TypedDict contracts, pytest; Nuxt 4 + NuxtUI 4, `exceljs`, `node --test`.

**Spec:** `docs/superpowers/specs/2026-08-02-recipe-param-export-and-api-design.md`

## Global Constraints

- Work happens in the worktree `../skewnono-param-export` on branch `work/param-export`. Never `git add -A` / `git add .` / `git commit -a` — always explicit pathspecs.
- Backend commands run from the repo root as `.venv/bin/python -m pytest` (the `-m` is what puts the root on `sys.path`). The worktree has no `.venv` and no `node_modules`: run `.venv/bin/python` and `npm` from `/Users/daeyoung/Codes/skewnono_v3_nuxt`, passing worktree paths, **or** symlink them in. Prefer running the commands from the main tree with explicit worktree paths.
- Do **not** edit `data.py`, `providers/mock.py`, `providers/office_example.py`, or `rawfiles.py`. This feature needs no provider change; if you believe it does, stop and re-read the spec's "Placement" section.
- Colors in Vue come from `--sk-*` tokens only, never inline hex. Read `DESIGN.md` before the UI task.
- Korean user-facing copy uses `~입니다.` / `~합니다.` endings. Markdown tables use markdownlint `MD060` `compact` style. Run `npm run lint:md` after any Markdown edit.
- The three image-bearing slots are exactly `img_add1`, `image_add3`, `img_meas1` (`rawfiles.IMAGE_SLOT_KEYS`). `img_add2` and `img_meas2` are setting files and carry no picture.
- `_MAX_PARAM_ITEMS` is 200 and already exists in `routes.py`. Reuse it; do not introduce a second cap constant.

## File Structure

| File | Responsibility |
| --- | --- |
| `back_dev_home/ebeam/hitachi/recipe_search/contracts.py` | **Modify** — add `ParameterListResponse`, `MeasurementPointsResponse`, `ParamInfoImage`, `ParamOccurrence`, `ParamInfoResponse` |
| `back_dev_home/ebeam/hitachi/recipe_search/param_info.py` | **Create** — pure composition: roll-ups, parameter filtering, slot trimming, `SettingBlock` flattening. No Flask, no I/O of its own |
| `back_dev_home/ebeam/hitachi/recipe_search/routes.py` | **Modify** — three `GET` routes: validate, call `data.py`, hand to `param_info` |
| `back_dev_home/ebeam/hitachi/recipe_search/tests/test_param_info.py` | **Create** — composition unit tests with an injected fetcher |
| `back_dev_home/ebeam/hitachi/recipe_search/tests/test_param_info_routes.py` | **Create** — route status codes and guards |
| `back_dev_home/ebeam/hitachi/recipe_search/MIGRATION.md` | **Modify** — record that the new endpoints need no adapter work |
| `front-dev-home/app/utils/recipeParamExport.ts` | **Create** — `buildParamWorkbook()` (pure) + `downloadParamWorkbook()` (exceljs, image fetch) |
| `front-dev-home/app/utils/recipeParamExport.test.ts` | **Create** — `node --test` over the pure builder |
| `front-dev-home/app/components/ebeam/RecipeOpenView.vue` | **Modify** — export button + options popover in the `SELECTED` header |
| `front-dev-home/app/pages/endpoints.vue` | **Modify** — six entries in the `Recipe Search` group |

---

### Task 1: Contracts and the composition module

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/recipe_search/contracts.py`
- Create: `back_dev_home/ebeam/hitachi/recipe_search/param_info.py`
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_param_info.py`

**Interfaces:**

- Consumes: `RecipeDetailResponse`, `IdpImageInfoRow`, `WaferMpInfoRow`, `SettingBlock`, `SettingRow`, `ParamDetailRequestItem`, `ParamDetailResponse` from `contracts.py`.
- Produces, all importable from `param_info`:
  - `INCLUDE_PARTS: tuple[str, ...]` — `("amp", "af_pr", "images")`
  - `parse_include(raw: str | None) -> tuple[str, ...]` — raises `ValueError` on an unknown part
  - `build_parameter_list(detail, tool_type, fab_name) -> ParameterListResponse`
  - `build_measurement_points(detail, parameter) -> MeasurementPointsResponse`
  - `rows_for_parameter(detail, parameter) -> list[IdpImageInfoRow]`
  - `build_param_info(detail, parameter, tool_type, fab_name, include, fetch) -> ParamInfoResponse`
  - `MAX_OCCURRENCES: int`

- [ ] **Step 1: Add the response contracts**

Append to `contracts.py`, and add every new name to `__all__` (keep it alphabetical):

```python
class ParameterListResponse(TypedDict):
    """Tier 0 — every idp_image_info row, no tool I/O.

    ``total_rows`` rather than ``total``: the grain is the ROW, and a bare
    ``total`` is the field a caller misreads as a parameter count. A row of
    idp_image_info is one image definition, so one parameter can occupy
    several rows — ``distinct_parameters`` is carried so the number a user
    actually wants needs no client-side dedup. ``mother_rows`` and
    ``addressing_rows`` are row counts too, and are named to say so.
    """
    recipe_id: str
    fab_name: str | None
    tool_type: ToolType
    locator: IdpLocator
    total_rows: int
    distinct_parameters: int
    mother_rows: int
    addressing_rows: int
    rows: list[IdpImageInfoRow]


class MeasurementPointsResponse(TypedDict):
    """Tier 1 — wafer_mp_info filtered to one parameter. No tool I/O."""
    recipe_id: str
    parameter: str
    total: int
    points: list[WaferMpInfoRow]


ParamInfoImage = TypedDict("ParamInfoImage", {
    "slot": str,
    "stage": str,
    "name": str,
    # Flattened from SettingBlock: the block's file name moves to
    # ``cond_source`` so the rows are a plain list. A caller wanting the
    # block shape verbatim uses param-detail.
    "cond": list[SettingRow],
    "cond_source": str | None
})

# One idp_image_info row's worth of raw-folder settings. Every settings key is
# NotRequired because ``include=`` omits the parts it was not asked for — and
# omits them by never reading their files, not by deleting them afterwards.
ParamOccurrence = TypedDict("ParamOccurrence", {
    "idp": IdpImageInfoRow,
    "amp": NotRequired[list[SettingRow]],
    "amp_source": NotRequired[str | None],
    "af_pr": NotRequired[list[SettingRow]],
    "af_pr_source": NotRequired[str | None],
    "images": NotRequired[list[ParamInfoImage]]
})


class ParamInfoResponse(TypedDict):
    """Tier 2 — the raw-recipe-folder settings for one parameter.

    ``occurrences`` is a LIST because a parameter is not a row: Para_13 at
    SEQ 4/6 and at SEQ 11/15 name different files. A single-object response
    would have to pick one silently, which is the bug recorded at
    useRecipeParamDetail.ts:83.
    """
    recipe_id: str
    fab_name: str | None
    tool_type: ToolType
    parameter: str
    locator: IdpLocator
    include: list[str]
    occurrences: list[ParamOccurrence]
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_param_info.py`:

```python
"""Composition for the three tiered recipe-search read endpoints.

Everything here is exercised against a hand-built RecipeDetailResponse rather
than the mock provider: the mock draws its Parameter values at random, so a
test that needs a parameter occupying TWO rows — the case the whole
``occurrences`` shape exists for — cannot be written against it reliably.
"""

import pytest

from back_dev_home.ebeam.hitachi.recipe_search import param_info


LOCATOR = {"eqp_ip": "10.1.2.3", "class_name": "CLS", "idw": "IDW_A", "idp": "IDP_B"}


def _row(parameter, seq, **overrides):
    row = {
        "Parameter": parameter,
        "img_add1": f"IMMP{seq:04d}",
        "img_add2": f"PRMP{seq:04d}",
        "img_meas1": f"IMMS{seq:04d}",
        "img_meas2": f"PRMS{seq:04d}",
        "image_add3": "non",
        "SEQ": seq,
        "Last_SEQ": seq + 2,
        "Region": 1,
        "Addressing": True,
        "Mother_Para": seq == 1,
        "Double_Addressing": False,
        "Meas_Counting": 5,
        "dnumber_removed": False,
    }
    row.update(overrides)
    return row


def _detail():
    return {
        "idp_image_info": [
            _row("Para_1", 1),
            _row("Para_13", 4, Addressing=False),
            _row("Para_13", 11),
        ],
        "wafer_mp_info": [
            {"Parameter": "Para_13", "P_No": 1, "D_No": 1},
            {"Parameter": "Para_1", "P_No": 2, "D_No": 2},
            {"Parameter": "Para_13", "P_No": 3, "D_No": 3},
        ],
        "wafer_align_info": [],
        "locator": LOCATOR,
        "recipe_id": "RCP_001",
        "fac_id": "M11",
        "tool_category": "cd-sem",
        "timestamp": "2026-08-02T00:00:00",
    }


def _fetch_stub(calls):
    """Stand in for get_param_detail, recording the items it was handed."""
    def fetch(items):
        calls.extend(items)
        return [
            {
                "parameter": item["parameter"],
                "amp": {"source": "PRMS0000", "rows": [{"key": "ACCV", "value": "800"}]},
                "af_pr": {"source": "ENMP0000",
                          "rows": [{"key": "MODE", "value": "AUTO", "section": "ADD1"}]},
                "images": [
                    {"slot": "img_add1", "stage": "Addressing 1", "name": "IMMP0004.jpeg",
                     "cond": {"source": "cond.txt", "rows": [{"key": "MAG", "value": "50k"}]}}
                ],
            }
            for item in items
        ]
    return fetch


# ── tier 0 ────────────────────────────────────────────────────────────────


def test_parameter_list_counts_rows_and_distinct_parameters_separately():
    out = param_info.build_parameter_list(_detail(), "cd-sem", "M11")
    assert out["total_rows"] == 3
    assert out["distinct_parameters"] == 2
    assert out["locator"] == LOCATOR


def test_parameter_list_roll_ups_count_rows_not_parameters():
    out = param_info.build_parameter_list(_detail(), "cd-sem", "M11")
    # Para_13 occupies two rows and is Addressing on only one of them.
    assert out["addressing_rows"] == 2
    assert out["mother_rows"] == 1


def test_parameter_list_returns_rows_verbatim():
    out = param_info.build_parameter_list(_detail(), "cd-sem", "M11")
    assert out["rows"] == _detail()["idp_image_info"]


# ── tier 1 ────────────────────────────────────────────────────────────────


def test_measurement_points_filters_by_parameter():
    out = param_info.build_measurement_points(_detail(), "Para_13")
    assert out["total"] == 2
    assert [p["P_No"] for p in out["points"]] == [1, 3]


# ── tier 2 ────────────────────────────────────────────────────────────────


def test_rows_for_parameter_returns_every_occurrence_in_row_order():
    rows = param_info.rows_for_parameter(_detail(), "Para_13")
    assert [row["SEQ"] for row in rows] == [4, 11]


def test_rows_for_parameter_is_empty_for_an_unknown_parameter():
    assert param_info.rows_for_parameter(_detail(), "Para_999") == []


def test_param_info_returns_one_occurrence_per_row():
    calls = []
    out = param_info.build_param_info(
        _detail(), "Para_13", "cd-sem", "M11",
        param_info.INCLUDE_PARTS, _fetch_stub(calls),
    )
    assert [occ["idp"]["SEQ"] for occ in out["occurrences"]] == [4, 11]
    assert len(calls) == 2


def test_param_info_flattens_setting_blocks_to_rows_plus_source():
    out = param_info.build_param_info(
        _detail(), "Para_13", "cd-sem", "M11",
        param_info.INCLUDE_PARTS, _fetch_stub([]),
    )
    occ = out["occurrences"][0]
    assert occ["amp"] == [{"key": "ACCV", "value": "800"}]
    assert occ["amp_source"] == "PRMS0000"
    assert occ["af_pr_source"] == "ENMP0000"
    assert occ["images"][0]["cond"] == [{"key": "MAG", "value": "50k"}]
    assert occ["images"][0]["cond_source"] == "cond.txt"


def test_include_amp_drops_every_other_slot_from_the_request():
    """The point of include=: a dropped slot is a file never read.

    Both adapters plan their reads with slots.get(...) through
    rawfiles.slot_sources, so an ABSENT key takes the same branch as an empty
    one. Filtering the response instead would cost the same FTP reads.
    """
    calls = []
    param_info.build_param_info(
        _detail(), "Para_13", "cd-sem", "M11", ("amp",), _fetch_stub(calls),
    )
    assert set(calls[0]["slots"]) == {"img_meas2"}


def test_include_amp_omits_the_other_parts_from_the_response():
    out = param_info.build_param_info(
        _detail(), "Para_13", "cd-sem", "M11", ("amp",), _fetch_stub([]),
    )
    occ = out["occurrences"][0]
    assert "amp" in occ
    assert "af_pr" not in occ
    assert "images" not in occ


def test_include_images_keeps_only_the_three_image_slots():
    calls = []
    param_info.build_param_info(
        _detail(), "Para_13", "cd-sem", "M11", ("images",), _fetch_stub(calls),
    )
    assert set(calls[0]["slots"]) == {"img_add1", "image_add3", "img_meas1"}


def test_param_info_caps_occurrences():
    detail = _detail()
    detail["idp_image_info"] = [_row("Para_X", seq) for seq in range(1, 260)]
    out = param_info.build_param_info(
        detail, "Para_X", "cd-sem", "M11",
        param_info.INCLUDE_PARTS, _fetch_stub([]),
    )
    assert len(out["occurrences"]) == param_info.MAX_OCCURRENCES


# ── include parsing ───────────────────────────────────────────────────────


@pytest.mark.parametrize("raw", [None, "", "   "])
def test_parse_include_defaults_to_every_part(raw):
    assert param_info.parse_include(raw) == param_info.INCLUDE_PARTS


def test_parse_include_reads_a_comma_separated_list():
    assert param_info.parse_include("amp, images") == ("amp", "images")


def test_parse_include_rejects_an_unknown_part():
    with pytest.raises(ValueError):
        param_info.parse_include("amp,beam")
```

- [ ] **Step 2b: Run the tests to verify they fail**

From `/Users/daeyoung/Codes/skewnono_v3_nuxt`:

```bash
.venv/bin/python -m pytest ../skewnono-param-export/back_dev_home/ebeam/hitachi/recipe_search/tests/test_param_info.py -q
```

Expected: collection error, `ModuleNotFoundError: ... param_info`.

- [ ] **Step 3: Implement `param_info.py`**

```python
"""Composition for the three tiered recipe-search read endpoints.

Pure: takes an already-fetched ``RecipeDetailResponse`` and a fetcher, returns
the response body. No Flask and no I/O of its own, so the cost behaviour that
matters — which slots reach the provider — is unit-testable without a tool.

The tiers exist because two very different costs hide behind "parameter info":
``idp_image_info`` and ``wafer_mp_info`` come from the .idp parse already in
hand, while ``amp``/``af_pr``/``cond`` cost up to five FTP reads per occurrence
off the measuring tool itself.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable

from back_dev_home.ebeam.hitachi.recipe_search.contracts import (
    IdpImageInfoRow,
    MeasurementPointsResponse,
    ParamDetailRequestItem,
    ParamDetailResponse,
    ParameterListResponse,
    ParamInfoImage,
    ParamInfoResponse,
    ParamOccurrence,
    RecipeDetailResponse,
    SettingBlock,
    SettingRow,
    ToolType,
)


__all__ = [
    "INCLUDE_PARTS",
    "MAX_OCCURRENCES",
    "build_measurement_points",
    "build_param_info",
    "build_parameter_list",
    "parse_include",
    "rows_for_parameter",
]


INCLUDE_PARTS: tuple[str, ...] = ("amp", "af_pr", "images")

# Which slot each part's files are named by. Dropping a slot is what makes
# ``include=`` a real cost control: both adapters plan reads through
# ``rawfiles.slot_sources``, which reads every slot with ``slots.get(...)``, so
# an absent key takes the same branch as an empty one and the read never
# happens. Filtering the RESPONSE instead would cost the same FTP session.
_PART_SLOTS: dict[str, tuple[str, ...]] = {
    "amp": ("img_meas2",),
    "af_pr": ("img_add2",),
    "images": ("img_add1", "image_add3", "img_meas1"),
}

# Same ceiling routes.py already applies to param-detail's item list. An
# unbounded parameter match is an unbounded pull off a production tool.
MAX_OCCURRENCES = 200


def parse_include(raw: str | None) -> tuple[str, ...]:
    """``"amp, images"`` -> ``("amp", "images")``. Absent means every part.

    Raises:
        ValueError: a part that is not in INCLUDE_PARTS.
    """
    text = (raw or "").strip()
    if not text:
        return INCLUDE_PARTS
    parts = tuple(piece.strip() for piece in text.split(",") if piece.strip())
    unknown = [part for part in parts if part not in INCLUDE_PARTS]
    if unknown:
        raise ValueError(
            f"include must name only {', '.join(INCLUDE_PARTS)}; got {', '.join(unknown)}"
        )
    return parts or INCLUDE_PARTS


def build_parameter_list(
    detail: RecipeDetailResponse,
    tool_type: ToolType,
    fab_name: str | None,
) -> ParameterListResponse:
    rows = list(detail.get("idp_image_info") or [])
    return {
        "recipe_id": detail.get("recipe_id", ""),
        "fab_name": fab_name,
        "tool_type": tool_type,
        "locator": detail.get("locator", {}),
        "total_rows": len(rows),
        "distinct_parameters": len({row.get("Parameter") for row in rows}),
        "mother_rows": sum(1 for row in rows if row.get("Mother_Para")),
        "addressing_rows": sum(1 for row in rows if row.get("Addressing")),
        "rows": rows,
    }


def build_measurement_points(
    detail: RecipeDetailResponse,
    parameter: str,
) -> MeasurementPointsResponse:
    points = [
        row for row in (detail.get("wafer_mp_info") or [])
        if row.get("Parameter") == parameter
    ]
    return {
        "recipe_id": detail.get("recipe_id", ""),
        "parameter": parameter,
        "total": len(points),
        "points": points,
    }


def rows_for_parameter(
    detail: RecipeDetailResponse,
    parameter: str,
) -> list[IdpImageInfoRow]:
    """Every idp_image_info row naming this parameter, in table order.

    A LIST, because a row is one image DEFINITION rather than one parameter:
    Para_13 at SEQ 4/6 and SEQ 11/15 resolve to different files.
    """
    return [
        row for row in (detail.get("idp_image_info") or [])
        if row.get("Parameter") == parameter
    ]


def _trimmed_slots(row: IdpImageInfoRow, include: Iterable[str]) -> dict[str, str]:
    keep = {slot for part in include for slot in _PART_SLOTS[part]}
    return {slot: str(row.get(slot) or "") for slot in keep}


def _flatten(block: SettingBlock | None) -> tuple[list[SettingRow], str | None]:
    if not block:
        return [], None
    return list(block.get("rows") or []), block.get("source")


def _occurrence(
    row: IdpImageInfoRow,
    detail: ParamDetailResponse,
    include: Iterable[str],
) -> ParamOccurrence:
    parts = set(include)
    occurrence: ParamOccurrence = {"idp": row}
    if "amp" in parts:
        occurrence["amp"], occurrence["amp_source"] = _flatten(detail.get("amp"))
    if "af_pr" in parts:
        occurrence["af_pr"], occurrence["af_pr_source"] = _flatten(detail.get("af_pr"))
    if "images" in parts:
        images: list[ParamInfoImage] = []
        for image in detail.get("images") or []:
            rows, source = _flatten(image.get("cond"))
            images.append({
                "slot": image.get("slot", ""),
                "stage": image.get("stage", ""),
                "name": image.get("name", ""),
                "cond": rows,
                "cond_source": source,
            })
        occurrence["images"] = images
    return occurrence


def build_param_info(
    detail: RecipeDetailResponse,
    parameter: str,
    tool_type: ToolType,
    fab_name: str | None,
    include: Iterable[str],
    fetch: Callable[[list[ParamDetailRequestItem]], list[ParamDetailResponse]],
) -> ParamInfoResponse:
    """One occurrence per idp_image_info row naming ``parameter``.

    ``fetch`` is injected rather than imported so the slot trimming — the part
    that decides how many files come off a production tool — can be asserted
    without one.
    """
    include = tuple(include)
    locator = detail.get("locator", {})
    rows = rows_for_parameter(detail, parameter)[:MAX_OCCURRENCES]
    items: list[ParamDetailRequestItem] = [
        {
            "locator": locator,
            "parameter": parameter,
            "slots": _trimmed_slots(row, include),
        }
        for row in rows
    ]
    details = fetch(items) if items else []
    return {
        "recipe_id": detail.get("recipe_id", ""),
        "fab_name": fab_name,
        "tool_type": tool_type,
        "parameter": parameter,
        "locator": locator,
        "include": list(include),
        # strict=True on purpose. Both adapters contract to return exactly one
        # entry per item; a mismatch means a provider bug, and zipping loosely
        # would silently DROP occurrences — the same class of quiet wrong answer
        # the occurrences list exists to prevent. A 500 is the honest answer.
        "occurrences": [
            _occurrence(row, found, include)
            for row, found in zip(rows, details, strict=True)
        ],
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest ../skewnono-param-export/back_dev_home/ebeam/hitachi/recipe_search/tests/test_param_info.py -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/recipe_search/contracts.py \
        back_dev_home/ebeam/hitachi/recipe_search/param_info.py \
        back_dev_home/ebeam/hitachi/recipe_search/tests/test_param_info.py
git commit -m "feat(recipe-search): compose tiered parameter read responses

param_info.py turns one RecipeDetailResponse into the three tier payloads.
include= trims the slots dict handed to get_param_detail rather than filtering
the response, so an omitted part is an FTP read that never happens."
```

---

### Task 2: The three routes

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/recipe_search/routes.py`
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/MIGRATION.md`
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_param_info_routes.py`

**Interfaces:**

- Consumes: everything Task 1 produced, plus `get_recipe_open_data` and `get_param_detail` from `data.py`, and the existing `_resolve_tool_type`, `_resolve_fab_name`, `_error`, `_MAX_PARAM_ITEMS` in `routes.py`.
- Produces: `GET /api/<tool_slug>/recipe-search/parameters`, `.../measurement-points`, `.../param-info`.

- [ ] **Step 1: Write the failing route tests**

Create `tests/test_param_info_routes.py`:

```python
"""Status codes and guards for the three tiered read endpoints.

These run against the MOCK provider, so they assert shape and status rather
than values: the mock draws Parameter values at random, and a test that
depended on a particular one would be flaky by construction. The composition
itself is tested in test_param_info.py against a fixed payload.
"""

import pytest
from flask import Flask

from back_dev_home.ebeam.hitachi.recipe_search import routes


@pytest.fixture()
def client():
    app = Flask(__name__)
    app.register_blueprint(routes.bp, url_prefix="/api")
    return app.test_client()


def _any_parameter(client):
    body = client.get(
        "/api/cdsem/recipe-search/parameters?recipe_name=RCP_001"
    ).get_json()
    return body["rows"][0]["Parameter"]


# ── parameters ────────────────────────────────────────────────────────────


def test_parameters_returns_row_and_parameter_counts(client):
    response = client.get("/api/cdsem/recipe-search/parameters?recipe_name=RCP_001")
    assert response.status_code == 200
    body = response.get_json()
    assert body["total_rows"] == len(body["rows"])
    assert body["distinct_parameters"] <= body["total_rows"]
    assert set(body["locator"]) == {"eqp_ip", "class_name", "idw", "idp"}


def test_parameters_requires_a_recipe_name(client):
    assert client.get("/api/cdsem/recipe-search/parameters").status_code == 400


def test_parameters_rejects_an_unknown_tool_slug(client):
    response = client.get("/api/xxsem/recipe-search/parameters?recipe_name=R")
    assert response.status_code == 400


# ── measurement-points ────────────────────────────────────────────────────


def test_measurement_points_returns_only_the_named_parameter(client):
    parameter = _any_parameter(client)
    response = client.get(
        "/api/cdsem/recipe-search/measurement-points"
        f"?recipe_name=RCP_001&parameter={parameter}"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert all(point["Parameter"] == parameter for point in body["points"])
    assert body["total"] == len(body["points"])


def test_measurement_points_requires_a_parameter(client):
    response = client.get(
        "/api/cdsem/recipe-search/measurement-points?recipe_name=RCP_001"
    )
    assert response.status_code == 400


def test_measurement_points_404s_on_a_parameter_the_recipe_lacks(client):
    response = client.get(
        "/api/cdsem/recipe-search/measurement-points"
        "?recipe_name=RCP_001&parameter=Para_does_not_exist"
    )
    assert response.status_code == 404


# ── param-info ────────────────────────────────────────────────────────────


def test_param_info_returns_an_occurrence_per_row(client):
    parameter = _any_parameter(client)
    listing = client.get(
        "/api/cdsem/recipe-search/parameters?recipe_name=RCP_001"
    ).get_json()
    expected = sum(1 for row in listing["rows"] if row["Parameter"] == parameter)

    response = client.get(
        "/api/cdsem/recipe-search/param-info"
        f"?recipe_name=RCP_001&parameter={parameter}"
    )
    assert response.status_code == 200
    body = response.get_json()
    assert len(body["occurrences"]) == expected
    assert body["include"] == ["amp", "af_pr", "images"]


def test_param_info_include_narrows_the_response(client):
    parameter = _any_parameter(client)
    response = client.get(
        "/api/cdsem/recipe-search/param-info"
        f"?recipe_name=RCP_001&parameter={parameter}&include=amp"
    )
    assert response.status_code == 200
    occurrence = response.get_json()["occurrences"][0]
    assert "amp" in occurrence
    assert "af_pr" not in occurrence
    assert "images" not in occurrence


def test_param_info_rejects_an_unknown_include_part(client):
    parameter = _any_parameter(client)
    response = client.get(
        "/api/cdsem/recipe-search/param-info"
        f"?recipe_name=RCP_001&parameter={parameter}&include=beam"
    )
    assert response.status_code == 400


def test_param_info_404s_on_a_parameter_the_recipe_lacks(client):
    response = client.get(
        "/api/cdsem/recipe-search/param-info"
        "?recipe_name=RCP_001&parameter=Para_does_not_exist"
    )
    assert response.status_code == 404


def test_param_info_requires_recipe_name_and_parameter(client):
    assert client.get(
        "/api/cdsem/recipe-search/param-info?parameter=Para_1"
    ).status_code == 400
    assert client.get(
        "/api/cdsem/recipe-search/param-info?recipe_name=RCP_001"
    ).status_code == 400


def test_param_info_turns_an_unreachable_tool_into_503(client, monkeypatch):
    """A tool that refuses the connection is a 503, not a 500 traceback.

    Same contract param-detail, align-detail and recipe-image already keep.
    """
    from back_dev_home.msr_image.errors import SourceUnavailable

    def boom(_items):
        raise SourceUnavailable("tool refused the connection")

    monkeypatch.setattr(routes, "get_param_detail", boom)
    parameter = _any_parameter(client)
    response = client.get(
        "/api/cdsem/recipe-search/param-info"
        f"?recipe_name=RCP_001&parameter={parameter}"
    )
    assert response.status_code == 503
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
.venv/bin/python -m pytest ../skewnono-param-export/back_dev_home/ebeam/hitachi/recipe_search/tests/test_param_info_routes.py -q
```

Expected: 404s from Flask for every new path (the routes do not exist yet).

Before implementing, confirm the exception name used in the last test really exists:

```bash
grep -n "class .*Error\|class .*Unavailable" ../skewnono-param-export/back_dev_home/msr_image/errors.py
```

If `SourceUnavailable` is not there, use whatever `MsrImageError` subclass is, and keep the test's intent (a coded 503, not a 500).

- [ ] **Step 3: Implement the routes**

Add to the imports at the top of `routes.py`:

```python
from back_dev_home.ebeam.hitachi.recipe_search import param_info
```

All three routes resolve the recipe through the same helper, so an office
adapter that reaches a tool to locate the `.idp` cannot escape as a 500:

```python
def _open_data_or_error(recipe_name: str, fab_name: str | None, tool_type: ToolType):
    """``(detail, None)`` or ``(None, coded_response)``.

    ``get_recipe_open_data`` is I/O at the office — locating the .idp can touch
    the tool — so it needs the same MsrImageError guard the raw-folder routes
    already apply. Returning the response rather than raising keeps the three
    callers flat.
    """
    try:
        return get_recipe_open_data(
            recipe_id=recipe_name, fac_id=fab_name, tool_category=tool_type
        ), None
    except MsrImageError as exc:
        return None, _error(exc)
```

Append the three routes after `recipe_search_recipe_detail`:

```python
@bp.get("/<tool_slug>/recipe-search/parameters")
def recipe_search_parameters(tool_slug: str):
    """Tier 0 — every idp_image_info row of one recipe. No tool I/O.

    A strict, cheaper subset of recipe-detail, for callers that want the
    parameter listing without the measurement and align tables. The locator is
    returned so a caller can drop straight into POST param-detail for bulk
    work without a second recipe-detail call.
    """
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    recipe_name = (request.args.get("recipe_name") or "").strip()
    if not recipe_name:
        return jsonify({"error": "recipe_name is required"}), 400

    fab_name = _resolve_fab_name()
    detail, failed = _open_data_or_error(recipe_name, fab_name, tool_type)
    if failed:
        return failed
    return jsonify(param_info.build_parameter_list(detail, tool_type, fab_name))


@bp.get("/<tool_slug>/recipe-search/measurement-points")
def recipe_search_measurement_points(tool_slug: str):
    """Tier 1 — wafer_mp_info for one parameter. No tool I/O.

    ``parameter`` is required: the unfiltered table is what recipe-detail
    already returns.
    """
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    recipe_name = (request.args.get("recipe_name") or "").strip()
    parameter = (request.args.get("parameter") or "").strip()
    if not recipe_name or not parameter:
        return jsonify({"error": "recipe_name and parameter are required"}), 400

    detail, failed = _open_data_or_error(recipe_name, _resolve_fab_name(), tool_type)
    if failed:
        return failed
    # 404 on the PARAMETER, not on an empty point list: a parameter can
    # legitimately have no measurement point, and collapsing the two would
    # report a typo'd name as "no points".
    if not param_info.rows_for_parameter(detail, parameter):
        return jsonify({"error": f"parameter not in recipe: {parameter}"}), 404

    return jsonify(param_info.build_measurement_points(detail, parameter))


@bp.get("/<tool_slug>/recipe-search/param-info")
def recipe_search_param_info(tool_slug: str):
    """Tier 2 — raw-recipe-folder settings for one parameter.

    ``occurrences`` is a list because a parameter can occupy several
    idp_image_info rows naming different files. ``include`` narrows what is
    read, not merely what is returned.
    """
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    recipe_name = (request.args.get("recipe_name") or "").strip()
    parameter = (request.args.get("parameter") or "").strip()
    if not recipe_name or not parameter:
        return jsonify({"error": "recipe_name and parameter are required"}), 400

    try:
        include = param_info.parse_include(request.args.get("include"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    fab_name = _resolve_fab_name()
    detail, failed = _open_data_or_error(recipe_name, fab_name, tool_type)
    if failed:
        return failed
    if not param_info.rows_for_parameter(detail, parameter):
        return jsonify({"error": f"parameter not in recipe: {parameter}"}), 404

    # The fetch is inside the guard because an unreachable tool raises
    # SourceUnavailable from deep in the FTP layer; without this it would
    # surface as a 500 traceback instead of the coded 503 the rest of the
    # tool-FTP surface returns.
    try:
        return jsonify(param_info.build_param_info(
            detail, parameter, tool_type, fab_name, include, get_param_detail
        ))
    except MsrImageError as exc:
        return _error(exc)
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest ../skewnono-param-export/back_dev_home/ebeam/hitachi/recipe_search -q
```

Expected: the new file passes and no existing recipe_search test regresses.

- [ ] **Step 5: Note the migration status**

Add to `MIGRATION.md`, under whatever heading lists the feature's endpoints:

```markdown
## Tiered read endpoints (2026-08-02) — no adapter work

`GET parameters`, `GET measurement-points` and `GET param-info` compose
`get_recipe_open_data()` and `get_param_detail()` in `param_info.py`. They add
no swap surface: nothing in `providers/` changes, and both adapters answer them
the moment the routes exist.

`param-info`'s `include=` narrows cost by trimming the `slots` dict, and
`rawfiles.slot_sources` reads every slot with `slots.get(...)`, so an absent key
takes the same branch as an empty one. An office adapter must keep planning its
reads through `slot_sources` for that to hold.
```

- [ ] **Step 6: Lint and commit**

```bash
# from /Users/daeyoung/Codes/skewnono_v3_nuxt
npx markdownlint-cli2 "../skewnono-param-export/back_dev_home/ebeam/hitachi/recipe_search/MIGRATION.md"
```

```bash
git add back_dev_home/ebeam/hitachi/recipe_search/routes.py \
        back_dev_home/ebeam/hitachi/recipe_search/MIGRATION.md \
        back_dev_home/ebeam/hitachi/recipe_search/tests/test_param_info_routes.py
git commit -m "feat(recipe-search): serve parameters, measurement-points, param-info

Three GET endpoints tiered by read cost: the first two answer from the .idp
parse alone, param-info is the raw-folder tier and turns an unreachable tool
into the same coded 503 the rest of the FTP surface returns."
```

---

### Task 3: Document the endpoints in the API catalog

**Files:**

- Modify: `front-dev-home/app/pages/endpoints.vue` (the `Recipe Search` group, currently at `endpoints.vue:211-289`)

**Interfaces:**

- Consumes: the routes from Task 2, and the page's existing `ApiEndpoint` / `ApiArg` types and `TOOL_SLUG_ARG` / `FAB_NAME_ARG` constants.
- Produces: nothing other tasks depend on.

There is no test harness for this page — it is a static catalog. Verification is `npm run typecheck` plus the browser check in the Verification phase.

- [ ] **Step 1: Add the six entries**

Insert into the `Recipe Search` group's `endpoints` array, **after** the `recipe-detail` entry and before `lateral`, so the group reads cheap → expensive:

```ts
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/parameters',
        summary: 'recipe의 parameter(idp_image_info) row 목록과 row/parameter 개수를 반환합니다. 장비 접속이 없어 가볍습니다.',
        args: [
          TOOL_SLUG_ARG,
          { name: 'recipe_name', kind: 'query', required: true, note: '조회할 recipe 이름' },
          FAB_NAME_ARG
        ],
        response: 'ParameterListResponse',
        auth: '토큰 가능',
        example: { path: '/cdsem/recipe-search/parameters', query: { recipe_name: 'RCP_001' } }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/measurement-points',
        summary: '해당 parameter의 측정 위치(wafer_mp_info) row만 필터링해 반환합니다. 장비 접속이 없어 가볍습니다.',
        args: [
          TOOL_SLUG_ARG,
          { name: 'recipe_name', kind: 'query', required: true, note: '조회할 recipe 이름' },
          { name: 'parameter', kind: 'query', required: true, note: 'parameters 응답의 Parameter 값' },
          FAB_NAME_ARG
        ],
        response: 'MeasurementPointsResponse',
        auth: '토큰 가능',
        example: {
          path: '/cdsem/recipe-search/measurement-points',
          query: { recipe_name: 'RCP_001', parameter: 'Para_13' }
        }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/param-info',
        summary: 'parameter의 AMP, AF/PR, 이미지별 빔 조건을 반환합니다. 같은 parameter가 여러 row에 걸쳐 있으면 occurrences 배열로 모두 내려갑니다. 장비 FTP를 읽으므로 occurrence당 최대 5개 파일을 조회합니다.',
        args: [
          TOOL_SLUG_ARG,
          { name: 'recipe_name', kind: 'query', required: true, note: '조회할 recipe 이름' },
          { name: 'parameter', kind: 'query', required: true, note: 'parameters 응답의 Parameter 값' },
          {
            name: 'include',
            kind: 'query',
            required: false,
            note: 'amp, af_pr, images 중 쉼표로 지정. 생략하면 전체. 제외한 항목은 장비 파일을 읽지 않으므로 호출이 가벼워집니다'
          },
          FAB_NAME_ARG
        ],
        response: 'ParamInfoResponse',
        auth: '토큰 가능',
        example: {
          path: '/cdsem/recipe-search/param-info',
          query: { recipe_name: 'RCP_001', parameter: 'Para_13', include: 'amp' }
        }
      },
      {
        method: 'POST',
        path: '/api/{tool_slug}/recipe-search/param-detail',
        summary: '여러 (recipe, parameter) 조합의 원본 폴더 설정을 한 번에 조회합니다. locator와 img_* slot 값을 직접 넘겨야 하므로, 단건 조회는 param-info가 더 간단합니다.',
        args: [
          TOOL_SLUG_ARG,
          {
            name: 'items',
            kind: 'body',
            required: true,
            note: '[{ locator, parameter, slots }] — 최대 200건. locator와 slots는 parameters 응답에서 얻습니다'
          }
        ],
        response: 'ParamDetailResponse[]',
        auth: '토큰 가능',
        example: {
          path: '/cdsem/recipe-search/param-detail',
          body: {
            items: [{
              locator: { eqp_ip: '10.1.2.3', class_name: 'CLS', idw: 'IDW_A', idp: 'IDP_B' },
              parameter: 'Para_13',
              slots: { img_meas2: 'PRMS0000' }
            }]
          }
        }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/align-detail',
        summary: 'wafer align point별 이미지, 빔 조건, AF/PR 설정을 한 번에 반환합니다.',
        args: [
          TOOL_SLUG_ARG,
          { name: 'eqp_ip', kind: 'query', required: true, note: 'recipe-detail 응답 locator의 eqp_ip' },
          { name: 'class_name', kind: 'query', required: true, note: 'locator의 class_name' },
          { name: 'idw', kind: 'query', required: true, note: 'locator의 idw' },
          { name: 'idp', kind: 'query', required: true, note: 'locator의 idp' },
          { name: 'p_numbers', kind: 'query', required: true, note: '쉼표로 구분한 P.No 정수 목록 (최대 200)' }
        ],
        response: 'AlignDetailResponse',
        auth: '토큰 가능',
        example: {
          path: '/cdsem/recipe-search/align-detail',
          query: {
            eqp_ip: '10.1.2.3', class_name: 'CLS', idw: 'IDW_A', idp: 'IDP_B', p_numbers: '1,2'
          }
        }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/recipe-image',
        summary: '원본 recipe 이미지 1장을 바이트로 반환합니다. JSON이 아니라 이미지 응답이며, 파일명은 param-info나 param-detail의 images에서 얻습니다.',
        args: [
          TOOL_SLUG_ARG,
          { name: 'eqp_ip', kind: 'query', required: true, note: 'locator의 eqp_ip' },
          { name: 'class_name', kind: 'query', required: true, note: 'locator의 class_name' },
          { name: 'idw', kind: 'query', required: true, note: 'locator의 idw' },
          { name: 'idp', kind: 'query', required: true, note: 'locator의 idp' },
          { name: 'name', kind: 'query', required: true, note: '이미지 파일명 (최대 256자)' }
        ],
        response: 'image/jpeg',
        auth: '토큰 가능',
        example: {
          path: '/cdsem/recipe-search/recipe-image',
          query: {
            eqp_ip: '10.1.2.3', class_name: 'CLS', idw: 'IDW_A', idp: 'IDP_B', name: 'IMMP0004.jpeg'
          }
        }
      },
```

- [ ] **Step 2: Typecheck and lint**

```bash
# from /Users/daeyoung/Codes/skewnono_v3_nuxt/front-dev-home
npm run typecheck
npm run lint
```

Both must pass. If `typecheck` complains that `example.body` is not assignable, note the existing `msr-files` entry already passes a `body` — match its shape rather than widening the type.

- [ ] **Step 3: Commit**

```bash
git add front-dev-home/app/pages/endpoints.vue
git commit -m "docs(endpoints): catalog the recipe-search parameter read API

Adds the three new tiered endpoints and the three that were shipped but never
documented (param-detail, align-detail, recipe-image), ordered cheap to
expensive so the no-tool-I/O tier is what a reader meets first."
```

---

### Task 4: The pure workbook builder

**Files:**

- Create: `front-dev-home/app/utils/recipeParamExport.ts`
- Test: `front-dev-home/app/utils/recipeParamExport.test.ts`

**Interfaces:**

- Consumes: `ParamDetail`, `ParamImage`, `SettingRow` from `~/composables/useRecipeParamDetail`, `IdpLocator` from `~/composables/useRecipeSearchApi`.
- Produces:
  - `EXPORT_IMAGE_SLOTS: { measure: readonly string[], addressing: readonly string[] }`
  - `ParamExportInput`, `ParamSheet`, `ParamImagePlacement`, `ParamWorkbook` interfaces
  - `buildParamWorkbook(input: ParamExportInput): ParamWorkbook`
  - `paramExportFilename(recipeId: string, parameter: string): string`

- [ ] **Step 1: Write the failing tests**

Create `app/utils/recipeParamExport.test.ts`:

```ts
// Pure-logic tests for recipeParamExport. Run: node --test app/utils/recipeParamExport.test.ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  buildParamWorkbook,
  paramExportFilename,
  EXPORT_IMAGE_SLOTS
} from './recipeParamExport.ts'

const LOCATOR = { eqp_ip: '10.1.2.3', class_name: 'CLS', idw: 'IDW_A', idp: 'IDP_B' }

const IDP = {
  Parameter: 'Para_13',
  SEQ: 4,
  Last_SEQ: 6,
  Region: 1,
  Addressing: true,
  Mother_Para: false,
  Double_Addressing: false,
  Meas_Counting: 5,
  dnumber_removed: false,
  img_add1: 'IMMP0004',
  img_add2: 'PRMP0000',
  image_add3: 'non',
  img_meas1: 'IMMS0000',
  img_meas2: 'PRMS0000'
}

const DETAIL = {
  parameter: 'Para_13',
  amp: { source: 'PRMS0000', rows: [{ key: 'ACCV', value: '800' }] },
  af_pr: {
    source: 'ENMP0000',
    rows: [
      { key: 'MODE', value: 'AUTO', section: 'ADD1' },
      { key: 'MODE', value: 'MANUAL', section: 'ADD2' }
    ]
  },
  images: [
    {
      slot: 'img_add1',
      stage: 'Addressing 1',
      name: 'IMMP0004.jpeg',
      cond: { source: 'cond.txt', rows: [{ key: 'MAG', value: '50k' }] }
    },
    {
      slot: 'img_meas1',
      stage: 'Measure 1',
      name: 'IMMS0000.jpeg',
      cond: { source: 'cond.txt', rows: [{ key: 'MAG', value: '120k' }] }
    }
  ]
}

const input = (slots: string[]) => ({
  recipeId: 'RCP_001',
  fabName: 'M11',
  toolLabel: 'CD-SEM',
  locator: LOCATOR,
  idp: IDP,
  detail: DETAIL,
  slots,
  exportedAt: '2026-08-02T06:00:00+09:00'
})

const sheet = (wb: ReturnType<typeof buildParamWorkbook>, name: string) =>
  wb.sheets.find(s => s.name === name)!

test('measurement-only export has the four sheets in order', () => {
  const wb = buildParamWorkbook(input([...EXPORT_IMAGE_SLOTS.measure]))
  assert.deepEqual(wb.sheets.map(s => s.name), ['개요', 'AMP', 'AF_PR', '이미지'])
})

test('개요 carries the idp row, the locator and the export time', () => {
  const wb = buildParamWorkbook(input([...EXPORT_IMAGE_SLOTS.measure]))
  const flat = new Map(sheet(wb, '개요').rows.map(r => [String(r[0]), r[1]]))
  assert.equal(flat.get('recipe_id'), 'RCP_001')
  assert.equal(flat.get('Parameter'), 'Para_13')
  assert.equal(flat.get('SEQ'), 4)
  assert.equal(flat.get('Meas_Counting'), 5)
  assert.equal(flat.get('eqp_ip'), '10.1.2.3')
  assert.equal(flat.get('exported_at'), '2026-08-02T06:00:00+09:00')
})

test('AMP keeps reader order and records its source file', () => {
  const wb = buildParamWorkbook(input([]))
  const rows = sheet(wb, 'AMP').rows
  assert.deepEqual(rows[0], ['key', 'value'])
  assert.deepEqual(rows[1], ['ACCV', '800'])
  assert.equal(sheet(wb, 'AMP').source, 'PRMS0000')
})

test('AF_PR keeps section as its own column, not a flattened label', () => {
  // A row's identity is (section, key): two addressing passes carry the SAME
  // inner key, so a flattened "ADD1.MODE" label would need string surgery to
  // read back, and a bare "MODE" would show one pass's value under both.
  const wb = buildParamWorkbook(input([]))
  const rows = sheet(wb, 'AF_PR').rows
  assert.deepEqual(rows[0], ['section', 'key', 'value'])
  assert.deepEqual(rows[1], ['ADD1', 'MODE', 'AUTO'])
  assert.deepEqual(rows[2], ['ADD2', 'MODE', 'MANUAL'])
})

test('이미지 includes only the requested slots', () => {
  const wb = buildParamWorkbook(input([...EXPORT_IMAGE_SLOTS.measure]))
  assert.deepEqual(wb.images.map(i => i.slot), ['img_meas1'])
  const text = sheet(wb, '이미지').rows.flat().join('\n')
  assert.ok(text.includes('Measure 1'))
  assert.ok(!text.includes('Addressing 1'))
})

test('addressing slots come along when asked for', () => {
  const wb = buildParamWorkbook(
    input([...EXPORT_IMAGE_SLOTS.measure, ...EXPORT_IMAGE_SLOTS.addressing])
  )
  assert.deepEqual(wb.images.map(i => i.slot), ['img_add1', 'img_meas1'])
})

test('a requested slot with no image is labelled rather than dropped', () => {
  // image_add3 is "non" in this recipe, so no ParamImage exists for it.
  const wb = buildParamWorkbook(
    input([...EXPORT_IMAGE_SLOTS.measure, ...EXPORT_IMAGE_SLOTS.addressing])
  )
  const text = sheet(wb, '이미지').rows.flat().join('\n')
  assert.ok(text.includes('Addressing 3'))
  assert.ok(text.includes('없음'))
  assert.ok(!wb.images.some(i => i.slot === 'image_add3'))
})

test('each placement anchors at a row that exists and is blank', () => {
  const wb = buildParamWorkbook(
    input([...EXPORT_IMAGE_SLOTS.measure, ...EXPORT_IMAGE_SLOTS.addressing])
  )
  const rows = sheet(wb, '이미지').rows
  for (const placement of wb.images) {
    assert.ok(placement.anchorRow < rows.length)
    assert.deepEqual(rows[placement.anchorRow], [])
  }
})

test('a null detail still produces a readable workbook', () => {
  const wb = buildParamWorkbook({ ...input([]), detail: null })
  assert.deepEqual(wb.sheets.map(s => s.name), ['개요', 'AMP', 'AF_PR', '이미지'])
  assert.ok(sheet(wb, 'AMP').rows.flat().join(' ').includes('파일 없음'))
})

test('filename is recipe and parameter, sanitised', () => {
  assert.equal(paramExportFilename('RCP/001', 'Para_13'), 'RCP_001_Para_13.xlsx')
})
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
# from /Users/daeyoung/Codes/skewnono_v3_nuxt/front-dev-home
node --test ../../skewnono-param-export/front-dev-home/app/utils/recipeParamExport.test.ts
```

Expected: `ERR_MODULE_NOT_FOUND`. (If running the test from the worktree is awkward without `node_modules`, copy the two files into the main tree only to run them, then move them back — do not commit them from the main tree.)

- [ ] **Step 3: Implement the builder**

Create `app/utils/recipeParamExport.ts`:

```ts
/**
 * One parameter of one recipe, as a workbook.
 *
 * Separate from `utils/recipeCompare.ts` on purpose: that builder is shaped
 * around an N-recipes-wide matrix, and its filenames-only image decision was
 * driven by a cost — one FTP pull per recipe per image — that does not apply to
 * a single parameter's at-most-three slots.
 *
 * The build is PURE and returns image PLACEMENTS rather than bytes, so the
 * layout is `node --test`-able while the fetching stays in the browser half.
 */

import type { IdpLocator } from '../composables/useRecipeSearchApi.ts'
import type { ParamDetail, SettingBlock } from '../composables/useRecipeParamDetail.ts'

/** The image-bearing slots, split the way the export offers them.
 *  `img_add2` and `img_meas2` are setting files and carry no picture. */
export const EXPORT_IMAGE_SLOTS = {
  measure: ['img_meas1'],
  addressing: ['img_add1', 'image_add3']
} as const

/** Stage labels, so a slot with no ParamImage can still be named in the sheet. */
const STAGE_OF: Record<string, string> = {
  img_add1: 'Addressing 1',
  image_add3: 'Addressing 3',
  img_meas1: 'Measure 1'
}

/** Sheet order, and the order slots appear within 이미지. */
const SLOT_ORDER = ['img_add1', 'image_add3', 'img_meas1']

export interface ParamExportInput {
  recipeId: string
  fabName: string
  toolLabel: string
  locator: IdpLocator
  /** The SELECTED idp_image_info row — one image definition, not the parameter. */
  idp: Record<string, unknown>
  detail: ParamDetail | null
  /** Which image slots to include. Order is normalised to SLOT_ORDER. */
  slots: string[]
  exportedAt: string
}

export interface ParamSheet {
  name: string
  /** The file these rows came from, shown in the sheet header. */
  source?: string | null
  rows: (string | number | boolean | null)[][]
}

export interface ParamImagePlacement {
  slot: string
  stage: string
  name: string
  /** 0-based index into the 이미지 sheet's rows. That row is blank and is where
   *  the picture is anchored; the writer sets its height. */
  anchorRow: number
}

export interface ParamWorkbook {
  sheets: ParamSheet[]
  images: ParamImagePlacement[]
}

const IDP_FIELDS = [
  'Parameter', 'SEQ', 'Last_SEQ', 'Region', 'Meas_Counting',
  'Addressing', 'Double_Addressing', 'Mother_Para', 'dnumber_removed',
  'img_add1', 'img_add2', 'image_add3', 'img_meas1', 'img_meas2'
]

const NO_FILE = '파일 없음'

function overviewSheet(input: ParamExportInput): ParamSheet {
  const rows: ParamSheet['rows'] = [
    ['field', 'value'],
    ['recipe_id', input.recipeId],
    ['fab_name', input.fabName],
    ['tool', input.toolLabel]
  ]
  for (const field of IDP_FIELDS) {
    const value = input.idp[field]
    rows.push([field, (value ?? '') as string | number | boolean])
  }
  rows.push(
    ['eqp_ip', input.locator.eqp_ip],
    ['class_name', input.locator.class_name],
    ['idw', input.locator.idw],
    ['idp', input.locator.idp],
    ['exported_at', input.exportedAt]
  )
  return { name: '개요', rows }
}

function blockSheet(name: string, block: SettingBlock | null | undefined, sectioned: boolean): ParamSheet {
  if (!block) return { name, source: null, rows: [[NO_FILE]] }
  const header = sectioned ? ['section', 'key', 'value'] : ['key', 'value']
  const rows: ParamSheet['rows'] = [header]
  for (const row of block.rows) {
    rows.push(sectioned ? [row.section ?? '', row.key, row.value] : [row.key, row.value])
  }
  return { name, source: block.source, rows }
}

function imageSheet(input: ParamExportInput): { sheet: ParamSheet, images: ParamImagePlacement[] } {
  const wanted = SLOT_ORDER.filter(slot => input.slots.includes(slot))
  const bySlot = new Map((input.detail?.images ?? []).map(image => [image.slot, image]))
  const rows: ParamSheet['rows'] = []
  const images: ParamImagePlacement[] = []

  for (const slot of wanted) {
    const stage = STAGE_OF[slot] ?? slot
    const image = bySlot.get(slot)
    rows.push([stage, slot])
    if (!image) {
      // The slot holds "non", or the detail never loaded. Named rather than
      // skipped, so a reader can tell "not requested" from "not present".
      rows.push(['없음'])
      rows.push([])
      continue
    }
    rows.push([image.name])
    images.push({ slot, stage, name: image.name, anchorRow: rows.length })
    rows.push([])
    if (image.cond) {
      rows.push(['key', 'value', image.cond.source])
      for (const row of image.cond.rows) rows.push([row.key, row.value])
    } else {
      rows.push([NO_FILE])
    }
    rows.push([])
  }

  if (!rows.length) rows.push(['포함된 이미지가 없습니다.'])
  return { sheet: { name: '이미지', rows }, images }
}

export function buildParamWorkbook(input: ParamExportInput): ParamWorkbook {
  const { sheet, images } = imageSheet(input)
  return {
    sheets: [
      overviewSheet(input),
      blockSheet('AMP', input.detail?.amp, false),
      blockSheet('AF_PR', input.detail?.af_pr, true),
      sheet
    ],
    images
  }
}

/** `RCP_001_Para_13.xlsx`. Recipe and parameter names come from the office and
 *  can carry characters a filesystem rejects, so they are sanitised here. */
export function paramExportFilename(recipeId: string, parameter: string): string {
  const safe = (value: string) => (value || 'unknown').replace(/[^\w.-]+/g, '_')
  return `${safe(recipeId)}_${safe(parameter)}.xlsx`
}
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
node --test ../../skewnono-param-export/front-dev-home/app/utils/recipeParamExport.test.ts
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/utils/recipeParamExport.ts \
        front-dev-home/app/utils/recipeParamExport.test.ts
git commit -m "feat(recipe-open): build one parameter's export workbook

Pure builder returning sheets plus image PLACEMENTS, so the layout is
node --test-able while byte fetching stays in the browser half. AF_PR keeps
section as its own column because a row's identity is (section, key)."
```

---

### Task 5: Write the file and wire the button

**Files:**

- Modify: `front-dev-home/app/utils/recipeParamExport.ts` (add `downloadParamWorkbook`)
- Modify: `front-dev-home/app/components/ebeam/RecipeOpenView.vue:83-128` (the `SELECTED` header) and its `<script setup>`

**Interfaces:**

- Consumes: `buildParamWorkbook`, `paramExportFilename`, `EXPORT_IMAGE_SLOTS` from Task 4; `recipeImageUrl`, `recipeApiBase` from `useRecipeParamDetail`.
- Produces: `downloadParamWorkbook(workbook: ParamWorkbook, filename: string, resolveImageUrl: (name: string) => string): Promise<void>`

- [ ] **Step 1: Add the writer to `recipeParamExport.ts`**

Append:

```ts
/** Roughly 4:3 at a readable size in Excel's default zoom. */
const IMAGE_BOX = { width: 320, height: 240 }
/** Excel row height is in points; the anchored row must clear the picture. */
const ANCHOR_ROW_POINTS = 190

/**
 * Write the workbook, embedding each placement's actual picture.
 *
 * `resolveImageUrl` is injected so this module never reaches for
 * `useRuntimeConfig()` — the pure half above stays importable under
 * `node --test`, which has no Nuxt runtime.
 *
 * A picture that cannot be fetched is labelled in place rather than failing the
 * export: the tool is a live FTP server and a single 404 should not cost the
 * user the other three sheets.
 */
export async function downloadParamWorkbook(
  workbook: ParamWorkbook,
  filename: string,
  resolveImageUrl: (name: string) => string
): Promise<void> {
  const mod = await import('exceljs')
  const ExcelJS = (mod as unknown as { default?: typeof mod }).default ?? mod
  const book = new ExcelJS.Workbook()

  const worksheets = new Map<string, ReturnType<typeof book.addWorksheet>>()
  for (const sheet of workbook.sheets) {
    const ws = book.addWorksheet(sheet.name.slice(0, 31))
    if (sheet.source) ws.addRow([`source: ${sheet.source}`])
    for (const row of sheet.rows) ws.addRow(row)
    // getColumn, not ws.columns.forEach: `columns` is only populated when the
    // sheet was given a column definition, and these sheets are built from
    // addRow alone. Three is the widest any sheet here gets (AF_PR).
    for (let column = 1; column <= 3; column += 1) ws.getColumn(column).width = 28
    worksheets.set(sheet.name, ws)
  }

  const ws = worksheets.get('이미지')
  if (ws) {
    for (const placement of workbook.images) {
      try {
        const response = await fetch(resolveImageUrl(placement.name), {
          credentials: 'include'
        })
        if (!response.ok) throw new Error(String(response.status))
        const buffer = await response.arrayBuffer()
        const extension = placement.name.toLowerCase().endsWith('.png') ? 'png' : 'jpeg'
        // exceljs types `buffer` as its own Node Buffer alias; the browser
        // build accepts an ArrayBuffer at runtime, so the cast is the whole
        // fix. If `npm run typecheck` still objects, cast the ARGUMENT object
        // rather than widening the import.
        const id = book.addImage({
          buffer: buffer as unknown as ArrayBuffer,
          extension
        })
        ws.getRow(placement.anchorRow + 1).height = ANCHOR_ROW_POINTS
        ws.addImage(id, {
          tl: { col: 0, row: placement.anchorRow },
          ext: IMAGE_BOX
        })
      } catch {
        ws.getRow(placement.anchorRow + 1).getCell(1).value
          = `${placement.name} (이미지를 가져오지 못했습니다)`
      }
    }
  }

  const buffer = await book.xlsx.writeBuffer()
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}
```

Note the off-by-one that matters: `addRow` is 1-based and a `source` line shifts every subsequent row, so `anchorRow + 1` is only correct when the 이미지 sheet has **no** `source`. It does not — `imageSheet` never sets one. Do not add one without also offsetting the placements.

- [ ] **Step 2: Re-run the pure tests**

```bash
node --test ../../skewnono-param-export/front-dev-home/app/utils/recipeParamExport.test.ts
```

Expected: still all pass — the writer is additive and untested here by design (it needs a browser).

- [ ] **Step 3: Wire the control into `RecipeOpenView.vue`**

In the `SELECTED` header block, wrap the existing title row so the button sits at its right. Replace the opening of that row:

```vue
            <div class="mb-3 flex flex-wrap items-baseline gap-2.5">
```

with:

```vue
            <div class="mb-3 flex flex-wrap items-center justify-between gap-2.5">
              <div class="flex flex-wrap items-baseline gap-2.5">
```

then close the inner `div` after the `MOTHER` pill's closing `</span>` and add the control before the outer close:

```vue
              </div>

              <div class="flex shrink-0 items-center gap-1">
                <UButton
                  size="xs"
                  color="neutral"
                  variant="outline"
                  icon="i-lucide-file-down"
                  :loading="exporting"
                  :disabled="paramPending || !paramDetail"
                  label="Excel 다운로드"
                  @click="downloadExcel"
                />
                <UPopover :content="{ align: 'end' }">
                  <UButton
                    size="xs"
                    color="neutral"
                    variant="ghost"
                    icon="i-lucide-chevron-down"
                    :disabled="exporting"
                    aria-label="다운로드 옵션"
                  />
                  <template #content>
                    <div class="w-64 space-y-2 p-3">
                      <p class="sk-label">
                        이미지 포함
                      </p>
                      <p class="sk-meta">
                        측정 이미지는 항상 포함됩니다. Addressing 이미지는 파일을 2장 더 받아오므로 필요할 때만 선택하십시오.
                      </p>
                      <UCheckbox
                        v-model="includeAddressing"
                        size="xs"
                        label="Addressing 이미지 포함"
                      />
                    </div>
                  </template>
                </UPopover>
              </div>
```

- [ ] **Step 4: Add the script half**

Extend the import from `useRecipeParamDetail` (it already imports `recipeApiBase`, `recipeImageUrl`) and add:

```ts
import {
  EXPORT_IMAGE_SLOTS,
  buildParamWorkbook,
  downloadParamWorkbook,
  paramExportFilename
} from '~/utils/recipeParamExport'
```

Then, beside the other refs:

```ts
// Addressing images are opt-in: they are two of the three images and the ones
// a reader most often does not need. 측정 이미지 is unconditional.
const includeAddressing = ref(false)
const exporting = ref(false)

const downloadExcel = async () => {
  const row = selectedIdp.value
  if (!row || !paramDetail.value || exporting.value) return
  exporting.value = true
  try {
    const slots = [
      ...EXPORT_IMAGE_SLOTS.measure,
      ...(includeAddressing.value ? EXPORT_IMAGE_SLOTS.addressing : [])
    ]
    const workbook = buildParamWorkbook({
      recipeId: titleRecipeName.value,
      fabName: props.fab,
      toolLabel: props.toolLabel,
      locator: locator.value,
      idp: row as unknown as Record<string, unknown>,
      detail: paramDetail.value,
      slots,
      exportedAt: new Date().toISOString()
    })
    const base = recipeApiBase()
    await downloadParamWorkbook(
      workbook,
      paramExportFilename(titleRecipeName.value, row.Parameter),
      name => recipeImageUrl(base, toolSlug.value, locator.value, name)
    )
  } catch (err) {
    console.error('Excel export failed', err)
  } finally {
    exporting.value = false
  }
}
```

- [ ] **Step 5: Typecheck, lint, and run every frontend test**

```bash
# from /Users/daeyoung/Codes/skewnono_v3_nuxt/front-dev-home
npm run typecheck
npm run lint
npm test
```

All three must pass.

- [ ] **Step 6: Commit**

```bash
git add front-dev-home/app/utils/recipeParamExport.ts \
        front-dev-home/app/components/ebeam/RecipeOpenView.vue
git commit -m "feat(recipe-open): download the selected parameter as xlsx

Embeds the measurement image always and the two addressing images on request;
an image the tool will not serve is labelled in place rather than failing the
export."
```

---

## Verification phase

Run after Task 5. Not optional — the image-embedding path has no automated coverage.

- [ ] **Full backend suite** (from `/Users/daeyoung/Codes/skewnono_v3_nuxt`, against the worktree):

```bash
cd ../skewnono-param-export && /Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest -q
```

Expect ~2196 passing. Note that a worktree legitimately shows a different **skip** count than the main checkout — gitignored `office.py` files do not exist there — so compare `passed + skipped`, not `passed` alone.

- [ ] **Browser check** via the `verify` skill: start Flask on :5050 and Nuxt on :3000, open `/ebeam/cd-sem/m11/recipe-search`, open a recipe, and confirm:
  1. the export button renders in the `SELECTED` header and is disabled while the settings panel is pending;
  2. a default download produces an `.xlsx` whose 이미지 sheet holds one real picture;
  3. with 「Addressing 이미지 포함」 checked, the file holds the addressing images too, and a `non` slot reads `없음`;
  4. `/endpoints` shows the six new Recipe Search entries with working curl/Python snippets.

- [ ] **API smoke**, respecting the 20 req / 5 s limit:

```bash
curl -s -b LASTUSER=local-dev "http://localhost:5050/api/cdsem/recipe-search/parameters?recipe_name=RCP_001" | head -c 400
curl -s -b LASTUSER=local-dev "http://localhost:5050/api/cdsem/recipe-search/param-info?recipe_name=RCP_001&parameter=Para_1&include=amp" | head -c 400
```

- [ ] **`/simplify`** over the branch diff, then **`/code-review`**. Apply what survives.

- [ ] **Land it:**

```bash
cd /Users/daeyoung/Codes/skewnono_v3_nuxt
git merge --ff-only work/param-export && git push
git worktree remove ../skewnono-param-export && git branch -d work/param-export
git worktree list   # must show the main tree alone
```

## Self-review notes

Checked against the spec:

- Tier 0 / 1 / 2 endpoints → Tasks 1–2. Roll-up naming (`total_rows`, `distinct_parameters`) → Task 1 Step 2 tests.
- `include=` trimming slots rather than filtering output → Task 1, asserted twice (request shape *and* response shape).
- `occurrences` list + the multi-row parameter → Task 1 (`test_param_info_returns_one_occurrence_per_row`) and Task 2.
- 404 / 400 / 503 → Task 2.
- Six catalog entries → Task 3.
- Four sheets, `AF_PR` three columns, no `측정 위치` sheet, embedded pixels, 측정 always / Addressing optional → Tasks 4–5.
- No provider change → enforced by the Global Constraints and recorded in `MIGRATION.md` (Task 2 Step 5).
