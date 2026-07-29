# Raw-recipe folder — real AMP, focus/PR and beam conditions — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the fabricated `amp_info` / `align_images` on the recipe-open and
recipe-compare screens with real AMP, AF/PR and beam-condition data parsed from the
raw-recipe folder on the measuring tool's own FTP server.

**Architecture:** `/recipe-detail` starts returning the FTP locator it already resolves
and discards, so every follow-up call reaches the raw folder without re-downloading the
`.idp`. Path arithmetic lives in a new pure `rawfiles.py` with no I/O, so the part most
likely to be wrong is fully testable from home. Three new endpoints — a list-shaped
`param-detail` POST, an `align-detail` GET and a bytes-streaming `recipe-image` GET —
serve settings and images lazily on click.

**Tech Stack:** Flask blueprints (auto-discovered), pandas, `ftp_handler` (vendored),
Nuxt 4 + NuxtUI, `useAsyncData`, pytest, `node --test`.

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-07-29-raw-recipe-folder-amp-and-conditions-design.md`.
  Where this plan and the spec disagree, the spec wins.
- **Worktree.** This touches ~15 files. Per CLAUDE.md, do the whole change in an isolated
  worktree: `git worktree add ../skewnono-rawrecipe -b work/raw-recipe-folder`, work and
  commit there, then `git -C . merge --ff-only work/raw-recipe-folder && git push`, then
  `git worktree remove ../skewnono-rawrecipe && git branch -d work/raw-recipe-folder`.
  The task is not done until `git worktree list` shows the main tree alone.
- **Never stage broadly.** `git add -A`, `git add .`, `git commit -a` and bare `git stash`
  are banned — several agent sessions share this working tree. Always pass explicit paths.
- **Backend tests:** `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q`.
  The `-m` form is required; it is what puts the repo root on `sys.path`.
- **Frontend:** from `front-dev-home/` — `npm test`, `npm run typecheck`, `npm run lint`.
- **Markdown:** `npm run lint:md` from the repo root after any `.md` edit.
- **Naming facts, verbatim from the spec (user-confirmed 2026-07-29):** values are
  8-character `{kind}{stage}{NNNN}` names with no extension; `"non"` (French, **not**
  `"none"`) is the empty sentinel; numbering is zero-padded to **four** digits;
  `img_add2`'s `PR` prefix becomes `EN`; `img_meas2` is used as-is; images add `.jpeg`;
  the condition sidecar is `.{image}.jpeg/cond.txt` in a **`.`-prefixed hidden directory**.
- **Three image slots:** `img_add1`, `image_add3`, `img_meas1`. `img_add2` and `img_meas2`
  are setting keys only and yield no image.
- **Do not edit `data.py`'s dispatch pattern** — add functions following it exactly.
- **`office.py` is gitignored.** Edit `office_example.py`; it is the tracked template.
- **Colours** come from `--sk-*` tokens only. `DESIGN.md` governs the frontend.

---

### Task 1: `rawfiles.py` — pure path arithmetic

The foundation. No I/O, no office dependency, so it carries the full weight of the
naming rules and is 100% testable at home. Every later task consumes it.

**Files:**

- Create: `back_dev_home/ebeam/hitachi/recipe_search/rawfiles.py`
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_rawfiles.py`

**Interfaces:**

- Consumes: `back_dev_home.msr_image.paths.cond_path` (existing,
  `/dir/foo.jpeg -> /dir/.foo.jpeg/cond.txt`).
- Produces: `EMPTY_SLOT`, `IMAGE_SLOT_KEYS`, `is_empty(value) -> bool`,
  `raw_dir(class_name, idw_stem, idp_stem) -> str`, `image_name(value) -> str | None`,
  `setting_name(value, *, pr_to_en=False) -> str | None`,
  `align_names(p_no) -> tuple[str, str]`, `remote_path(raw, name) -> str`,
  `cond_remote_path(raw, image_file_name) -> str`.

- [ ] **Step 1: Write the failing test**

```python
"""Naming rules for the raw-recipe folder. Pure — these run anywhere.

Every assertion here encodes an office fact from
docs/superpowers/specs/2026-07-29-raw-recipe-folder-amp-and-conditions-design.md.
A change to one of them is a change to what the office was observed to do,
not a refactor.
"""

import pytest

from back_dev_home.ebeam.hitachi.recipe_search import rawfiles


def test_raw_dir_is_the_idp_sibling_folder():
    assert rawfiles.raw_dir("CLS", "IDW_A", "IDP_B") == (
        "/HITACHI/DEVICE/HD/CLS/data/IDW_A/IDP_B"
    )


def test_image_name_appends_jpeg():
    assert rawfiles.image_name("IMMP0001") == "IMMP0001.jpeg"
    assert rawfiles.image_name("I2MP0000") == "I2MP0000.jpeg"
    assert rawfiles.image_name("IMMS0000") == "IMMS0000.jpeg"


@pytest.mark.parametrize("value", ["non", "NON", "  non  ", "", None])
def test_empty_sentinel_yields_no_file(value):
    """'non' is French, not a truncated 'none' — and 'none' is NOT a sentinel."""
    assert rawfiles.is_empty(value) is True
    assert rawfiles.image_name(value) is None
    assert rawfiles.setting_name(value) is None


def test_none_string_is_not_the_sentinel():
    assert rawfiles.is_empty("none") is False
    assert rawfiles.image_name("none") == "none.jpeg"


def test_img_meas2_is_used_as_is():
    assert rawfiles.setting_name("PRMS0000") == "PRMS0000"


def test_img_add2_translates_pr_to_en():
    assert rawfiles.setting_name("PRMP0000", pr_to_en=True) == "ENMP0000"


def test_pr_to_en_rejects_a_value_that_does_not_start_with_pr():
    """Translating blindly would fetch a PR file while believing it is an EN
    file. Refusing surfaces the surprise instead of serving wrong settings."""
    assert rawfiles.setting_name("IMMP0001", pr_to_en=True) is None


def test_align_names_pad_to_four_digits():
    assert rawfiles.align_names(1) == ("IMAP0001.jpeg", "ENAP0001")


def test_align_names_stay_eight_characters_past_nine():
    """'ENAP000' + str(p) breaks at p=10; four-digit padding is the rule."""
    assert rawfiles.align_names(12) == ("IMAP0012.jpeg", "ENAP0012")


def test_cond_sidecar_lives_in_a_dot_prefixed_hidden_directory():
    raw = rawfiles.raw_dir("CLS", "IDW_A", "IDP_B")
    assert rawfiles.cond_remote_path(raw, "IMMP0001.jpeg") == (
        "/HITACHI/DEVICE/HD/CLS/data/IDW_A/IDP_B/.IMMP0001.jpeg/cond.txt"
    )


def test_image_slot_keys_exclude_the_two_setting_only_columns():
    assert rawfiles.IMAGE_SLOT_KEYS == ("img_add1", "image_add3", "img_meas1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search/tests/test_rawfiles.py -q`

Expected: FAIL — `ModuleNotFoundError: No module named
'back_dev_home.ebeam.hitachi.recipe_search.rawfiles'`.

- [ ] **Step 3: Write minimal implementation**

```python
"""Pure path arithmetic for the raw-recipe folder beside the .idp.

No I/O, no phase, no office dependency — which is the point. Naming is the part
of this feature most likely to be wrong and the part that cannot be checked from
home against a live tool, so it is isolated here where it needs no tool at all.
Same reasoning that already separates providers/office_example.py's
_to_detail_response.

Layout (user-confirmed 2026-07-29), under
``/HITACHI/DEVICE/HD/{class}/data/{idw}/{idp}/``::

    IMMP0001.jpeg          img_add1    addressing image 1
    .IMMP0001.jpeg/cond.txt            its beam condition (hidden sibling dir)
    ENMP0000               img_add2    AF/PR setting  (value is PRMP0000)
    I2MP0000.jpeg          image_add3  addressing image 3
    IMMS0000.jpeg          img_meas1   measurement image
    PRMS0000               img_meas2   AMP setting    (value used as-is)
    IMAP0001.jpeg          P.No = 1    align image
    ENAP0001               P.No = 1    align setting
"""

from __future__ import annotations

from back_dev_home.msr_image.paths import cond_path

__all__ = [
    "EMPTY_SLOT",
    "IMAGE_SLOT_KEYS",
    "align_names",
    "cond_remote_path",
    "image_name",
    "is_empty",
    "raw_dir",
    "remote_path",
    "setting_name",
]

# Shared with msr_image (office 확인 2026-07-24): images/{msr} and data/{idw}
# are siblings under one tree, on the same servers.
_ROOT = "/HITACHI/DEVICE/HD"

# French "non", NOT a truncated "none" (user-confirmed 2026-07-29). A slot
# holding this has no file and must not produce an FTP request.
EMPTY_SLOT = "non"

# The columns that name an image. img_add2 and img_meas2 are setting keys and
# have no image; image_add3 breaks the img_* naming run but IS an image.
IMAGE_SLOT_KEYS: tuple[str, ...] = ("img_add1", "image_add3", "img_meas1")


def is_empty(value: str | None) -> bool:
    return not value or value.strip().lower() == EMPTY_SLOT


def raw_dir(class_name: str, idw_stem: str, idp_stem: str) -> str:
    return f"{_ROOT}/{class_name}/data/{idw_stem}/{idp_stem}"


def remote_path(raw: str, name: str) -> str:
    return f"{raw}/{name}"


def image_name(value: str | None) -> str | None:
    """``'IMMP0001' -> 'IMMP0001.jpeg'``; empty slot -> ``None``."""
    if is_empty(value):
        return None
    return f"{value.strip()}.jpeg"


def setting_name(value: str | None, *, pr_to_en: bool = False) -> str | None:
    """The setting file's name. ``pr_to_en`` for img_add2, off for img_meas2.

    Returns ``None`` rather than translating a value that does not start with
    ``PR``: a blind replace would request a PR file while the caller believes it
    holds EN settings, which reads as plausible wrong data instead of an error.
    """
    if is_empty(value):
        return None
    name = value.strip()
    if pr_to_en:
        if not name.startswith("PR"):
            return None
        name = f"EN{name[2:]}"
    return name


def align_names(p_no: int) -> tuple[str, str]:
    """``P.No -> (image, setting)``, both zero-padded to four digits."""
    return f"IMAP{p_no:04d}.jpeg", f"ENAP{p_no:04d}"


def cond_remote_path(raw: str, image_file_name: str) -> str:
    """The image's hidden condition sidecar: ``.{image}.jpeg/cond.txt``."""
    return cond_path(remote_path(raw, image_file_name))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search/tests/test_rawfiles.py -q`

Expected: PASS, 11 tests.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/recipe_search/rawfiles.py \
        back_dev_home/ebeam/hitachi/recipe_search/tests/test_rawfiles.py
git commit -m "feat(recipe-search): add pure path arithmetic for the raw-recipe folder"
```

---

### Task 2: Contract types for settings, images and the locator

Additive only — nothing is removed yet, so both providers keep working. Task 7 does
the removals once the replacement path exists.

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/recipe_search/contracts.py`
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_contracts_shape.py`

**Interfaces:**

- Produces: `IdpLocator`, `SettingRow`, `SettingBlock`, `ParamImage`,
  `ParamDetailRequestItem`, `ParamDetailResponse`, `AlignPoint`, `AlignDetailResponse`.

- [ ] **Step 1: Write the failing test**

```python
"""The new contract types exist and carry the keys the frontend indexes."""

from back_dev_home.ebeam.hitachi.recipe_search import contracts


def test_setting_block_is_open_key_value():
    """Open rows, not fixed columns: the readers' real field names are still
    OFFICE-VERIFY, and an unknown key must render rather than vanish."""
    assert set(contracts.SettingRow.__annotations__) == {"key", "value"}
    assert set(contracts.SettingBlock.__annotations__) == {"source", "rows"}


def test_param_detail_carries_amp_af_pr_and_images():
    assert set(contracts.ParamDetailResponse.__annotations__) == {
        "parameter", "amp", "af_pr", "images",
    }


def test_param_image_names_the_file_the_image_endpoint_takes():
    assert set(contracts.ParamImage.__annotations__) == {
        "slot", "stage", "name", "cond",
    }


def test_align_point_carries_both_the_cond_and_the_en_setting():
    assert set(contracts.AlignPoint.__annotations__) == {
        "P_No", "image", "cond", "setting",
    }


def test_locator_carries_the_four_ftp_path_fields():
    assert set(contracts.IdpLocator.__annotations__) == {
        "eqp_ip", "class_name", "idw", "idp",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search/tests/test_contracts_shape.py -q`

Expected: FAIL — `AttributeError: module ... has no attribute 'SettingRow'`.

- [ ] **Step 3: Write minimal implementation**

Append to `contracts.py`, and add every new name to `__all__`:

```python
# The resolved FTP location of a recipe's .idp, handed to the client by
# recipe-detail so follow-up calls reach the raw folder without re-downloading
# or re-parsing the .idp. Mirrors msr_image, where the client holds
# eqp_ip/class_name/msr and sends them on each image GET.
IdpLocator = TypedDict("IdpLocator", {
    "eqp_ip": str,
    "class_name": str,
    "idw": str,
    "idp": str
})

# One parsed setting. Open key/value rather than fixed columns: the field names
# office_utils.idp_amp_reader returns are still OFFICE-VERIFY, and an open shape
# renders an unexpected key instead of dropping it. Row ORDER is the reader's
# own — nothing here sorts or renames.
SettingRow = TypedDict("SettingRow", {
    "key": str,
    "value": str
})

SettingBlock = TypedDict("SettingBlock", {
    # The file these rows came from, e.g. "PRMS0000" — shown on screen so a
    # surprising value can be traced back to a file without a server log.
    "source": str,
    "rows": list[SettingRow]
})

# One image slot of one parameter. ``name`` is the full filename, ready to hand
# straight to the recipe-image endpoint.
ParamImage = TypedDict("ParamImage", {
    "slot": str,
    "stage": str,
    "name": str,
    "cond": SettingBlock | None
})

# One element of the param-detail POST body. ``slots`` is the row's five img_*
# values verbatim from idp_image_info — the client already holds them, so the
# server never re-parses the .idp to recover them.
ParamDetailRequestItem = TypedDict("ParamDetailRequestItem", {
    "locator": IdpLocator,
    "parameter": str,
    "slots": dict[str, str]
})

class ParamDetailResponse(TypedDict):
    parameter: str
    amp: SettingBlock | None
    af_pr: SettingBlock | None
    images: list[ParamImage]


AlignPoint = TypedDict("AlignPoint", {
    "P_No": int,
    "image": str | None,
    "cond": SettingBlock | None,
    "setting": SettingBlock | None
})


class AlignDetailResponse(TypedDict):
    points: list[AlignPoint]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q`

Expected: PASS — the new file, and every pre-existing test still green (this task
removes nothing).

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/recipe_search/contracts.py \
        back_dev_home/ebeam/hitachi/recipe_search/tests/test_contracts_shape.py
git commit -m "feat(recipe-search): add setting-block, param-detail and locator contracts"
```

---

### Task 3: Correct the mock's naming convention

**This is the home-data correction the user asked for explicitly.** The mock emits
`IMG_ADD1_0001.jpg` where the office emits `IMMP0001`. Until this is fixed, Task 1's
path layer has nothing real to run against at home and the frontend is built against a
naming convention that does not exist.

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/recipe_search/providers/mock.py` —
  `generate_idp_image_info()` (currently lines 210-241)
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_mock_naming.py`

**Interfaces:**

- Consumes: `rawfiles.EMPTY_SLOT` from Task 1.
- Produces: `generate_idp_image_info()` emitting office-shaped slot values.

- [ ] **Step 1: Write the failing test**

```python
"""The mock's img_* values must follow the office naming convention.

Not cosmetic: rawfiles.py derives every path from these strings, so a mock that
emits IMG_ADD1_0001.jpg makes the whole path layer untestable at home and lets a
wrong derivation pass here and fail only at the office.
"""

import re

from back_dev_home.ebeam.hitachi.recipe_search import rawfiles
from back_dev_home.ebeam.hitachi.recipe_search.providers import mock


PREFIX = {
    "img_add1": "IMMP",
    "img_add2": "PRMP",
    "img_meas1": "IMMS",
    "img_meas2": "PRMS",
    "image_add3": "I2MP",
}


def _rows():
    return mock.generate_idp_image_info(num_records=20)


def test_every_slot_is_prefix_plus_four_digits_or_the_sentinel():
    for row in _rows():
        for column, prefix in PREFIX.items():
            value = row[column]
            assert value == rawfiles.EMPTY_SLOT or re.fullmatch(
                rf"{prefix}\d{{4}}", value
            ), f"{column}={value!r}"


def test_no_slot_carries_a_file_extension():
    for row in _rows():
        for column in PREFIX:
            assert "." not in row[column], f"{column}={row[column]!r}"


def test_the_empty_sentinel_is_actually_exercised():
    """A mock that never emits 'non' leaves the no-file path unreachable at
    home, which is where that path has to be proven."""
    values = [row[column] for row in _rows() for column in PREFIX]
    assert rawfiles.EMPTY_SLOT in values


def test_generation_is_stable_for_a_given_seed():
    import random
    first = mock.generate_idp_image_info(num_records=5, rng=random.Random(7))
    second = mock.generate_idp_image_info(num_records=5, rng=random.Random(7))
    assert first == second
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search/tests/test_mock_naming.py -q`

Expected: FAIL on the first test — `img_add1='IMG_ADD1_0001.jpg'`.

- [ ] **Step 3: Write minimal implementation**

Replace the five slot assignments in `generate_idp_image_info()`:

```python
# Office naming (user-confirmed 2026-07-29): {kind}{stage}{NNNN}, no extension.
# IM/I2 name images, PR names a setting key, MP/MS/AP are the stages.
_SLOT_PREFIX: dict[str, str] = {
    "img_add1": "IMMP",
    "img_add2": "PRMP",
    "img_meas1": "IMMS",
    "img_meas2": "PRMS",
    "image_add3": "I2MP",
}

# Slots that legitimately hold no file. Parameters routinely lack an addressing
# image or an AF/PR setting, so the sentinel has to appear at home or the
# no-file path is never exercised until the office run.
_MAY_BE_EMPTY: tuple[str, ...] = ("img_add2", "image_add3")


def _slot(column: str, seq: int, rng: random.Random) -> str:
    if column in _MAY_BE_EMPTY and rng.random() < 0.25:
        return rawfiles.EMPTY_SLOT
    return f"{_SLOT_PREFIX[column]}{seq:04d}"
```

and inside the loop body, replacing the five `f"IMG_..."` literals:

```python
            "img_add1": _slot("img_add1", seq, active_rng),
            "img_add2": _slot("img_add2", seq, active_rng),
            "img_meas1": _slot("img_meas1", seq, active_rng),
            "img_meas2": _slot("img_meas2", seq, active_rng),
            ...
            "image_add3": _slot("image_add3", seq, active_rng),
```

Add `from back_dev_home.ebeam.hitachi.recipe_search import rawfiles` to the imports.

Update the module docstring to record that slot values now imitate the office naming
convention (shape only — the numbering is still fabricated).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q`

Expected: PASS. If `test_idp_mapping.py` or `test_contract.py` asserts on the old
literals, update those assertions — the old values were wrong.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/recipe_search/providers/mock.py \
        back_dev_home/ebeam/hitachi/recipe_search/tests/test_mock_naming.py
git commit -m "fix(recipe-search): give the mock the office img_* naming convention"
```

---

### Task 4: Home stand-in for `idp_amp_reader` + mock providers

**Files:**

- Create: `office_utils/idp_amp_reader.py` (**gitignored** — never committed)
- Modify: `office_utils/__init__.py` (add to `__all__` and the contents list)
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/providers/mock.py`
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_param_detail_mock.py`

**Interfaces:**

- Consumes: `rawfiles.*` (Task 1), the contract types (Task 2).
- Produces: `get_param_detail(items) -> list[ParamDetailResponse]`,
  `get_align_detail(locator, p_numbers) -> AlignDetailResponse`,
  `fetch_recipe_image(locator, name) -> tuple[bytes, str]` (bytes, content-type).
  Reader stand-ins: `read_amp_info(source)`, `read_af_pr_condition(source)`,
  `read_meas_image_condition(source)`, each returning `dict[str, str]`.

- [ ] **Step 1: Write the failing test**

```python
"""The mock's param-detail obeys the naming rules and the empty sentinel."""

from back_dev_home.ebeam.hitachi.recipe_search import rawfiles
from back_dev_home.ebeam.hitachi.recipe_search.providers import mock


LOCATOR = {"eqp_ip": "10.1.2.3", "class_name": "CLS", "idw": "IDW_A", "idp": "IDP_B"}


def _detail(slots):
    item = {"locator": LOCATOR, "parameter": "Para_1", "slots": slots}
    return mock.get_param_detail([item])[0]


def test_amp_comes_from_img_meas2_used_as_is():
    detail = _detail({"img_meas2": "PRMS0007"})
    assert detail["amp"]["source"] == "PRMS0007"
    assert detail["amp"]["rows"], "amp rows must not be empty"
    assert set(detail["amp"]["rows"][0]) == {"key", "value"}


def test_af_pr_comes_from_img_add2_translated_pr_to_en():
    detail = _detail({"img_add2": "PRMP0007"})
    assert detail["af_pr"]["source"] == "ENMP0007"


def test_the_empty_sentinel_produces_no_block_and_no_image():
    detail = _detail({"img_meas2": "non", "img_add2": "non", "img_add1": "non"})
    assert detail["amp"] is None
    assert detail["af_pr"] is None
    assert detail["images"] == []


def test_only_the_three_image_slots_produce_images():
    detail = _detail({
        "img_add1": "IMMP0001", "img_add2": "PRMP0001", "image_add3": "I2MP0001",
        "img_meas1": "IMMS0001", "img_meas2": "PRMS0001",
    })
    assert [image["name"] for image in detail["images"]] == [
        "IMMP0001.jpeg", "I2MP0001.jpeg", "IMMS0001.jpeg",
    ]
    assert [image["slot"] for image in detail["images"]] == list(
        rawfiles.IMAGE_SLOT_KEYS
    )


def test_each_image_carries_its_condition_block():
    detail = _detail({"img_meas1": "IMMS0001"})
    assert detail["images"][0]["cond"]["source"] == ".IMMS0001.jpeg/cond.txt"


def test_align_detail_returns_one_point_per_p_number():
    align = mock.get_align_detail(LOCATOR, [3, 1, 1, 2])
    assert [point["P_No"] for point in align["points"]] == [1, 2, 3]
    assert align["points"][0]["image"] == "IMAP0001.jpeg"
    assert align["points"][0]["setting"]["source"] == "ENAP0001"


def test_recipe_image_returns_bytes_and_a_content_type():
    data, content_type = mock.fetch_recipe_image(LOCATOR, "IMMP0001.jpeg")
    assert isinstance(data, bytes) and data
    assert content_type == "image/svg+xml"


def test_param_detail_is_stable_across_calls():
    slots = {"img_meas2": "PRMS0007"}
    assert _detail(slots) == _detail(slots)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search/tests/test_param_detail_mock.py -q`

Expected: FAIL — `AttributeError: module ... has no attribute 'get_param_detail'`.

- [ ] **Step 3: Write minimal implementation**

First `office_utils/idp_amp_reader.py`. It mirrors `read_idp_info.py`'s honesty
contract — same signatures, fabricated values, parses nothing:

```python
"""HOME STAND-IN for the office-only AMP/condition parser — NEVER COMMITTED.

At the office ``office_utils/idp_amp_reader.py`` reads the raw-recipe files that
sit beside the .idp and returns their parameter settings::

    read_amp_info(source)              # PRMS0000  — amp / measurement method
    read_af_pr_condition(source)       # ENMP0000, ENAP0001 — focus + pattern rec.
    read_meas_image_condition(source)  # .IMMS0000.jpeg/cond.txt — beam condition

Each accepts a path, bytes, or a string. This stand-in accepts the same three
and reads none of them — the file formats are unknown at home, and pretending to
parse them would be a lie with a longer tail than pretending to have parsed.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
Imitate the office FIELD NAMES. They are still OFFICE-VERIFY (see
docs/superpowers/specs/2026-07-29-raw-recipe-folder-amp-and-conditions-design.md),
so the keys below are obvious placeholders — ``AMP_FIELD_1`` rather than a
plausible-looking ``Mag``. A mock that invents credible optical field names
teaches the frontend to expect columns the office may never send; that is
exactly how AmpRow's sixteen invented fields survived for months.

The adapter normalises whatever these return through ``_to_rows`` , which
handles a dict, a DataFrame and a list of pairs — so the office returning a
different container than this one does is not a breaking surprise.

Gitignored via the ``/office_utils/`` rule in .gitignore.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

__all__ = ["read_af_pr_condition", "read_amp_info", "read_meas_image_condition"]

logger = logging.getLogger(__name__)


def _key(source: str | bytes | Path) -> str:
    """A stable identity for whatever was handed in, used only as a seed."""
    if isinstance(source, bytes):
        raw = source
    else:
        raw = str(source).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _rows(source, prefix: str, count: int) -> dict[str, str]:
    logger.warning(
        "office_utils.idp_amp_reader is the HOME STAND-IN — %.60s was NOT "
        "parsed; the settings below are fabricated.", source,
    )
    digest = _key(source)
    return {
        f"{prefix}_FIELD_{i + 1}": digest[i * 4:(i + 1) * 4].upper()
        for i in range(count)
    }


def read_amp_info(source) -> dict[str, str]:
    return _rows(source, "AMP", 8)


def read_af_pr_condition(source) -> dict[str, str]:
    return _rows(source, "AFPR", 6)


def read_meas_image_condition(source) -> dict[str, str]:
    return _rows(source, "COND", 5)
```

Then in `mock.py`, add the three provider functions. The mock does not touch FTP; it
derives names with `rawfiles` (so home exercises the real derivation) and feeds the
*names* to the stand-in reader in place of file contents:

```python
def _block(source: str | None, reader) -> SettingBlock | None:
    """A SettingBlock from a reader, or None when the slot names no file."""
    if source is None:
        return None
    return {
        "source": source,
        "rows": [{"key": k, "value": str(v)} for k, v in reader(source).items()],
    }


def get_param_detail(
    items: list[ParamDetailRequestItem]
) -> list[ParamDetailResponse]:
    from office_utils.idp_amp_reader import (
        read_af_pr_condition, read_amp_info, read_meas_image_condition,
    )

    out: list[ParamDetailResponse] = []
    for item in items:
        slots = item.get("slots") or {}
        images: list[ParamImage] = []
        for slot in rawfiles.IMAGE_SLOT_KEYS:
            name = rawfiles.image_name(slots.get(slot))
            if name is None:
                continue
            stage = next(s["stage"] for s in IMAGE_SLOTS if s["key"] == slot)
            images.append({
                "slot": slot,
                "stage": stage,
                "name": name,
                # Office-side this is the sidecar's remote path; the mock keeps
                # the same relative form so the screen shows the same string.
                "cond": _block(f".{name}/cond.txt", read_meas_image_condition),
            })
        out.append({
            "parameter": item.get("parameter", ""),
            "amp": _block(
                rawfiles.setting_name(slots.get("img_meas2")), read_amp_info
            ),
            "af_pr": _block(
                rawfiles.setting_name(slots.get("img_add2"), pr_to_en=True),
                read_af_pr_condition,
            ),
            "images": images,
        })
    return out


def get_align_detail(
    locator: IdpLocator, p_numbers: list[int]
) -> AlignDetailResponse:
    from office_utils.idp_amp_reader import (
        read_af_pr_condition, read_meas_image_condition,
    )

    points: list[AlignPoint] = []
    for p_no in sorted({int(p) for p in p_numbers}):
        image, setting = rawfiles.align_names(p_no)
        points.append({
            "P_No": p_no,
            "image": image,
            "cond": _block(f".{image}/cond.txt", read_meas_image_condition),
            "setting": _block(setting, read_af_pr_condition),
        })
    return {"points": points}


def fetch_recipe_image(locator: IdpLocator, name: str) -> tuple[bytes, str]:
    """A seeded SVG placeholder, exactly as msr_image's mock does it — it
    renders without pretending to be a SEM photograph."""
    hue = _seed_for_values("recipe-image", name) % 360
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240">'
        f'<rect width="320" height="240" fill="hsl({hue} 30% 18%)"/>'
        f'<text x="160" y="124" fill="hsl({hue} 60% 78%)" font-size="15" '
        f'font-family="monospace" text-anchor="middle">{name}</text></svg>'
    )
    return svg.encode("utf-8"), "image/svg+xml"
```

Add the new names to `mock.py`'s `__all__` and import the new contract types.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q`

Expected: PASS.

- [ ] **Step 5: Commit**

`office_utils/` is gitignored, so **only `mock.py` and the test are staged.** Verify
with `git status --porcelain office_utils/` — it must print nothing.

```bash
git add back_dev_home/ebeam/hitachi/recipe_search/providers/mock.py \
        back_dev_home/ebeam/hitachi/recipe_search/tests/test_param_detail_mock.py
git commit -m "feat(recipe-search): serve param-detail, align-detail and images from the mock"
```

---

### Task 5: Dispatcher and routes

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/recipe_search/data.py`
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/routes.py`
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_routes.py` (extend)

**Interfaces:**

- Consumes: `mock.get_param_detail`, `mock.get_align_detail`, `mock.fetch_recipe_image`
  (Task 4); `msr_image.paths.validate_segment` / `validate_tool_ip`;
  `msr_image.errors.InvalidLocator` / `InvalidToolIp`.
- Produces: `POST /api/<tool_slug>/recipe-search/param-detail`,
  `GET /api/<tool_slug>/recipe-search/align-detail`,
  `GET /api/<tool_slug>/recipe-search/recipe-image`.

- [ ] **Step 1: Write the failing test**

```python
def test_param_detail_returns_one_entry_per_item(client):
    response = client.post(
        "/api/cdsem/recipe-search/param-detail",
        json={"items": [
            {"locator": LOCATOR, "parameter": "Para_1",
             "slots": {"img_meas2": "PRMS0001"}},
            {"locator": LOCATOR, "parameter": "Para_2",
             "slots": {"img_meas2": "PRMS0002"}},
        ]},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert [entry["parameter"] for entry in body] == ["Para_1", "Para_2"]


def test_param_detail_rejects_an_empty_item_list(client):
    response = client.post("/api/cdsem/recipe-search/param-detail",
                           json={"items": []})
    assert response.status_code == 400


def test_param_detail_rejects_a_path_separator_in_a_slot(client):
    """The client names FTP paths here, so this is the traversal guard."""
    response = client.post(
        "/api/cdsem/recipe-search/param-detail",
        json={"items": [{"locator": LOCATOR, "parameter": "P",
                         "slots": {"img_meas2": "../../etc/passwd"}}]},
    )
    assert response.status_code == 400


def test_param_detail_rejects_a_non_ipv4_eqp_ip(client):
    bad = {**LOCATOR, "eqp_ip": "evil.example.com"}
    response = client.post(
        "/api/cdsem/recipe-search/param-detail",
        json={"items": [{"locator": bad, "parameter": "P", "slots": {}}]},
    )
    assert response.status_code == 400


def test_param_detail_caps_the_item_list(client):
    items = [{"locator": LOCATOR, "parameter": f"P{i}", "slots": {}}
             for i in range(201)]
    response = client.post("/api/cdsem/recipe-search/param-detail",
                           json={"items": items})
    assert response.status_code == 400


def test_align_detail_returns_sorted_points(client):
    response = client.get(
        "/api/cdsem/recipe-search/align-detail",
        query_string={**LOCATOR, "p_numbers": "3,1,2"},
    )
    assert response.status_code == 200
    assert [p["P_No"] for p in response.get_json()["points"]] == [1, 2, 3]


def test_recipe_image_serves_bytes_with_a_cache_header(client):
    response = client.get(
        "/api/cdsem/recipe-search/recipe-image",
        query_string={**LOCATOR, "name": "IMMP0001.jpeg"},
    )
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert response.headers["Cache-Control"] == "public, max-age=3600"
    assert response.data


def test_recipe_image_rejects_a_traversing_name(client):
    response = client.get(
        "/api/cdsem/recipe-search/recipe-image",
        query_string={**LOCATOR, "name": "../../../etc/passwd"},
    )
    assert response.status_code == 400
```

Add at the top of the file:

```python
LOCATOR = {"eqp_ip": "10.1.2.3", "class_name": "CLS", "idw": "IDW_A", "idp": "IDP_B"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search/tests/test_routes.py -q`

Expected: FAIL — 404 on every new path.

- [ ] **Step 3: Write minimal implementation**

In `data.py`, three functions following the existing `_provider()` pattern exactly:

```python
def get_param_detail(items: list[ParamDetailRequestItem]) -> list[ParamDetailResponse]:
    return _provider().get_param_detail(items)


def get_align_detail(locator: IdpLocator, p_numbers: list[int]) -> AlignDetailResponse:
    return _provider().get_align_detail(locator, p_numbers)


def fetch_recipe_image(locator: IdpLocator, name: str) -> tuple[bytes, str]:
    return _provider().fetch_recipe_image(locator, name)
```

In `routes.py`:

```python
# Compare fans out across recipes, so the body is a list. As N separate GETs
# this would trip the 20 req / 5 s per-user limit on /api/* the moment a user
# compared more than a handful of recipes.
_MAX_PARAM_ITEMS = 200


def _validated_locator(raw: object) -> IdpLocator:
    """Guard the four client-supplied FTP path fields. Raises InvalidLocator /
    InvalidToolIp — the backend opens an FTP session to whatever this names."""
    if not isinstance(raw, dict):
        raise InvalidLocator("locator must be an object")
    locator = {key: str(raw.get(key) or "").strip()
               for key in ("eqp_ip", "class_name", "idw", "idp")}
    validate_tool_ip(locator["eqp_ip"], load_config().allowed_subnets)
    for key in ("class_name", "idw", "idp"):
        validate_segment(locator[key], key)
    return locator


@bp.post("/<tool_slug>/recipe-search/param-detail")
def recipe_search_param_detail(tool_slug: str):
    if not _resolve_tool_type(tool_slug):
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    payload = request.get_json(silent=True) or {}
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        return jsonify({"error": "items must be a non-empty list"}), 400
    if len(items) > _MAX_PARAM_ITEMS:
        return jsonify({"error": f"items exceeds the {_MAX_PARAM_ITEMS} limit"}), 400

    clean: list[ParamDetailRequestItem] = []
    try:
        for item in items:
            slots = {key: str(value or "").strip()
                     for key, value in (item.get("slots") or {}).items()}
            for key, value in slots.items():
                # "non" is a legitimate value and passes validate_segment; only
                # separators and control characters are rejected here.
                if value:
                    validate_segment(value, key)
            clean.append({
                "locator": _validated_locator(item.get("locator")),
                "parameter": str(item.get("parameter") or "").strip(),
                "slots": slots,
            })
    except (InvalidLocator, InvalidToolIp) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify(get_param_detail(clean))


@bp.get("/<tool_slug>/recipe-search/align-detail")
def recipe_search_align_detail(tool_slug: str):
    if not _resolve_tool_type(tool_slug):
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400
    try:
        locator = _validated_locator(request.args.to_dict())
    except (InvalidLocator, InvalidToolIp) as exc:
        return jsonify({"error": str(exc)}), 400

    raw = (request.args.get("p_numbers") or "").strip()
    try:
        p_numbers = [int(part) for part in raw.split(",") if part.strip()]
    except ValueError:
        return jsonify({"error": "p_numbers must be comma-separated integers"}), 400

    return jsonify(get_align_detail(locator, p_numbers))


@bp.get("/<tool_slug>/recipe-search/recipe-image")
def recipe_search_recipe_image(tool_slug: str):
    if not _resolve_tool_type(tool_slug):
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400
    name = (request.args.get("name") or "").strip()
    try:
        locator = _validated_locator(request.args.to_dict())
        validate_segment(name, "name")
    except (InvalidLocator, InvalidToolIp) as exc:
        return jsonify({"error": str(exc)}), 400

    try:
        payload, content_type = fetch_recipe_image(locator, name)
    except LookupError:
        # A missing image is a real 404 so <img> falls back to its own broken
        # state instead of decoding a JSON error body as a picture.
        return jsonify({"error": f"image not found: {name}"}), 404

    return Response(payload, mimetype=content_type,
                    headers={"Cache-Control": "public, max-age=3600"})
```

Import `Response` from flask, `load_config` from `back_dev_home.msr_image.config`,
`validate_segment`/`validate_tool_ip` from `back_dev_home.msr_image.paths`, and
`InvalidLocator`/`InvalidToolIp` from `back_dev_home.msr_image.errors`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/recipe_search/data.py \
        back_dev_home/ebeam/hitachi/recipe_search/routes.py \
        back_dev_home/ebeam/hitachi/recipe_search/tests/test_routes.py
git commit -m "feat(recipe-search): add param-detail, align-detail and recipe-image routes"
```

---

### Task 6: Office adapter

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py`
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_raw_normalise.py`

**Interfaces:**

- Consumes: `rawfiles.*`, `_IdpLocation`, `_transport()`, `_locate_idp()` (all existing).
- Produces: `_to_rows(obj) -> list[SettingRow]`, `_fetch_raw(locator, names) ->
  dict[str, bytes]`, and the same three public functions the mock exposes.

- [ ] **Step 1: Write the failing test**

Only the pure normaliser is testable at home — that is deliberate, and it is the piece
most likely to break, because the reader's return container is OFFICE-VERIFY:

```python
"""_to_rows must survive whatever container the office reader returns."""

import pandas as pd

from back_dev_home.ebeam.hitachi.recipe_search.providers import office_example as office


def test_a_dict_becomes_rows_in_insertion_order():
    assert office._to_rows({"B": 2, "A": "x"}) == [
        {"key": "B", "value": "2"}, {"key": "A", "value": "x"},
    ]


def test_a_single_row_dataframe_becomes_column_rows():
    frame = pd.DataFrame([{"Mag": "50.0K", "Vacc": 800}])
    assert office._to_rows(frame) == [
        {"key": "Mag", "value": "50.0K"}, {"key": "Vacc", "value": "800"},
    ]


def test_a_two_column_dataframe_is_read_as_key_value_pairs():
    frame = pd.DataFrame({"item": ["Mag", "Vacc"], "value": ["50.0K", 800]})
    assert office._to_rows(frame) == [
        {"key": "Mag", "value": "50.0K"}, {"key": "Vacc", "value": "800"},
    ]


def test_a_list_of_pairs_becomes_rows():
    assert office._to_rows([("Mag", "50.0K")]) == [
        {"key": "Mag", "value": "50.0K"},
    ]


def test_none_and_empty_become_no_rows():
    assert office._to_rows(None) == []
    assert office._to_rows({}) == []
    assert office._to_rows(pd.DataFrame()) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search/tests/test_raw_normalise.py -q`

Expected: FAIL — `AttributeError: ... has no attribute '_to_rows'`.

- [ ] **Step 3: Write minimal implementation**

```python
def _to_rows(obj: Any) -> list[SettingRow]:
    """Whatever a reader returned -> ordered key/value rows.

    The readers' return CONTAINER is OFFICE-VERIFY, not just their field names:
    they may hand back a dict, a one-row DataFrame (columns are fields), a
    two-column DataFrame (rows are pairs), or a list of pairs. Handling all four
    here means a wrong guess degrades to rows in a slightly odd order rather
    than a 500 on a screen that used to work.
    """
    if obj is None:
        return []
    if isinstance(obj, pd.DataFrame):
        if obj.empty:
            return []
        if obj.shape[1] == 2:
            keys, values = obj.columns[0], obj.columns[1]
            return [{"key": str(r[keys]), "value": str(r[values])}
                    for _, r in obj.iterrows()]
        first = obj.iloc[0]
        return [{"key": str(c), "value": str(first[c])} for c in obj.columns]
    if isinstance(obj, dict):
        return [{"key": str(k), "value": str(v)} for k, v in obj.items()]
    if isinstance(obj, (list, tuple)):
        return [{"key": str(pair[0]), "value": str(pair[1])}
                for pair in obj if len(pair) >= 2]
    return []


def _fetch_raw(locator: IdpLocator, names: list[str]) -> dict[str, bytes]:
    """One batched FTP session for every raw file a call needs.

    A missing file is NOT an error — parameters legitimately lack an addressing
    image or an AF/PR setting. Failures are logged and simply absent from the
    returned mapping; only the session failing raises.
    """
    from back_dev_home.msr_image.config import load_config
    from back_dev_home.msr_image.paths import validate_tool_ip

    if not names:
        return {}
    config = load_config()
    validate_tool_ip(locator["eqp_ip"], config.allowed_subnets)
    downloader_cls, host_spec_cls, transport = _transport()
    downloader = downloader_cls(
        user=config.ftp_user,
        password=config.ftp_password,
        port=config.ftp_port,
        connect_timeout=config.ftp_timeout,
    )
    report = downloader.download(
        [host_spec_cls(locator["eqp_ip"], files=sorted(set(names)))]
    )
    for failure in report.failures:
        _LOG.info(
            "recipe_search: %s absent on %s (%s) — rendered as 파일 없음",
            failure.remote_path, locator["eqp_ip"], failure.error,
        )
    return {result.remote_path: result.data for result in report.files}
```

Plus the reader guard, which is what keeps one malformed file off the whole screen:

```python
def _read_block(source_name: str | None, payload: bytes | None, reader) -> SettingBlock | None:
    """Parse one raw file into a block. None when absent OR unparseable.

    A reader raising on a real file must not 500 the parameter — the other
    three blocks are still good. The filename is logged so the bad file can be
    found without reproducing the click.
    """
    if source_name is None or payload is None:
        return None
    try:
        parsed = reader(payload)
    except Exception:
        _LOG.warning(
            "recipe_search: %s could not be parsed by %s — rendered as 파일 없음",
            source_name, getattr(reader, "__name__", reader), exc_info=True,
        )
        return None
    return {"source": source_name, "rows": _to_rows(parsed)}
```

Then `get_param_detail` / `get_align_detail` / `fetch_recipe_image`, each assembling
paths with `rawfiles`, calling `_fetch_raw` **once** per call, and mapping the returned
bytes through `_read_block`. `fetch_recipe_image` raises `LookupError` when the image is
absent (the route turns that into a 404) and returns `"image/jpeg"` as the content type
for `.jpeg`/`.jpg` names.

Update the module docstring: remove the "`align_images` and `amp_info` — not among the
parser's three keys, so fabricated" bullet and describe the raw-folder source instead.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q`

Expected: PASS. Office-side verification happens later with
`SKEWNONO_RECIPE_SEARCH_PROVIDER=office`; it cannot run at home.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py \
        back_dev_home/ebeam/hitachi/recipe_search/tests/test_raw_normalise.py
git commit -m "feat(recipe-search): read AMP and conditions from the raw-recipe folder at the office"
```

---

### Task 7: Retire the fabricated `amp_info` and `align_images`

The breaking change, done only now that the replacement exists.

**Files:**

- Modify: `contracts.py`, `providers/mock.py`, `providers/office_example.py`, `data.py`
- Modify: `tests/test_contract.py`, `tests/test_idp_mapping.py`

**Interfaces:**

- Produces: `RecipeDetailResponse` gains `locator: IdpLocator` and loses `amp_info`
  and `align_images`; `CompareRecipe` gains `locator`; `CompareParameter` loses `amp`.

- [ ] **Step 1: Write the failing test**

```python
def test_detail_no_longer_carries_fabricated_amp_or_align_images():
    """Both were invented at the office too, not only at home. They are now
    sourced from the raw-recipe folder through param-detail / align-detail."""
    detail = data.get_recipe_open_data(recipe_id="R1", fac_id="R3",
                                       tool_category=TOOL_TYPE)
    assert "amp_info" not in detail
    assert "align_images" not in detail


def test_detail_carries_the_locator_follow_up_calls_need():
    detail = data.get_recipe_open_data(recipe_id="R1", fac_id="R3",
                                       tool_category=TOOL_TYPE)
    assert set(detail["locator"]) == {"eqp_ip", "class_name", "idw", "idp"}


def test_compare_recipes_carry_a_locator_and_no_amp():
    compare = data.get_recipe_compare_data(TOOL_TYPE, "R3", ["R1"])
    recipe = compare["recipes"][0]
    assert set(recipe["locator"]) == {"eqp_ip", "class_name", "idw", "idp"}
    assert "amp" not in recipe["parameters"][0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search/tests/test_contract.py -q`

Expected: FAIL — `amp_info` is still present, `locator` missing.

- [ ] **Step 3: Write minimal implementation**

- `contracts.py`: delete `AmpRow` and `AlignImageRow` and their `__all__` entries;
  remove `amp_info` / `align_images` from `RecipeDetailResponse` and add
  `locator: IdpLocator`; remove `amp` from `CompareParameter`; add `locator` to
  `CompareRecipe`.
- `mock.py`: delete `generate_amp_info`, `generate_wafer_align_images`,
  `_ADDR_ONLY_NONE`, `_MEAS_ONLY_NONE`; drop the `amp_by_param` block from
  `get_recipe_compare_data`; emit a deterministic fake locator
  (`{"eqp_ip": "10.0.0.1", "class_name": ..., "idw": ..., "idp": ...}` seeded off
  `recipe_id`) from both `get_recipe_open_data` and `get_recipe_compare_data`.
- `office_example.py`: **delete `_sourceless_extras()` entirely** — this is the
  deletion its own docstring asked for — and drop the
  `generate_amp_info` / `generate_wafer_align_images` imports. `_to_detail_response`
  takes the `_IdpLocation` and emits `locator`.

`IMAGE_SLOTS` **stays** — Task 4 reads `stage` from it.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest back_dev_home -q`

Expected: PASS across the whole backend (~1320 tests). A failure outside
`recipe_search` means something else read `amp_info`.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/recipe_search/contracts.py \
        back_dev_home/ebeam/hitachi/recipe_search/data.py \
        back_dev_home/ebeam/hitachi/recipe_search/providers/mock.py \
        back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py \
        back_dev_home/ebeam/hitachi/recipe_search/tests/test_contract.py \
        back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_mapping.py
git commit -m "refactor(recipe-search): retire fabricated amp_info and align_images"
```

---

### Task 8: Frontend types and the param-detail composable

**Files:**

- Modify: `front-dev-home/app/composables/useRecipeSearchApi.ts`
- Create: `front-dev-home/app/composables/useRecipeParamDetail.ts`
- Create: `front-dev-home/app/composables/useRecipeParamDetail.test.ts`

**Interfaces:**

- Produces: `IdpLocator`, `SettingRow`, `SettingBlock`, `ParamImage`, `ParamDetail`
  types; `recipeImageUrl(tool, locator, name) -> string`;
  `useRecipeParamDetail(tool, locator, recipeId, parameter, slots)`.

- [ ] **Step 1: Write the failing test**

`node --test` covers pure functions only (there is no mounting harness), so the URL
builder is what gets tested — and it is the piece a typo would break silently:

```ts
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { recipeImageUrl } from './useRecipeParamDetail'

const LOCATOR = { eqp_ip: '10.1.2.3', class_name: 'CLS', idw: 'IDW_A', idp: 'IDP_B' }

describe('recipeImageUrl', () => {
  it('targets the tool-scoped recipe-image endpoint', () => {
    const url = recipeImageUrl('cdsem', LOCATOR, 'IMMP0001.jpeg')
    assert.ok(url.startsWith('/api/cdsem/recipe-search/recipe-image?'))
  })

  it('carries every locator field plus the name', () => {
    const params = new URLSearchParams(
      recipeImageUrl('cdsem', LOCATOR, 'IMMP0001.jpeg').split('?')[1]
    )
    assert.equal(params.get('eqp_ip'), '10.1.2.3')
    assert.equal(params.get('class_name'), 'CLS')
    assert.equal(params.get('idw'), 'IDW_A')
    assert.equal(params.get('idp'), 'IDP_B')
    assert.equal(params.get('name'), 'IMMP0001.jpeg')
  })

  it('encodes a name that would otherwise break the query string', () => {
    const url = recipeImageUrl('cdsem', LOCATOR, 'A&B 0001.jpeg')
    assert.ok(!url.includes('A&B 0001'))
    const params = new URLSearchParams(url.split('?')[1])
    assert.equal(params.get('name'), 'A&B 0001.jpeg')
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `front-dev-home/`): `npm test`

Expected: FAIL — cannot resolve `./useRecipeParamDetail`.

- [ ] **Step 3: Write minimal implementation**

```ts
export interface IdpLocator {
  eqp_ip: string
  class_name: string
  idw: string
  idp: string
}

export interface SettingRow { key: string, value: string }
export interface SettingBlock { source: string, rows: SettingRow[] }
export interface ParamImage {
  slot: string
  stage: string
  name: string
  cond: SettingBlock | null
}
export interface ParamDetail {
  parameter: string
  amp: SettingBlock | null
  af_pr: SettingBlock | null
  images: ParamImage[]
}

/** URL for one raw-recipe image. Pure — a plain <img src>, so the browser's
 *  own cache absorbs repeat views and nothing is stored server-side. */
export function recipeImageUrl(
  tool: string,
  locator: IdpLocator,
  name: string
): string {
  const params = new URLSearchParams({ ...locator, name })
  return `/api/${tool}/recipe-search/recipe-image?${params.toString()}`
}

/** Settings for one parameter, fetched on click and cached per (recipe, parameter). */
export function useRecipeParamDetail(
  tool: string,
  locator: IdpLocator,
  recipeId: string,
  parameter: string,
  slots: Record<string, string>
) {
  return useAsyncData<ParamDetail>(
    `recipe-param-detail:${recipeId}:${parameter}`,
    async () => {
      const body = { items: [{ locator, parameter, slots }] }
      const rows = await $fetch<ParamDetail[]>(
        `/api/${tool}/recipe-search/param-detail`,
        { method: 'POST', body }
      )
      return rows[0]
    }
  )
}
```

In `useRecipeSearchApi.ts`: remove `align_images` and `amp_info` from the detail
interface, delete the `AmpRow`/`AlignImage` types, and add `locator: IdpLocator`.

- [ ] **Step 4: Run test to verify it passes**

Run (from `front-dev-home/`): `npm test && npm run typecheck`

Expected: tests PASS. `typecheck` will now flag the components Task 9 fixes — that is
the expected intermediate state, and Task 9 closes it.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/composables/useRecipeSearchApi.ts \
        front-dev-home/app/composables/useRecipeParamDetail.ts \
        front-dev-home/app/composables/useRecipeParamDetail.test.ts
git commit -m "feat(recipe-search): add the param-detail composable and image URL builder"
```

---

### Task 9: Rewire the recipe-open screen

**Files:**

- Modify: `front-dev-home/app/components/ebeam/recipeOpen/AmpBlock.vue`
- Modify: `front-dev-home/app/components/ebeam/recipeOpen/ImgThumb.vue`
- Modify: `front-dev-home/app/components/ebeam/recipeOpen/ImageLightbox.vue`
- Modify: `front-dev-home/app/components/ebeam/recipeOpen/AlignPopup.vue`
- Modify: `front-dev-home/app/components/ebeam/RecipeOpenView.vue` (`:220-230`, `:153`)

**Interfaces:**

- Consumes: `useRecipeParamDetail`, `recipeImageUrl`, `SettingBlock`, `ParamImage`
  (Task 8).

- [ ] **Step 1: Write the failing check**

There is no component-test harness, so the gate is the type checker plus a browser
pass. Run first to capture the starting error list:

Run (from `front-dev-home/`): `npm run typecheck`

Expected: errors in all five components — `Property 'amp_info' does not exist`,
`Property 'align_images' does not exist`.

- [ ] **Step 2: Confirm the failure is the expected one**

Every reported error must name `amp_info`, `align_images`, or `AmpRow`. An error
naming anything else means Task 8 changed something it should not have.

- [ ] **Step 3: Write the implementation**

- **`AmpBlock.vue`** — takes `block: SettingBlock | null` instead of `ampRows:
  AmpRow[]`. Renders `block.rows` as a two-column key/value table with `block.source`
  as the caption, and `파일 없음` when `block` is null. Delete the sixteen hardcoded
  column headers. Colours from `--sk-*` tokens only.
- **`ImgThumb.vue` / `ImageLightbox.vue`** — `src` becomes
  `recipeImageUrl(tool, locator, image.name)`; show the image's `cond` block beside
  the lightbox view.
- **`AlignPopup.vue`** — on open, `$fetch` `align-detail` with the locator and the
  sorted unique `P.No` values from `wafer_align_info`; render each point's image via
  `recipeImageUrl` with its `cond` and `setting` blocks.
- **`RecipeOpenView.vue`** — delete `ampInfo` / `ampRowsForSelected` (`:221`), call
  `useRecipeParamDetail` for the selected parameter instead, and pass
  `data.locator` down. Remove `:images="data.align_images"` (`:153`).

- [ ] **Step 4: Verify**

Run (from `front-dev-home/`): `npm run typecheck && npm run lint && npm test`

Expected: all clean. Then a browser pass via the `verify` skill: open a recipe, click a
parameter, confirm the settings table and thumbnails populate, open the align popup,
and confirm a parameter with a `"non"` slot renders `파일 없음` rather than a broken
image.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/recipeOpen/AmpBlock.vue \
        front-dev-home/app/components/ebeam/recipeOpen/ImgThumb.vue \
        front-dev-home/app/components/ebeam/recipeOpen/ImageLightbox.vue \
        front-dev-home/app/components/ebeam/recipeOpen/AlignPopup.vue \
        front-dev-home/app/components/ebeam/RecipeOpenView.vue
git commit -m "feat(recipe-search): render real AMP and conditions on the recipe-open screen"
```

---

### Task 10: Compare fetches the visible cell lazily

**Files:**

- Modify: `front-dev-home/app/components/ebeam/recipeCompare/CompareMatrix.vue` (`:120-135`)
- Modify: `front-dev-home/app/composables/useRecipeCompareApi.ts`

**Interfaces:**

- Consumes: `POST …/param-detail` with **one item per recipe** (Task 5), `SettingBlock`
  (Task 8).

- [ ] **Step 1: Write the failing check**

Run (from `front-dev-home/`): `npm run typecheck`

Expected: FAIL in `CompareMatrix.vue` — `Property 'amp' does not exist on type
'CompareParameter'`.

- [ ] **Step 2: Confirm the failure is the expected one**

The only errors should name `amp` on `CompareParameter`.

- [ ] **Step 3: Write the implementation**

Replace `buildAmpRows(props.recipes, props.parameter, props.slotKey)` with a watcher on
`(props.parameter, props.slotKey)` that issues **one** POST carrying an item per
recipe:

```ts
const body = {
  items: props.recipes.map(recipe => ({
    locator: recipe.locator,
    parameter: props.parameter,
    slots: recipe.parameters.find(p => p.Parameter === props.parameter)?.images ?? {}
  }))
}
const details = await $fetch<ParamDetail[]>(
  `/api/${tool}/recipe-search/param-detail`, { method: 'POST', body }
)
```

Diff on the **union of keys** across the returned blocks, preserving first-seen order,
so a field only one recipe carries still shows a row (marked differing). Keep the
existing `diffOnly` filter behaviour.

One POST, not N — the `/api/*` limit is 20 requests / 5 s per user, and a 20-recipe
comparison would trip it instantly as separate GETs.

- [ ] **Step 4: Verify**

Run (from `front-dev-home/`): `npm run typecheck && npm run lint && npm test`

Then a browser pass: compare 2+ recipes, switch parameter and slot, confirm the AMP
diff repopulates and that `diffOnly` still filters.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/components/ebeam/recipeCompare/CompareMatrix.vue \
        front-dev-home/app/composables/useRecipeCompareApi.ts
git commit -m "feat(recipe-search): fetch compare AMP lazily for the visible cell"
```

---

### Task 11: Documentation

Per CLAUDE.md, office knowledge lands in **two** places — `docs/datatables/` and the
feature's `mock.py`. Task 3 did the mock half; this does the schema-of-record half.

**Files:**

- Modify: `docs/datatables/recipe_idp.txt`
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/MIGRATION.md`

- [ ] **Step 1: Add the raw-recipe-folder section to `recipe_idp.txt`**

A new section covering: the folder path `data/{idw}/{idp}/`; the full naming table from
the spec; the `.`-prefixed hidden `cond.txt` sidecar (cross-referencing
`msr_image`, `office 확인 2026-07-24`); `"non"` as the French empty sentinel — noting
explicitly that `"none"` is **not** a sentinel; four-digit zero padding; extensionless
`EN…`/`PR…` files; `PR`→`EN` for `img_add2` and as-is for `img_meas2`; and that
`img_add2`/`img_meas2` yield no image while `image_add3` does.

Mark every fact `user-confirmed 2026-07-29`. Mark the readers' field names
`OFFICE-VERIFY`. Written in Korean, matching the file's existing style.

- [ ] **Step 2: Add the office-adapter obligations to `MIGRATION.md`**

Document the three new functions the office adapter owes, the `office_utils.idp_amp_reader`
dependency, that missing files are normal and must not raise, and that
`fetch_recipe_image` must raise `LookupError` for a missing image so the route can 404.

- [ ] **Step 3: Lint**

Run (from the repo root): `npm run lint:md`

Expected: `0 error(s)`. `.txt` files are not linted; `MIGRATION.md` is.

- [ ] **Step 4: Full suite**

```bash
.venv/bin/python -m pytest -q
cd front-dev-home && npm test && npm run typecheck && npm run lint
```

Expected: all green.

- [ ] **Step 5: Commit, merge, and tear the worktree down**

```bash
git add docs/datatables/recipe_idp.txt \
        back_dev_home/ebeam/hitachi/recipe_search/MIGRATION.md
git commit -m "docs(recipe-search): record the raw-recipe folder naming convention"

git -C <main-tree> merge --ff-only work/raw-recipe-folder
git -C <main-tree> push
git -C <main-tree> worktree remove ../skewnono-rawrecipe
git -C <main-tree> branch -d work/raw-recipe-folder
git -C <main-tree> worktree list   # must show the main tree alone
```

---

## Office follow-up (cannot be done at home)

Not tasks — these need an office PC, and the plan is complete without them:

1. Run `SKEWNONO_RECIPE_SEARCH_PROVIDER=office .venv/bin/python -m pytest
   back_dev_home/ebeam/hitachi/recipe_search -q`.
2. Capture the readers' **real field names**, then update `mock.py`'s stand-in keys and
   `recipe_idp.txt`. The contract does not change — that is why it is open key/value.
3. Confirm `_to_rows` picked the right branch for the readers' actual return container.
4. Settle spec open items 2 and 3: whether `ENAP{p:04d}` exists for every `P.No`, and
   whether `PRMP…` holds anything useful.
