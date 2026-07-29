# Redis-first IDP Location Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Locate a recipe's `.idp` file from two new per-fab Redis registry hashes, falling back to the existing OpenSearch `meas_hist` lookup, and retry the FTP download down the tool list the registry provides.

**Architecture:** `_locate_idp` becomes a dispatcher over two strategies that both return an ordered `list[_IdpLocation]`. Redis is tried first and returns `None` (never an error) when it cannot answer; `meas_hist` is the fallback. A new `_download_first` loop walks the candidates so one unreachable tool no longer fails the request. Everything below the download — parse and map — is untouched.

**Tech Stack:** Python 3.14, Flask, `redis-py`, `opensearch-py` via `ops_store`, pandas, pytest.

**Spec:** `.scratch/recipe-idp-redis-locate/spec.md`

## Global Constraints

- **Work in the worktree** `/Users/daeyoung/Codes/skewnono-rcp-loc` on branch `work/rcp-loc`. Every path below is relative to that root.
- **Edit only** `back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py` and the new test file. Never touch `routes.py`, `data.py`, `contracts.py`, `tests/test_contract.py`, `tests/test_idp_mapping.py`, or `providers/mock.py` **behavior** (its docstring is edited in Task 6).
- **`providers/office.py` is gitignored.** Never edit, never `git add`, never commit it.
- **Run tests from the repo root as** `.venv/bin/python -m pytest ...`. The `-m` is what puts the root on `sys.path`.
- **Commit with explicit pathspecs only.** Form: `git commit -m "msg" -- path/a path/b`. The `-m` must come *before* `--`. `git add -A`, `git add .`, and `git commit -a` are banned — other agent sessions share this repo.
- **Commit message style:** `type(scope): summary` subject plus a body saying what changed and why.
- **Office facts are dated.** New facts from the user are marked `user-confirmed 2026-07-29`; anything still assumed is marked `OFFICE-VERIFY`.
- **Markdown tables use markdownlint `MD060` compact style** (`| --- |`). Run `npm run lint:md` from the repo root after any Markdown edit.
- **Do not add a `from __future__ import annotations`** — the module does not use one and does not need one.

## File Structure

| File | Responsibility | Task |
| --- | --- | --- |
| `back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py` | The whole change: helpers, both strategies, the retry loop | 1–5 |
| `back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py` | New. Home-runnable gate for every new pure function and the retry loop | 1–5 |
| `docs/datatables/recipe_name_list.txt` | Schema of record for the Redis recipe hashes | 6 |
| `docs/datatables/recipe_idp.txt` | Schema of record for the IDP source chain | 6 |
| `back_dev_home/ebeam/hitachi/recipe_search/providers/mock.py` | Docstring only — what the mock stands in for | 6 |
| `back_dev_home/ebeam/hitachi/recipe_search/MIGRATION.md` | Office adapter status and error table | 6 |

`office_example.py` grows by roughly 150 lines. That is acceptable here: the file's organizing principle is the four-step pipeline marked by its `# ── step ──` banners, and the new code slots into step 1 rather than adding a new concern.

---

### Task 1: Pure key and name helpers

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py`
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py` (create)

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces:
  - `_FAMILY: dict[ToolType, str]`
  - `_fab_hash(kind: str, tool_type: ToolType, fab_name: str) -> str`
  - `_class_name(recipe_id: str) -> str`
  - `_parse_str_list(value) -> list[str]` — renamed from `_parse_recipe_list`, same behavior

- [ ] **Step 1: Write the failing test**

Create `back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py`:

```python
"""Gate for the .idp LOCATION step of the office adapter (Redis + OpenSearch).

`test_idp_mapping.py` covers the step after the download; this file covers the
step before it. Same reason for existing: locate -> download are the two links
in the chain that home cannot reach, so every part of them that can be made a
pure function is, and gated here.

It imports `providers/office_example.py` — the tracked template — never
`providers/office.py`, which is gitignored and absent on a clean checkout.
Redis, OpenSearch, sem_list and FTP are all stubbed; nothing here does I/O.
"""

import pytest

from back_dev_home.ebeam.hitachi.recipe_search.providers import office_example as oe


class TestFabHash:
    def test_lowercases_the_fab_at_the_redis_boundary(self):
        assert oe._fab_hash("rcp_loc", "cd-sem", "R3") == "v3_cdsem_rcp_loc_r3"

    def test_strips_surrounding_whitespace(self):
        assert oe._fab_hash("tools_in_rcp", "hv-sem", " M14A ") == (
            "v3_hvsem_tools_in_rcp_m14a"
        )

    def test_unknown_tool_type_is_a_value_error(self):
        with pytest.raises(ValueError, match="Unknown tool_type"):
            oe._fab_hash("rcp_loc", "ebeam", "R3")


class TestClassName:
    def test_prefix_before_the_first_slash(self):
        assert oe._class_name("ADI/ADI_CD_BIAS_001") == "ADI"

    def test_numeric_class_is_a_class(self):
        # Real catalog names look like this (user-confirmed 2026-07-29).
        assert oe._class_name("1/AC_M2_TAT") == "1"

    def test_only_the_first_segment_is_the_class(self):
        assert oe._class_name("OVL/SUB/DEEP_001") == "OVL"

    def test_no_slash_yields_empty_rather_than_the_whole_name(self):
        # Returning the name itself would build /HD/AC_M2_TAT/data/... — a
        # plausible path that does not exist. Empty forces the caller to bail.
        assert oe._class_name("AC_M2_TAT") == ""


class TestParseStrList:
    def test_json_list(self):
        assert oe._parse_str_list('["/Recipe/A.idw", "/Recipe/A.idp"]') == [
            "/Recipe/A.idw", "/Recipe/A.idp",
        ]

    def test_python_repr_list(self):
        assert oe._parse_str_list("['CG6300_01', 'CG6380_02']") == [
            "CG6300_01", "CG6380_02",
        ]

    def test_bytes_are_decoded(self):
        assert oe._parse_str_list(b'["CG6300_01"]') == ["CG6300_01"]

    def test_blank_is_empty(self):
        assert oe._parse_str_list("") == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run from the repo root:

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py -q
```

Expected: FAIL — `AttributeError: module ... has no attribute '_fab_hash'`.

- [ ] **Step 3: Rename `_parse_recipe_list` to `_parse_str_list`**

In `office_example.py`, rename the function defined at the `# ── catalog (Redis) ──` banner and update its docstring first line and both call sites (`_recipes_for_fab`, `_all_recipes`):

```python
def _parse_str_list(value) -> list[str]:
    """A hash value -> list of strings, tolerant of JSON / repr / CSV.

    Shared by all three per-recipe hashes (the name catalog, the location
    registry, the tool registry) because they are written by the same kind of
    job: a Python list that lands in Redis as JSON (``["a", "b"]``) or as a
    ``repr`` (``['a', 'b']``) depending on the writer, and both parse here. The
    CSV fallback covers a plain comma-joined string — recipe names, paths and
    equipment ids carry ``/`` and ``_`` but no commas, so that split is safe as
    a last resort.
    """
```

The body is unchanged. Then update the two call sites:

```python
        return _unique(_parse_str_list(raw))
```

```python
        names.extend(_parse_str_list(value))
```

`_unique` is untouched: `RecipeSearchRow` is an alias for `str`, so its
`list[RecipeSearchRow]` parameter already accepts what `_parse_str_list`
returns. After the rename, `grep -n "_parse_recipe_list" office_example.py`
must return nothing.

- [ ] **Step 4: Add the two new helpers**

Insert immediately after `_RECIPE_HASH` (before the `# ── catalog (Redis) ──` banner):

```python
# The same two families, spelled the way the per-fab registry hashes spell
# them. _RECIPE_HASH above is a whole key because the catalog has one hash per
# family; the registry has one hash per family AND fab, so it is built instead.
_FAMILY: dict[ToolType, str] = {"cd-sem": "cdsem", "hv-sem": "hvsem"}
```

Then add both functions after `_stem` (inside the locate section, before `_locate_idp`):

```python
def _fab_hash(kind: str, tool_type: ToolType, fab_name: str) -> str:
    """Redis key for one fab's per-recipe registry hash.

    ``kind`` is ``"rcp_loc"`` (the ``[idw_name, idp_name]`` pair) or
    ``"tools_in_rcp"`` (the equipment list). The fab is lowercased HERE, at the
    Redis boundary, for the same reason the catalog does it: routes.py hands
    down an uppercase name and nothing above this module should have to know
    that the store disagrees.
    """
    family = _FAMILY.get(tool_type)
    if family is None:
        raise ValueError(
            f"Unknown tool_type {tool_type!r}; expected one of {sorted(_FAMILY)}"
        )
    return f"v3_{family}_{kind}_{fab_name.strip().lower()}"


def _class_name(recipe_id: str) -> str:
    """'ADI/ADI_CD_BIAS_001' -> 'ADI'. The FTP tree's class directory.

    ``full_name = f"{class_name}/{recipe_name}"``
    (docs/datatables/meas_hist.txt), so on the Redis path the class is the
    prefix of the key just looked up — neither registry hash carries it
    separately, and meas_hist is not queried to get it.

    A name with no ``/`` yields ``""`` rather than the name itself: using the
    whole name would assemble a plausible path to a directory that does not
    exist, and a blank forces the caller to fall back instead.
    """
    return recipe_id.split("/", 1)[0].strip() if "/" in recipe_id else ""
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q
```

Expected: PASS, including the pre-existing `test_contract.py` and `test_idp_mapping.py` (the rename must not have broken the catalog path).

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(recipe-search): add registry key and class-name helpers

Adds _fab_hash (per-fab Redis registry key, lowercased at the boundary) and
_class_name (the FTP class directory, derived from the full_name prefix since
neither new hash carries it). Renames _parse_recipe_list to _parse_str_list:
it now serves all three per-recipe hashes, not just the name catalog.
" -- back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py \
     back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py
```

---

### Task 2: Roster resolution and candidate ordering

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py`
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py`

**Interfaces:**

- Consumes: nothing from Task 1.
- Produces:
  - `_eqp_ip_index() -> dict[str, tuple[str, str]]` — `eqp_id -> (eqp_ip, available)`, `ttl_cache`d. Has `.cache_clear()`.
  - `_order_candidates(eqp_ids: list[str], index: dict[str, tuple[str, str]]) -> list[tuple[str, str]]` — pure, returns `[(eqp_id, eqp_ip), ...]` best-first.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_idp_locate.py`:

```python
ROSTER = {
    "CG6300_01": ("10.1.2.1", "On"),
    "CG6300_07": ("10.1.2.7", "On"),
    "CG6380_02": ("10.1.2.2", "Off"),
}


class TestOrderCandidates:
    def test_available_tools_come_first(self):
        assert oe._order_candidates(["CG6380_02", "CG6300_01"], ROSTER) == [
            ("CG6300_01", "10.1.2.1"),
            ("CG6380_02", "10.1.2.2"),
        ]

    def test_registry_order_is_preserved_within_a_group(self):
        # The registry carries no ranking, so a stable order keeps the same
        # recipe hitting the same tool run after run.
        assert oe._order_candidates(["CG6300_07", "CG6300_01"], ROSTER) == [
            ("CG6300_07", "10.1.2.7"),
            ("CG6300_01", "10.1.2.1"),
        ]

    def test_tools_absent_from_the_roster_are_dropped(self):
        assert oe._order_candidates(["GONE_99", "CG6300_01"], ROSTER) == [
            ("CG6300_01", "10.1.2.1"),
        ]

    def test_all_unknown_yields_nothing(self):
        assert oe._order_candidates(["GONE_99"], ROSTER) == []

    def test_whitespace_around_an_id_still_resolves(self):
        assert oe._order_candidates([" CG6300_01 "], ROSTER) == [
            ("CG6300_01", "10.1.2.1"),
        ]


class TestEqpIpIndex:
    def test_builds_the_index_from_the_sem_list_roster(self, monkeypatch):
        monkeypatch.setattr(oe, "get_sem_list", lambda: [
            {"eqp_id": "CG6300_01", "eqp_ip": "10.1.2.1", "available": "On"},
            {"eqp_id": "CG6380_02", "eqp_ip": "10.1.2.2", "available": "Off"},
        ])
        oe._eqp_ip_index.cache_clear()
        assert oe._eqp_ip_index() == {
            "CG6300_01": ("10.1.2.1", "On"),
            "CG6380_02": ("10.1.2.2", "Off"),
        }
        oe._eqp_ip_index.cache_clear()

    def test_rows_without_an_ip_are_skipped(self, monkeypatch):
        # A fleet row with no IP cannot be dialed; keeping it would produce a
        # candidate that always fails the SSRF guard.
        monkeypatch.setattr(oe, "get_sem_list", lambda: [
            {"eqp_id": "CG6300_01", "eqp_ip": "", "available": "On"},
        ])
        oe._eqp_ip_index.cache_clear()
        assert oe._eqp_ip_index() == {}
        oe._eqp_ip_index.cache_clear()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py -q
```

Expected: FAIL — `AttributeError: module ... has no attribute '_order_candidates'`.

- [ ] **Step 3: Add the imports**

In `office_example.py`, extend the existing `_office_search` import and add the `sem_list` one:

```python
from back_dev_home.ebeam.hitachi._office_search import fetch_hits, query, ttl_cache
```

and, after the `recipe_search.contracts` import block:

```python
from back_dev_home.sem_list.data import get_sem_list
```

- [ ] **Step 4: Add both functions**

Insert after `_class_name` (still in the locate section):

```python
@ttl_cache
def _eqp_ip_index() -> dict[str, tuple[str, str]]:
    """``eqp_id -> (eqp_ip, available)`` for the whole fleet.

    The registry names tools by ``eqp_id`` but FTP dials an IP, so the roster
    resolves the gap — the same ``eqp_id -> eqp_ip`` join lateral check makes,
    and through the same source, so the two screens cannot disagree about
    which tools exist.

    Cached because ``get_sem_list()`` deserializes two parquet blobs from Redis
    and merges them: reasonable once per TTL, wasteful once per recipe open.
    What that costs is an IP change taking up to 15 minutes to be seen, which
    is the right trade for a roster that only moves when tools do.
    """
    index: dict[str, tuple[str, str]] = {}
    for row in get_sem_list():
        eqp_id = str(row.get("eqp_id") or "").strip()
        eqp_ip = str(row.get("eqp_ip") or "").strip()
        if eqp_id and eqp_ip:
            index[eqp_id] = (eqp_ip, str(row.get("available") or ""))
    return index


def _order_candidates(
    eqp_ids: list[str],
    index: dict[str, tuple[str, str]],
) -> list[tuple[str, str]]:
    """``[eqp_id, ...]`` -> ``[(eqp_id, eqp_ip), ...]``, best host first. Pure.

    Tools the roster reports available sort ahead of the rest; within each
    group the registry's own order is preserved, since it carries no ranking
    and a stable order keeps the same recipe hitting the same tool. Offline
    tools are kept rather than dropped — ``available`` describes whether the
    tool is running production, not whether its FTP server answers, and the
    .idp is worth trying for once the online tools have failed.

    An ``eqp_id`` the roster does not know is dropped: the registry says the
    recipe is there, but with no IP there is nothing to dial.
    """
    online: list[tuple[str, str]] = []
    offline: list[tuple[str, str]] = []
    unknown: list[str] = []
    for raw_id in eqp_ids:
        eqp_id = raw_id.strip()
        resolved = index.get(eqp_id)
        if resolved is None:
            unknown.append(eqp_id)
            continue
        eqp_ip, available = resolved
        (online if available == "On" else offline).append((eqp_id, eqp_ip))
    if unknown:
        _LOG.warning(
            "recipe_search: %d tool(s) named by the recipe registry are not in "
            "the sem_list roster and were skipped: %s. The two sources use the "
            "same eqp_id spelling (user-confirmed 2026-07-29), so this means "
            "the roster is missing the tool, not that the ids disagree.",
            len(unknown), unknown,
        )
    return online + offline
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(recipe-search): resolve registry eqp_id to eqp_ip via sem_list

The tools_in_rcp registry names tools by eqp_id but the FTP fetch dials an IP.
_eqp_ip_index builds the eqp_id -> (eqp_ip, available) map from the sem_list
roster (the same source lateral check uses, so tool inventory cannot disagree
between screens), TTL-cached because the roster read deserializes two parquet
blobs. _order_candidates sorts available tools first, keeps registry order
within each group, and drops ids the roster does not know.
" -- back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py \
     back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py
```

---

### Task 3: The Redis locate strategy

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py`
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py`

**Interfaces:**

- Consumes: `_fab_hash`, `_class_name`, `_parse_str_list` (Task 1); `_eqp_ip_index`, `_order_candidates` (Task 2); `_IdpLocation`, `_stem` (existing).
- Produces: `_locate_via_redis(tool_type: ToolType, recipe_id: str, fab_name: str | None) -> list[_IdpLocation] | None`. `None` means "fall back", never an error. A returned list is always non-empty.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_idp_locate.py`:

```python
class _FakeRedis:
    """Minimal `hget` stand-in. `store` is {key: {field: value}}."""

    def __init__(self, store):
        self.store = store

    def hget(self, key, field):
        return self.store.get(key, {}).get(field)


LOC_KEY = "v3_cdsem_rcp_loc_r3"
TOOLS_KEY = "v3_cdsem_tools_in_rcp_r3"
RECIPE = "ADI/ADI_CD_BIAS_001"


@pytest.fixture
def wired(monkeypatch):
    """Both hashes populated and the roster resolvable — the happy path."""
    def _wire(store):
        monkeypatch.setattr(oe, "_redis_client", lambda: _FakeRedis(store))
        monkeypatch.setattr(oe, "_eqp_ip_index", lambda: ROSTER)
    return _wire


class TestLocateViaRedis:
    def test_builds_candidates_from_both_hashes(self, wired):
        wired({
            LOC_KEY: {RECIPE: '["/Recipe/ADI/ADI_CD_BIAS_001.idw",'
                              ' "/Recipe/ADI/ADI_CD_BIAS_001.idp"]'},
            TOOLS_KEY: {RECIPE: '["CG6380_02", "CG6300_01"]'},
        })
        locations = oe._locate_via_redis("cd-sem", RECIPE, "R3")
        assert locations == [
            oe._IdpLocation("CG6300_01", "10.1.2.1", "ADI",
                            "ADI_CD_BIAS_001", "ADI_CD_BIAS_001"),
            oe._IdpLocation("CG6380_02", "10.1.2.2", "ADI",
                            "ADI_CD_BIAS_001", "ADI_CD_BIAS_001"),
        ]

    def test_paths_are_reduced_to_stems(self, wired):
        # The registry stores paths; the FTP tree wants bare names.
        wired({
            LOC_KEY: {RECIPE: '["/Recipe/ADI/A.idw", "/Recipe/ADI/B.idp"]'},
            TOOLS_KEY: {RECIPE: '["CG6300_01"]'},
        })
        location = oe._locate_via_redis("cd-sem", RECIPE, "R3")[0]
        assert (location.idw_stem, location.idp_stem) == ("A", "B")

    def test_blank_fab_falls_back(self, wired):
        wired({})
        assert oe._locate_via_redis("cd-sem", RECIPE, None) is None

    def test_recipe_without_a_class_prefix_falls_back(self, wired):
        wired({
            LOC_KEY: {"AC_M2_TAT": '["/R/A.idw", "/R/A.idp"]'},
            TOOLS_KEY: {"AC_M2_TAT": '["CG6300_01"]'},
        })
        assert oe._locate_via_redis("cd-sem", "AC_M2_TAT", "R3") is None

    def test_missing_location_field_falls_back(self, wired):
        wired({TOOLS_KEY: {RECIPE: '["CG6300_01"]'}})
        assert oe._locate_via_redis("cd-sem", RECIPE, "R3") is None

    def test_one_sided_location_value_falls_back(self, wired):
        # Read positionally, so a 1-entry list is unusable rather than partial.
        wired({
            LOC_KEY: {RECIPE: '["/Recipe/ADI/A.idw"]'},
            TOOLS_KEY: {RECIPE: '["CG6300_01"]'},
        })
        assert oe._locate_via_redis("cd-sem", RECIPE, "R3") is None

    def test_missing_tool_field_falls_back(self, wired):
        wired({LOC_KEY: {RECIPE: '["/R/A.idw", "/R/A.idp"]'}})
        assert oe._locate_via_redis("cd-sem", RECIPE, "R3") is None

    def test_no_tool_resolves_falls_back(self, wired):
        wired({
            LOC_KEY: {RECIPE: '["/R/A.idw", "/R/A.idp"]'},
            TOOLS_KEY: {RECIPE: '["GONE_99"]'},
        })
        assert oe._locate_via_redis("cd-sem", RECIPE, "R3") is None

    def test_uppercase_fab_reaches_the_lowercase_key(self, wired):
        wired({
            LOC_KEY: {RECIPE: '["/R/A.idw", "/R/A.idp"]'},
            TOOLS_KEY: {RECIPE: '["CG6300_01"]'},
        })
        assert oe._locate_via_redis("cd-sem", RECIPE, "R3") is not None
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py -q
```

Expected: FAIL — `AttributeError: module ... has no attribute '_locate_via_redis'`.

- [ ] **Step 3: Implement `_locate_via_redis`**

Insert immediately before the existing `_locate_idp` definition:

```python
def _locate_via_redis(
    tool_type: ToolType,
    recipe_id: str,
    fab_name: str | None,
) -> list[_IdpLocation] | None:
    """Candidate locations from the two per-fab registry hashes, or ``None``.

    ``None`` means "ask meas_hist" and is never an error: the registry is a
    newer source and is not promised to cover every fab or every recipe. It is
    all-or-nothing on purpose — a location assembled half from the registry and
    half from measurement history would be untraceable the day the path it
    produces turns out to be wrong.

    Every bail logs which step produced it, because from outside the office a
    silent fallback and a broken lookup look identical.
    """
    if not fab_name:
        _LOG.info(
            "recipe_search: no fab_name for %r, so no registry key can be "
            "built — falling back to meas_hist.", recipe_id,
        )
        return None

    class_name = _class_name(recipe_id)
    if not class_name:
        _LOG.info(
            "recipe_search: %r has no class prefix, so the registry cannot "
            "supply the FTP class directory — falling back to meas_hist.",
            recipe_id,
        )
        return None

    client = _redis_client()

    loc_key = _fab_hash("rcp_loc", tool_type, fab_name)
    parts = _parse_str_list(client.hget(loc_key, recipe_id) or "")
    if len(parts) < 2:
        _LOG.info(
            "recipe_search: %s has no usable [idw, idp] entry for %r (got %s) "
            "— falling back to meas_hist.", loc_key, recipe_id, parts,
        )
        return None

    tools_key = _fab_hash("tools_in_rcp", tool_type, fab_name)
    eqp_ids = _parse_str_list(client.hget(tools_key, recipe_id) or "")
    if not eqp_ids:
        _LOG.info(
            "recipe_search: %s names no tool for %r — falling back to "
            "meas_hist.", tools_key, recipe_id,
        )
        return None

    idw_stem, idp_stem = _stem(parts[0]), _stem(parts[1])
    if not idw_stem or not idp_stem:
        _LOG.info(
            "recipe_search: %s entry for %r has an empty path component (%s) "
            "— falling back to meas_hist.", loc_key, recipe_id, parts[:2],
        )
        return None

    candidates = _order_candidates(eqp_ids, _eqp_ip_index())
    if not candidates:
        _LOG.info(
            "recipe_search: none of %s resolves to an IP for %r — falling back "
            "to meas_hist.", eqp_ids, recipe_id,
        )
        return None

    _LOG.info(
        "recipe_search: located %r via the Redis registry — %d tool "
        "candidate(s), no OpenSearch query.", recipe_id, len(candidates),
    )
    return [
        _IdpLocation(
            eqp_id=eqp_id,
            eqp_ip=eqp_ip,
            class_name=class_name,
            idw_stem=idw_stem,
            idp_stem=idp_stem,
        )
        for eqp_id, eqp_ip in candidates
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git commit -m "feat(recipe-search): locate the .idp from the Redis registry

_locate_via_redis reads v3_{family}_rcp_loc_{fab} for the [idw, idp] pair and
v3_{family}_tools_in_rcp_{fab} for the tool list, then resolves and orders the
tools into candidate locations. Returns None rather than raising when it cannot
answer — the registry is newer than meas_hist and need not cover every fab, so
a miss is a fallback, not a fault. Every bail logs which step produced it.
" -- back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py \
     back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py
```

---

### Task 4: The meas_hist strategy returns candidates, and the dispatcher

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py` (the existing `_locate_idp`, currently at the `# ── recipe open, step 1 ──` banner)
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py`

**Interfaces:**

- Consumes: `_locate_via_redis` (Task 3).
- Produces:
  - `_locate_via_meas_hist(tool_type: ToolType, recipe_id: str, fab_name: str | None) -> list[_IdpLocation]` — renamed from `_locate_idp`, now returns every complete hit newest-first instead of only the first.
  - `_locate_idp(tool_type: ToolType, recipe_id: str, fab_name: str | None) -> list[_IdpLocation]` — the dispatcher.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_idp_locate.py`:

```python
def _hit(eqp_id, ts, **overrides):
    hit = {
        "eqp_id": eqp_id,
        "eqp_ip": f"10.9.9.{eqp_id[-1]}",
        "class_name": "ADI",
        "idw_name": "/Recipe/ADI/ADI_CD_BIAS_001.idw",
        "idp_name": "/Recipe/ADI/ADI_CD_BIAS_001.idp",
        "timestamp": ts,
    }
    hit.update(overrides)
    return hit


class TestLocateViaMeasHist:
    def test_returns_every_complete_hit_newest_first(self, monkeypatch):
        monkeypatch.setattr(oe, "fetch_hits", lambda *a, **k: [
            _hit("CG6300_1", "2026-07-28T10:00:00"),
            _hit("CG6300_2", "2026-07-27T10:00:00"),
        ])
        locations = oe._locate_via_meas_hist("cd-sem", RECIPE, "R3")
        assert [location.eqp_id for location in locations] == [
            "CG6300_1", "CG6300_2",
        ]

    def test_incomplete_documents_are_skipped_not_fatal(self, monkeypatch):
        monkeypatch.setattr(oe, "fetch_hits", lambda *a, **k: [
            _hit("CG6300_1", "2026-07-28T10:00:00", eqp_ip=""),
            _hit("CG6300_2", "2026-07-27T10:00:00"),
        ])
        locations = oe._locate_via_meas_hist("cd-sem", RECIPE, "R3")
        assert [location.eqp_id for location in locations] == ["CG6300_2"]

    def test_no_document_is_a_lookup_error(self, monkeypatch):
        monkeypatch.setattr(oe, "fetch_hits", lambda *a, **k: [])
        with pytest.raises(LookupError, match="has never been measured"):
            oe._locate_via_meas_hist("cd-sem", RECIPE, "R3")

    def test_all_documents_incomplete_is_a_lookup_error(self, monkeypatch):
        monkeypatch.setattr(oe, "fetch_hits", lambda *a, **k: [
            _hit("CG6300_1", "2026-07-28T10:00:00", eqp_ip=""),
        ])
        with pytest.raises(LookupError, match="none carries every field"):
            oe._locate_via_meas_hist("cd-sem", RECIPE, "R3")


class TestLocateIdpDispatch:
    def test_redis_wins_and_opensearch_is_never_queried(self, monkeypatch):
        sentinel = [oe._IdpLocation("CG6300_01", "10.1.2.1", "ADI", "A", "A")]
        monkeypatch.setattr(oe, "_locate_via_redis", lambda *a: sentinel)
        monkeypatch.setattr(oe, "_locate_via_meas_hist", lambda *a: pytest.fail(
            "meas_hist must not be queried when the registry answered"
        ))
        assert oe._locate_idp("cd-sem", RECIPE, "R3") == sentinel

    def test_registry_miss_falls_through_to_meas_hist(self, monkeypatch):
        sentinel = [oe._IdpLocation("CG6300_02", "10.9.9.2", "ADI", "A", "A")]
        monkeypatch.setattr(oe, "_locate_via_redis", lambda *a: None)
        monkeypatch.setattr(oe, "_locate_via_meas_hist", lambda *a: sentinel)
        assert oe._locate_idp("cd-sem", RECIPE, "R3") == sentinel
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py -q
```

Expected: FAIL — `AttributeError: module ... has no attribute '_locate_via_meas_hist'`.

- [ ] **Step 3: Rename and rework the existing function**

Rename `_locate_idp` to `_locate_via_meas_hist`, change its return annotation and docstring, and replace the `for hit in hits:` block's early `return` with accumulation. The signature and the `fetch_hits` call are unchanged. The finished function:

```python
def _locate_via_meas_hist(
    tool_type: ToolType,
    recipe_id: str,
    fab_name: str | None,
) -> list[_IdpLocation]:
    """Candidate locations from measurement history, newest run first.

    The fallback for anything the Redis registry cannot answer, and still the
    only source for a fab the registry does not cover. Every complete document
    becomes a candidate rather than only the newest: if the tool that ran the
    recipe most recently is unreachable, the tool that ran it the time before
    holds the same file.

    Raises:
        LookupError: no measurement document names this recipe, or none of the
            candidates carries the four fields the FTP path is assembled from.
    """
    index = _MEAS_HIST_INDEX.get(tool_type)
    if index is None:
        raise ValueError(
            f"Unknown tool_type {tool_type!r}; expected one of {sorted(_MEAS_HIST_INDEX)}"
        )

    clauses: list[dict[str, Any]] = [{"term": {_FULL_NAME_KW: recipe_id}}]
    if fab_name:
        clauses.append({"term": {_FAB_NAME_KW: fab_name}})

    hits = fetch_hits(
        index,
        query(clauses),
        size=_LOCATE_CANDIDATES,
        sort=[{"timestamp": "desc"}],
        source=_SOURCE,
    )
    if not hits:
        raise LookupError(
            f"No document in {index} has full_name={recipe_id!r}"
            + (f" for fab {fab_name!r}" if fab_name else "")
            + ". A recipe that exists in the catalog but has never been measured "
            "has no .idp location to derive — recipe open needs one run, or an "
            "entry in the Redis recipe registry."
        )

    complete: list[_IdpLocation] = []
    incomplete: list[str] = []
    for hit in hits:
        location = _IdpLocation(
            eqp_id=str(hit.get("eqp_id") or "").strip(),
            eqp_ip=str(hit.get("eqp_ip") or "").strip(),
            class_name=str(hit.get("class_name") or "").strip(),
            idw_stem=_stem(hit.get("idw_name")),
            idp_stem=_stem(hit.get("idp_name")),
        )
        missing = [
            name
            for name, value in (
                ("eqp_ip", location.eqp_ip),
                ("class_name", location.class_name),
                ("idw_name", location.idw_stem),
                ("idp_name", location.idp_stem),
            )
            if not value
        ]
        if not missing:
            complete.append(location)
            continue
        incomplete.append(f"{hit.get('timestamp')}: missing {', '.join(missing)}")

    if complete:
        return complete

    raise LookupError(
        f"Found {len(hits)} document(s) in {index} for full_name={recipe_id!r}, "
        "but none carries every field the FTP path needs — "
        + " | ".join(incomplete)
    )
```

Note the "never been measured" message gains a clause about the registry, which the test matches on `"has never been measured"` — that substring is unchanged.

- [ ] **Step 4: Add the dispatcher**

Insert immediately after `_locate_via_meas_hist`:

```python
def _locate_idp(
    tool_type: ToolType,
    recipe_id: str,
    fab_name: str | None,
) -> list[_IdpLocation]:
    """Where this recipe's .idp can be fetched from, best candidate first.

    The Redis registry knows this directly and answers without a query to
    measurement history; meas_hist is the fallback. Both return an ordered
    list rather than one answer so the download can walk it.
    """
    return _locate_via_redis(tool_type, recipe_id, fab_name) or _locate_via_meas_hist(
        tool_type, recipe_id, fab_name
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git commit -m "feat(recipe-search): dispatch .idp location Redis-first

_locate_idp becomes a dispatcher: the Redis registry answers first, meas_hist
is the fallback and remains the only source for fabs the registry does not
cover. The meas_hist path (now _locate_via_meas_hist) returns every complete
document rather than only the newest, so a recipe whose latest tool is
unreachable falls through to the previous run's tool instead of 502-ing.
" -- back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py \
     back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py
```

---

### Task 5: Download retry across candidates

**Files:**

- Modify: `back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py` (add `_download_first` after `_download_idp`; rewire `get_recipe_open_data`)
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py`

**Interfaces:**

- Consumes: `_locate_idp` (Task 4), `_download_idp` (existing).
- Produces: `_download_first(candidates: list[_IdpLocation], dest_dir: Path) -> Path`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_idp_locate.py`. No new stdlib import is needed — `tmp_path`
is already a `Path`.

```python
from back_dev_home.msr_image.errors import InvalidToolIp

THREE = [
    oe._IdpLocation("CG6300_01", "10.1.2.1", "ADI", "A", "A"),
    oe._IdpLocation("CG6300_07", "10.1.2.7", "ADI", "A", "A"),
    oe._IdpLocation("CG6380_02", "10.1.2.2", "ADI", "A", "A"),
]


def _always_raise(exception_type, message):
    """A _download_idp stand-in that fails on every tool."""
    def _download(location, dest_dir):
        raise exception_type(f"{message} ({location.eqp_id})")
    return _download


class TestDownloadFirst:
    def test_first_success_wins_and_stops(self, monkeypatch, tmp_path):
        dialed = []

        def _download(location, dest_dir):
            dialed.append(location.eqp_id)
            if location.eqp_id != "CG6300_07":
                raise LookupError("connection refused")
            return dest_dir / "A.idp"

        monkeypatch.setattr(oe, "_download_idp", _download)
        assert oe._download_first(THREE, tmp_path) == tmp_path / "A.idp"
        # Stopped at the first success — the third tool was never dialed.
        assert dialed == ["CG6300_01", "CG6300_07"]

    def test_every_tool_failing_names_each_one(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            oe, "_download_idp", _always_raise(LookupError, "no such file")
        )
        with pytest.raises(LookupError) as excinfo:
            oe._download_first(THREE, tmp_path)
        message = str(excinfo.value)
        assert "Tried 3 tool(s)" in message
        assert "CG6300_01" in message and "CG6380_02" in message

    def test_one_blocked_ip_is_skipped_not_fatal(self, monkeypatch, tmp_path):
        def _download(location, dest_dir):
            if location.eqp_id == "CG6300_01":
                raise InvalidToolIp("outside the allowed subnets")
            return dest_dir / "A.idp"

        monkeypatch.setattr(oe, "_download_idp", _download)
        # A single stale roster IP must not fail a recipe held on three tools.
        assert oe._download_first(THREE, tmp_path) == tmp_path / "A.idp"

    def test_every_ip_blocked_reraises_the_guard(self, monkeypatch, tmp_path):
        monkeypatch.setattr(
            oe, "_download_idp", _always_raise(InvalidToolIp, "outside subnets")
        )
        # Not a fetch failure — this is the misconfiguration MIGRATION.md
        # documents InvalidToolIp for, so it must survive as itself.
        with pytest.raises(InvalidToolIp):
            oe._download_first(THREE, tmp_path)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py -q
```

Expected: FAIL — `AttributeError: module ... has no attribute '_download_first'`.

- [ ] **Step 3: Implement `_download_first`**

Insert immediately after `_download_idp`:

```python
def _download_first(candidates: list[_IdpLocation], dest_dir: Path) -> Path:
    """Try each candidate in order and return the first successful download.

    Raises:
        InvalidToolIp: EVERY candidate was refused by the tool-IP guard.
        LookupError: candidates were dialable but none served the file.
    """
    # Imported here, not at module scope, to match _download_idp's deferral of
    # the msr_image imports. InvalidToolIp is NOT a LookupError subclass
    # (msr_image/errors.py: it descends from MsrImageError), so the two except
    # clauses below are disjoint.
    from back_dev_home.msr_image.errors import InvalidToolIp

    failures = []
    blocked = []
    for location in candidates:
        try:
            return _download_idp(location, dest_dir)
        except InvalidToolIp as exc:
            # Skipped rather than raised: one stale roster IP must not fail
            # every recipe held on that tool. The guard still refuses to dial
            # it and the WARNING names it, so the roster can be corrected.
            blocked.append(exc)
            _LOG.warning(
                "recipe_search: %s (%s) is outside SKEWNONO_TOOL_SUBNETS and "
                "was skipped — %s", location.eqp_id, location.eqp_ip, exc,
            )
            failures.append(f"{location.eqp_id} ({location.eqp_ip}): IP blocked")
        except LookupError as exc:
            failures.append(f"{location.eqp_id}: {exc}")

    if blocked and len(blocked) == len(candidates):
        # Not a fetch failure. Every tool holding this recipe sits outside the
        # allowed subnets, which is a configuration fault worth surfacing as
        # itself rather than flattening into "could not download".
        raise blocked[0]

    raise LookupError(
        f"Tried {len(candidates)} tool(s) and none served the .idp — "
        + " | ".join(failures)
    )
```

- [ ] **Step 4: Rewire `get_recipe_open_data`**

Replace the two lines in `get_recipe_open_data` that call `_locate_idp` and `_download_idp`:

```python
    locations = _locate_idp(tool_type, recipe, fab_name)
    with tempfile.TemporaryDirectory(prefix="skewnono-idp-") as tmp_dir:
        local_path = _download_first(locations, Path(tmp_dir))
        frames = _parse_idp(local_path)
```

Update that function's docstring paragraph to match:

```python
    """One recipe's IDP tables: locate -> download -> parse -> map.

    Locate prefers the Redis recipe registry and falls back to measurement
    history; either way it yields tool candidates in preference order and the
    download walks them until one answers.

    The download lands in a temp directory that is removed on the way out.
    Nothing is cached: a recipe's .idp is small, and with the registry path the
    lookup is now two Redis reads rather than an OpenSearch query. If 열어보기
    latency ever becomes a complaint this is still the seam to put a TTL cache
    behind (keyed on the recipe triple, not on the path).
    """
```

- [ ] **Step 5: Run the whole feature suite**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q
```

Expected: PASS.

- [ ] **Step 6: Run the full backend suite for regressions**

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS (~1320 tests, ~17 s). The `sem_list` import added in Task 2 is the one new cross-feature edge — a failure here most likely means an import cycle.

- [ ] **Step 7: Commit**

```bash
git commit -m "feat(recipe-search): retry the .idp download down the tool list

_download_first walks the candidate locations and returns the first successful
fetch, so one powered-off or unreachable tool no longer fails a recipe held on
several. An out-of-subnet IP is skipped with a WARNING rather than propagated,
since a single stale roster entry should not fail every recipe on that tool —
but if EVERY candidate is blocked the guard's InvalidToolIp is re-raised as
itself, which is the configuration fault MIGRATION.md documents it for.
" -- back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py \
     back_dev_home/ebeam/hitachi/recipe_search/tests/test_idp_locate.py
```

---

### Task 6: Documentation

Office DB facts must land in the schema of record **and** the mock docstring —
`CLAUDE.md`'s two-places rule. This task also corrects two passages that the
code change makes false.

**Files:**

- Modify: `docs/datatables/recipe_name_list.txt`
- Modify: `docs/datatables/recipe_idp.txt`
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/providers/mock.py` (docstring only)
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/MIGRATION.md`
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py` (module docstring only)

**Interfaces:**

- Consumes: the finished behavior from Tasks 1–5.
- Produces: nothing consumed by later tasks.

- [ ] **Step 1: Add both hash schemas to `recipe_name_list.txt`**

Append a section after the existing `주의` list and before `recipe 자세히 보기 / 비교는 이 소스가 아닙니다`. Written in Korean to match the file:

```text
Recipe 위치 registry (user-confirmed 2026-07-29)
================================================

Recipe 이름 목록과 별개로, recipe 파일의 **위치**와 **보유 장비**를 fab 별 hash
2개가 직접 들고 있습니다. recipe open 이 이 둘로 .idp 경로를 조립하므로,
측정된 적 없는 recipe 도 열어볼 수 있습니다.

Key -> "v3_{cdsem|hvsem}_rcp_loc_{fab}"       : recipe 파일 위치
Key -> "v3_{cdsem|hvsem}_tools_in_rcp_{fab}"  : 그 recipe 를 보유한 장비 목록

  {fab} 은 fab 이름의 **소문자** 표기입니다(unique_rcp_list 의 hash field 와
  같은 규칙이지만, 여기서는 field 가 아니라 **key 이름**의 일부입니다).

hash field -> full_name ("class_name/recipe_name")
hash value -> rcp_loc      : [idw_name, idp_name]  (경로 문자열 2개, 순서 고정)
              tools_in_rcp : [eqp_id, ...]

주의

1. rcp_loc 의 value 는 **위치로 읽습니다**(0번 idw, 1번 idp). 항목이 2개보다
   적으면 어댑터는 이 소스를 포기하고 meas_hist 로 넘어갑니다.
2. class_name 은 두 hash 어디에도 없습니다. full_name 의 "/" 앞부분이 곧
   class_name 이므로(meas_hist.txt), 조회에 쓴 key 에서 그대로 떼어 씁니다.
3. tools_in_rcp 는 eqp_id 를 주지만 FTP 는 eqp_ip 로 접속합니다. sem_list
   roster 로 eqp_id -> eqp_ip 를 해석하며, 두 소스의 eqp_id 표기는 동일합니다
   (user-confirmed 2026-07-29). roster 에 없는 eqp_id 는 "표기가 다르다"가
   아니라 "roster 에 그 장비가 없다"는 뜻입니다.
4. value 직렬화 형식은 unique_rcp_list 와 같은 규칙으로 파싱합니다(JSON ->
   Python repr -> 콤마 분리).
```

Then correct the stale closing section of the same file — replace the
`recipe 자세히 보기 / 비교는 이 소스가 아닙니다` body, which still says recipe
open is mock-backed, with:

```text
recipe 자세히 보기 / 비교

자세히 보기(recipe open)는 위 registry 2개로 .idp 경로를 조립해 장비 FTP 에서
파일을 받아 파싱합니다(docs/datatables/recipe_idp.txt). 비교(compare)는 아직
mock 을 그대로 re-export 하고 있습니다 — 열람에서 파생되는 관계를 유지하기
위해 재구현하지 않았습니다.
```

- [ ] **Step 2: Redraw the source chain in `recipe_idp.txt`**

Replace the `소스 체인` section (the diagram plus the paragraph beginning
`측정 이력 문서가`) with:

```text
소스 체인
=========

경로는 Redis registry 에서 먼저 찾고, 없으면 측정 이력에서 찾습니다.

  1순위: Redis (recipe_name_list.txt)
    v3_{cdsem|hvsem}_rcp_loc_{fab}       [idw_name, idp_name]
    v3_{cdsem|hvsem}_tools_in_rcp_{fab}  [eqp_id, ...]  ─► sem_list 로 eqp_ip
    full_name 의 "/" 앞부분                ─► class_name

  2순위: OpenSearch meas_hist_cdsem / meas_hist_hvsem
    ├── eqp_ip       ─────────────────►  FTP host
    ├── class_name   ──┐
    ├── idw_name     ──┼──────────────►  /HITACHI/DEVICE/HD/{class_name}/data/{idw_name}
    └── idp_name     ──┘                      ├── {idp_name}.idp    ← 파싱 대상
                                              └── {idp_name}/       ← raw recipe 파일 폴더

  {idp_name}.idp  ──►  office_utils.read_idp_info.combined_idp_info(idp_file_path)
                         ──►  read_idp_info: dict[str, pd.DataFrame]

두 경로는 **섞지 않습니다**. registry 가 둘 중 하나라도 답하지 못하면 (또는
fab 이 지정되지 않으면) 전체를 meas_hist 로 넘깁니다 — 절반씩 조립한 경로는
나중에 그 경로가 틀렸을 때 출처를 추적할 수 없기 때문입니다.

장비 선택 (user-confirmed 2026-07-29)

  두 경로 모두 후보를 **여러 개** 돌려주고, 다운로드가 순서대로 시도해 먼저
  성공한 것을 씁니다. registry 경로는 sem_list 의 available="On" 장비를 앞에
  두고 registry 순서를 유지하며, meas_hist 경로는 최근 측정 순입니다. 장비 한
  대가 꺼져 있다고 recipe 를 열 수 없게 되지 않도록 하기 위함입니다.

  eqp_ip 가 허용 subnet 밖이면 그 후보만 건너뛰고 WARNING 을 남깁니다. 후보
  **전부**가 그렇다면 InvalidToolIp 를 그대로 올립니다 — 그때는 전송 실패가
  아니라 설정 오류이기 때문입니다.

registry 경로에서는 eqp_id -> eqp_ip 해석에 sem_list 가 필요합니다(lateral
check 와 같은 join). meas_hist 경로에서만 측정 이력 문서가 그 recipe 를 실행한
장비를 이미 지목하므로 join 이 필요 없습니다.
```

- [ ] **Step 3: Update the `mock.py` docstring**

Two edits. First, replace the stale `★ RECIPE-OPEN AND COMPARE STILL RUN OFF
THIS MOCK AT THE OFFICE (2026-07-27).` paragraph — recipe open has been wired
since then — with:

```python
★ COMPARE STILL RUNS OFF THIS MOCK AT THE OFFICE.
`recipe_search/providers/office*.py` RE-EXPORTS `get_recipe_compare_data` from
THIS module, so that generator runs in production and its output there is
fabricated, not 사내 data. It is re-exported rather than reimplemented so it
stays derived from open — the invariant this module guarantees. Recipe open
itself is wired (2026-07-27) and returns parsed IDP data, so open and compare
DISAGREE office-side until the batched fetch lands; see MIGRATION.md.
```

Second, replace the `meas_hist_* -> eqp_ip + class_name + ...` chain diagram
with the two-source version:

```python
    v3_{cdsem,hvsem}_rcp_loc_{fab}       -> [idw_name, idp_name]
    v3_{cdsem,hvsem}_tools_in_rcp_{fab}  -> [eqp_id, ...] -> sem_list -> eqp_ip
      (fallback: meas_hist_* -> eqp_ip + class_name + idw_name + idp_name)
        -> /HITACHI/DEVICE/HD/{class}/data/{idw}/{idp}.idp
        -> office_utils.read_idp_info.combined_idp_info(path)
        -> {"wafer_mp_info": df, "wafer_align_info": df, "idp_image_info": df}
```

Do not change any generated value in `mock.py` — the mock never reaches Redis,
and these keys teach nothing new about the data it fabricates.

- [ ] **Step 4: Update `MIGRATION.md`**

In the `/recipe-detail` section, replace the four-step table with:

```markdown
| Step | Function | Source | Runs at home? |
| --- | --- | --- | --- |
| locate (1st) | `_locate_via_redis` | `v3_*_rcp_loc_*` + `v3_*_tools_in_rcp_*` + sem_list | no |
| locate (2nd) | `_locate_via_meas_hist` | `meas_hist_{cdsem,hvsem}` | no |
| fetch | `_download_first` → `_download_idp` | tool FTP (`SKEWNONO_TOOL_FTP_*`) | no |
| parse | `_parse_idp` | `office_utils.read_idp_info` | via stand-in |
| map | `_to_detail_response` | pure | yes |
```

Replace the paragraph beginning `` `recipe_id` is the catalog's `"class/recipe"` string `` with:

```markdown
`recipe_id` is the catalog's `"class/recipe"` string, which is both the
registry hash field and meas_hist's `full_name` — so the id the search table
hands back is already the lookup key, and its `/` prefix is the FTP class
directory. The Redis registry is tried first and is all-or-nothing: if either
hash misses, or `fac_id` is blank, the whole location falls to meas_hist rather
than blending the two. Both paths return tool candidates in preference order
(registry: `available == "On"` first; meas_hist: newest run first) and
`_download_first` walks them until one serves the file.
```

Update the error bullets under that section to:

```markdown
  - Recipe in neither the registry nor meas_hist → `LookupError` (502).
  - Every candidate tool refused or lacked the file → `LookupError` (502)
    naming each tool tried and why.
  - `eqp_ip` outside `SKEWNONO_TOOL_SUBNETS` → that candidate is skipped with a
    WARNING; if **every** candidate is outside, `InvalidToolIp` is raised. The
    IP comes from Redis or OpenSearch rather than a client, but the backend
    still opens a socket to it, so the SSRF guard applies.
  - `office_utils` not importable → `RuntimeError` (503, unconfigured).
  - Parser returns the wrong keys → `LookupError` (502).
```

Finally, in the Status table at the top, change the `/recipe-detail` office
source cell to:

```markdown
| `/recipe-detail` | Redis recipe registry (fallback: meas_hist) → tool FTP `.idp` → `office_utils.read_idp_info` | wired, unverified on real data |
```

- [ ] **Step 5: Update the `office_example.py` module docstring**

Replace the `**Recipe open** (``get_recipe_open_data``)` block's diagram and
the paragraph beginning `` ``eqp_ip`` riding on the measurement document `` with:

```python
**Recipe open** (``get_recipe_open_data``) — the measuring tool's own FTP
server. The path is assembled from the Redis recipe registry when it can be,
and from one meas_hist document when it cannot::

    v3_{cdsem,hvsem}_rcp_loc_{fab}        full_name -> [idw_name, idp_name]
    v3_{cdsem,hvsem}_tools_in_rcp_{fab}   full_name -> [eqp_id, ...]
                                                          │
                          sem_list roster: eqp_id ────────┴──►  FTP host
                          full_name's "/" prefix ──────────►  {class}

    (fallback) meas_hist_{cdsem,hvsem}            (OpenSearch)
      ├── eqp_ip      ─────────────────────────►  FTP host
      ├── class_name  ──┐
      ├── idw_name    ──┼───────────────────────►  /HITACHI/DEVICE/HD/{class}/data/{idw}
      └── idp_name    ──┘                              └── {idp}.idp
                                                            │
        office_utils.read_idp_info.combined_idp_info(path) ◄─┘
          -> {"wafer_mp_info": df, "wafer_align_info": df, "idp_image_info": df}

The two are all-or-nothing rather than blended: a location assembled half from
each would be untraceable the day the path it produces turns out wrong. Both
yield an ORDERED LIST of candidates and ``_download_first`` walks it, so one
unreachable tool no longer fails a recipe several tools hold.

On the registry path the ``eqp_id -> eqp_ip`` join through sem_list IS needed —
the same one lateral check makes. Only on the meas_hist path is it avoidable,
because there the measurement row already names the tool that ran the recipe,
so the host it must be readable from is the host we just proved ran it.
```

- [ ] **Step 6: Lint the Markdown**

```bash
npm run lint:md
```

Expected: clean. Only `MIGRATION.md` is in scope — `docs/datatables/*.txt` are
`.txt` and `.scratch/` is deliberately unlinted.

- [ ] **Step 7: Run the full suite one more time**

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git commit -m "docs(recipe-search): record the Redis recipe registry as the .idp source

Documents v3_{family}_rcp_loc_{fab} and v3_{family}_tools_in_rcp_{fab} in the
schema of record and in the mock docstring, per the two-places rule: the doc is
read when an office adapter is written, mock.py is what every home session runs
against, and a fact in one but not the other is a fact the next home session
contradicts.

Corrects two passages the wiring makes false: recipe_idp.txt said recipe open
needs no sem_list join (true only on the meas_hist fallback now), and mock.py
still claimed recipe open runs off the mock at the office (wired 2026-07-27).
" -- docs/datatables/recipe_name_list.txt \
     docs/datatables/recipe_idp.txt \
     back_dev_home/ebeam/hitachi/recipe_search/providers/mock.py \
     back_dev_home/ebeam/hitachi/recipe_search/MIGRATION.md \
     back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py
```

---

### Task 7: Land it and tear the worktree down

**Files:** none edited.

- [ ] **Step 1: Confirm the branch is clean and the gitignored copy was not committed**

```bash
git status --short
git log --oneline main..work/rcp-loc --name-only | grep -c "providers/office.py" || echo "clean: office.py not committed"
```

Expected: a clean tree, and `clean: office.py not committed`.

- [ ] **Step 2: Merge to main and push**

From the repo root (`/Users/daeyoung/Codes/skewnono_v3_nuxt`):

```bash
git merge --ff-only work/rcp-loc && git push
```

- [ ] **Step 3: Remove the worktree and branch**

```bash
git worktree remove ../skewnono-rcp-loc && git branch -d work/rcp-loc
git worktree list
```

Expected: `git worktree list` shows the main tree alone. A task is not done
until it does.

- [ ] **Step 4: Offer to refresh the local `office.py`**

`providers/office.py` is a gitignored copy and is now behind the template. It
is not exercised at home unless `SKEWNONO_RECIPE_SEARCH_PROVIDER=office` is
set, so this is the user's call rather than an automatic step:

```bash
.venv/bin/python -m scripts.sync_office_adapters recipe_search
```

## Notes for the implementer

**What must not change.** `_IdpLocation`, `_idp_remote_path`, `_download_idp`,
`_parse_idp`, `_to_detail_response`, `_scalar`, `_records`,
`_sourceless_extras`, and the whole catalog path apart from the
`_parse_recipe_list` rename. `tests/test_idp_mapping.py` and
`tests/test_contract.py` must pass unedited — if either needs a change, the
change is wrong.

**Why `None` and not an exception** for a registry miss: the registry is newer
than meas_hist and is not promised to cover every fab. A miss is the expected
state for an unmigrated fab, so it must be cheap and quiet, not an error path.

**Why the tests stub rather than mock the client.** `_FakeRedis` is nine lines
and exposes exactly the one method the adapter uses. A `MagicMock` would pass
even if the adapter started calling `hgetall`, which is precisely the drift
these tests exist to catch.

**Compare stays mock-backed.** `tools_in_rcp` is exactly the input the deferred
batched-compare work needs (one FTP session per distinct tool, every recipe's
`.idp` in one `HostSpec(files=[...])`), but that is a separate job and the
`TODO(office)` above the mock re-export stays where it is.
