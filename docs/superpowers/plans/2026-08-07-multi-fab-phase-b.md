# Multi-fab Phase B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recipe-search family serves fab-tagged rows with owning-fab detail routing, and live-alarm merges N fac feeds — completing multi-fab support per `docs/superpowers/specs/2026-08-07-multi-fab-phase-b-design.md`.

**Architecture:** Catalog rows become `(recipe_name, fab_name)` pairs end-to-end (contract → mock/office providers → frontend table). Detail screens stay single-fab but receive the owning fab via a `fab_name` query param while the URL path segment keeps the multi-fab selection. Ranking rows in recipe-tat/fail-issue gain contributing `fab_names` so their detail links stop assuming `fabs[0]`. Live-alarm maps selected fabs to distinct fac_ids, refreshes each, merges the boards, and stamps each event with its fab at read time.

**Tech Stack:** Flask + TypedDict contracts, Redis hash / OpenSearch composite aggs (office adapters), Nuxt 4 + NuxtUI, `useState`/`usePersistedState` (no Pinia), `node --test` + pytest.

## Global Constraints

- Wire format: request `?fab_name=R3,M16B` (comma-joined, uppercase); response meta `fab_names: list[str]` echoing the request — empty list when fab was omitted.
- Row identity is the `(recipe_name, fab_name)` pair. Never dedupe across fabs; duplicate names appear as adjacent rows.
- Detail screens (open / lateral / meas-hist) stay single-fab: the owning fab travels as `fab_name` in the **query**, the URL **path** segment keeps the current multi-fab selection.
- Fab badges render only when 2+ fabs are selected. Match the existing chip idiom (see the OpenSearch chip in `RecipeSearchView.vue`); colors via existing utility classes / `--sk-*` tokens only, no inline hex.
- localStorage v2 keys: `skewnono:recipe-search.selection.v2.{toolType}` and `skewnono:recipe-search.recent.v2.{toolType}`. Old keys are orphaned, not migrated.
- `AlarmEvent.fab_name` is reader-stamped from the roster at board-build time; it is NEVER written into stored ZSET members.
- Ranking `fab_names` = fabs contributing ANY execution to the aggregate (not just failing rows), sorted ascending.
- Backend tests: `.venv/bin/python -m pytest back_dev_home/<feature> -q` from the repo root (never bare `pytest`). Frontend: `npm test` / `npm run typecheck` / `npm run lint` from `front-dev-home/`.
- Commit style `type(scope): summary`, explicit pathspecs only (`git add <paths>` / `git commit -- <paths>`; `git add -A`/`.`/`-a` are banned).
- Korean UI copy uses formal endings (~입니다/~합니다).
- No Pinia, no TanStack Query; `useAsyncData` + `useState` + `usePersistedState` only.

---

## File Structure

Backend (per feature: contracts → routes → data → providers → tests):

- `back_dev_home/ebeam/hitachi/recipe_search/` — catalog row TypedDict, comma parse, tagged mock/office rows, compare body (`contracts.py`, `routes.py`, `data.py`, `providers/{mock,office_example}.py`, `tests/{test_contract,test_routes,test_contracts_shape}.py`)
- `back_dev_home/ebeam/hitachi/recipe_tat/` — RankingRow.fab_names (`contracts.py`, `providers/{mock,office_example}.py`, `tests/test_contract.py`) + `docs/api-contracts/recipe-tat.yaml`
- `back_dev_home/ebeam/hitachi/fail_issue/` — Align/MeasRankingRow.fab_names (same file set) + `docs/api-contracts/fail-issue.yaml`
- `back_dev_home/ebeam/hitachi/live_alarm/` — multi-fac board (`contracts.py`, `routes.py`, `data.py`, `board.py`, `providers/{mock,office_example}.py`, `tests/`)

Frontend:

- Pure TS first (node-testable): `composables/useRecipeSearchApi.ts`, `utils/recipeSearchMatch.ts`, `utils/recipeSelection.ts`, `composables/useRecipeSelectionSet.ts`, `composables/useRecipeRecentSearches.ts`, `composables/useRecipeCompareApi.ts`, `utils/recipeView.ts`, `utils/liveAlarm.ts`, `composables/useLiveAlarmFeed.ts`
- Components: `RecipeRowActions.vue`, `RecipeSearchView.vue`, `RecipeCompareView.vue`, `RecipeOpenView.vue`, `RecipeLateralView.vue`, `RecipeMeasHistView.vue`, `RecipeDetailNav.vue`, `RecipeSwitcher.vue`, `RecipeTatView.vue`, `FailIssueView.vue`, `LiveAlarmView.vue`, `live-alarm/AlarmRow.vue`, `live-alarm/MeasGroup.vue`, `skewvoir/workspace/LeftRail.vue`
- Pages (12): `pages/ebeam/{cd-sem,hv-sem}/[fab]/recipe-search/{index,compare,open,lateral,meas-hist}.vue`, `pages/ebeam/{cd-sem,hv-sem}/[fab]/live-alarm.vue`

---

### Task 1: Backend — recipe_search catalog tagged rows

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/contracts.py` (`RecipeSearchRow` ~line 36, `RecipeSearchResponse` ~line 186)
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/routes.py` (`_resolve_fab_name` ~line 95, catalog endpoint ~line 152)
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/data.py` (`get_recipe_catalog` ~line 42)
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/providers/mock.py` (`get_recipe_catalog` ~line 372)
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py` (`_recipes_for_fab`/`_all_recipes`/`get_recipe_catalog` ~lines 264–320)
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_contract.py`, `tests/test_routes.py`, `tests/test_contracts_shape.py`

**Interfaces:**
- Consumes: existing `_generate_recipe_rows(tool_type, fab_name) -> tuple[str, ...]` (mock), `_parse_str_list` / `_missing_key_error` / `_RECIPE_HASH` (office_example), `promote_request_fab_names(*values)` (already imported in routes.py).
- Produces (later tasks rely on these exactly):
  - `RecipeSearchRow` TypedDict `{recipe_name: str, fab_name: str}`
  - `RecipeSearchResponse` TypedDict `{tool_type: ToolType, fab_names: list[str], total: int, rows: list[RecipeSearchRow]}`
  - `get_recipe_catalog(tool_type: ToolType, fab_names: Sequence[str] | None = None) -> RecipeSearchResponse` (data.py + both providers)
  - routes helper `_resolve_fab_names() -> tuple[str, ...]` (empty tuple = all fabs)

- [ ] **Step 1: Write the failing tests**

In `tests/test_contract.py` (follow the file's existing import/fixture style — it exercises both providers via the import-skip alias pattern; the office side of catalog needs a fake Redis, so monkeypatch `office_example._redis_client`):

```python
def test_mock_catalog_rows_carry_owning_fab():
    payload = mock.get_recipe_catalog("cd-sem", ("R3", "M16B"))
    assert payload["fab_names"] == ["R3", "M16B"]
    assert payload["total"] == len(payload["rows"])
    assert {row["fab_name"] for row in payload["rows"]} == {"R3", "M16B"}
    assert all(row["recipe_name"] for row in payload["rows"])


def test_mock_catalog_duplicate_names_stay_per_fab():
    payload = mock.get_recipe_catalog("cd-sem", ("R3", "M16B"))
    r3 = {r["recipe_name"] for r in payload["rows"] if r["fab_name"] == "R3"}
    m16b = {r["recipe_name"] for r in payload["rows"] if r["fab_name"] == "M16B"}
    shared = r3 & m16b
    # ~20% of mock names overlap by construction; both copies must survive.
    assert shared
    rows_for_shared = [
        r for r in payload["rows"] if r["recipe_name"] in shared
    ]
    assert len(rows_for_shared) == 2 * len(shared)


def test_mock_catalog_single_fab_rows_match_union_slice():
    solo = mock.get_recipe_catalog("cd-sem", ("R3",))
    union = mock.get_recipe_catalog("cd-sem", ("R3", "M16B"))
    union_r3 = [r for r in union["rows"] if r["fab_name"] == "R3"]
    assert solo["rows"] == union_r3


def test_mock_catalog_omitted_fab_uses_default_fabs_and_empty_echo():
    payload = mock.get_recipe_catalog("cd-sem", None)
    assert payload["fab_names"] == []
    assert {row["fab_name"] for row in payload["rows"]} == {"R3", "M16B"}


class _FakeCatalogRedis:
    def __init__(self, entries):
        self._entries = entries  # {b"r3": b'["A", "B"]', ...}

    def hget(self, key, field):
        return self._entries.get(field.encode())

    def hgetall(self, key):
        return self._entries

    def exists(self, key):
        return 1 if self._entries else 0


def test_office_catalog_tags_rows_per_requested_fab(monkeypatch):
    fake = _FakeCatalogRedis({b"r3": b'["A", "B"]', b"m16b": b'["B", "C"]'})
    monkeypatch.setattr(office_example, "_redis_client", lambda: fake)
    payload = office_example.get_recipe_catalog("cd-sem", ("R3", "M16B"))
    assert payload["fab_names"] == ["R3", "M16B"]
    assert payload["rows"] == [
        {"recipe_name": "A", "fab_name": "R3"},
        {"recipe_name": "B", "fab_name": "R3"},
        {"recipe_name": "B", "fab_name": "M16B"},
        {"recipe_name": "C", "fab_name": "M16B"},
    ]


def test_office_catalog_union_preserves_provenance(monkeypatch):
    fake = _FakeCatalogRedis({b"r3": b'["A", "B"]', b"m16b": b'["B"]'})
    monkeypatch.setattr(office_example, "_redis_client", lambda: fake)
    payload = office_example.get_recipe_catalog("cd-sem", None)
    assert payload["fab_names"] == []
    # (B, R3) and (B, M16B) both survive — the union no longer dedupes names.
    names = [(r["recipe_name"], r["fab_name"]) for r in payload["rows"]]
    assert ("B", "R3") in names and ("B", "M16B") in names
```

In `tests/test_routes.py` (follow its existing Flask test-client fixture style):

```python
def test_recipes_route_parses_comma_fab_list(client):
    res = client.get("/api/cdsem/recipe-search/recipes?fab_name=r3,m16b")
    assert res.status_code == 200
    body = res.get_json()
    assert body["fab_names"] == ["R3", "M16B"]
    assert {row["fab_name"] for row in body["rows"]} == {"R3", "M16B"}
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q`
Expected: new tests FAIL (rows are still bare strings / signature mismatch).

- [ ] **Step 3: Implement**

`contracts.py` — replace `RecipeSearchRow = str` with:

```python
class RecipeSearchRow(TypedDict):
    recipe_name: str
    fab_name: str
```

Replace `RecipeSearchResponse`:

```python
class RecipeSearchResponse(TypedDict):
    tool_type: ToolType
    # Echo of the requested fabs (uppercase). Empty when the caller omitted
    # fab_name — the all-fab union; the rows still carry per-row provenance.
    fab_names: list[str]
    total: int
    rows: list[RecipeSearchRow]
```

`routes.py` — add next to `_resolve_fab_name` (which STAYS: the detail/tiered routes remain single-fab):

```python
def _resolve_fab_names() -> tuple[str, ...]:
    raw = request.args.get("fab_name") or ""
    return tuple(part.strip().upper() for part in raw.split(",") if part.strip())
```

Rewrite the catalog endpoint:

```python
@bp.get("/<tool_slug>/recipe-search/recipes")
def recipe_search_recipes(tool_slug: str):
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    fab_names = _resolve_fab_names()
    promote_request_fab_names(*fab_names)
    return jsonify(get_recipe_catalog(tool_type, fab_names or None))
```

`data.py` — new signature (add `from collections.abc import Sequence`):

```python
def get_recipe_catalog(
    tool_type: ToolType,
    fab_names: Sequence[str] | None = None,
) -> RecipeSearchResponse:
    return _provider().get_recipe_catalog(tool_type, fab_names)
```

`providers/mock.py` — add a module constant near `RECIPE_COUNT` and rewrite `get_recipe_catalog` (add the `Sequence` import; `_generate_recipe_rows` is unchanged):

```python
# Stand-in for the office HGETALL field set: the office catalog hash holds one
# field per fab, so "no fab requested" means "every fab in the hash". The mock
# cannot know the real field set; two fabs is enough to exercise the union and
# the ~20% duplicate-name overlap.
_DEFAULT_FAB_NAMES: tuple[str, ...] = ("R3", "M16B")


def get_recipe_catalog(
    tool_type: ToolType,
    fab_names: Sequence[str] | None = None,
) -> RecipeSearchResponse:
    requested = [fab.strip().upper() for fab in (fab_names or ()) if fab and fab.strip()]
    targets = requested or list(_DEFAULT_FAB_NAMES)
    rows: list[RecipeSearchRow] = []
    for fab in targets:
        rows.extend(
            {"recipe_name": name, "fab_name": fab}
            for name in _generate_recipe_rows(tool_type, fab)
        )
    return {
        "tool_type": tool_type,
        "fab_names": requested,
        "total": len(rows),
        "rows": rows,
    }
```

Note the seed already keys on `(tool_type, fab)`, so R3's rows are identical whether requested alone or in a union — same as the office hash.

`providers/office_example.py` — add a tagging helper, retag both paths, new `get_recipe_catalog`:

```python
def _tagged_rows(names: Iterable[str], fab_name: str) -> list[RecipeSearchRow]:
    fab = fab_name.strip().upper()
    return [{"recipe_name": name, "fab_name": fab} for name in names]
```

`_recipes_for_fab` keeps its current body (per-fab `HGET`, `_unique` within one fab). Replace `_all_recipes`:

```python
def _all_recipes(client, key: str) -> list[RecipeSearchRow]:
    """Every fab's recipe names, tagged with the owning fab.

    Reached only when the caller omits ``fab_name``. The hash field IS the
    provenance (field = lowercase fab), and the row grain is (recipe, fab),
    so there is no cross-fab dedupe — a name present in two fabs is two rows.
    """
    entries = client.hgetall(key)
    if not entries:
        raise _missing_key_error(key)
    rows: list[RecipeSearchRow] = []
    for field, value in entries.items():
        fab = field.decode() if isinstance(field, bytes) else str(field)
        rows.extend(_tagged_rows(_unique(_parse_str_list(value)), fab))
    return rows
```

```python
def get_recipe_catalog(
    tool_type: ToolType,
    fab_names: Sequence[str] | None = None,
) -> RecipeSearchResponse:
    key = _RECIPE_HASH.get(tool_type)
    if key is None:
        raise ValueError(
            f"Unknown tool_type {tool_type!r}; expected one of {sorted(_RECIPE_HASH)}"
        )
    requested = [fab.strip().upper() for fab in (fab_names or ()) if fab and fab.strip()]
    client = _redis_client()
    if requested:
        rows: list[RecipeSearchRow] = []
        for fab in requested:
            rows.extend(_tagged_rows(_recipes_for_fab(client, key, fab), fab))
    else:
        rows = _all_recipes(client, key)
    return {
        "tool_type": tool_type,
        "fab_names": requested,
        "total": len(rows),
        "rows": rows,
    }
```

Update any existing assertions in `tests/test_contract.py` / `tests/test_contracts_shape.py` / `tests/test_routes.py` that treat `rows` as strings or read `fab_name` off the envelope.

- [ ] **Step 4: Run the feature suite**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/recipe_search
git commit -m "feat(recipe-search): catalog rows become (recipe, fab) pairs with fab_names meta"
```

---

### Task 2: Backend — recipe_search compare takes per-recipe fabs

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/contracts.py` (add `CompareRequestItem`; `RecipeCompareResponse` ~line 224)
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/routes.py` (compare endpoint ~line 251)
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/data.py` (`get_recipe_compare_data` ~line 55)
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/providers/mock.py` (`get_recipe_compare_data` ~line 1077)
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/providers/office_example.py` (only if its compare re-export names the old signature — verify the re-export still resolves)
- Test: `back_dev_home/ebeam/hitachi/recipe_search/tests/test_contract.py`, `tests/test_routes.py`

**Interfaces:**
- Consumes: `get_recipe_open_data(recipe_id, fab_name, tool_category)` (unchanged), Task 1's contract style.
- Produces:
  - `CompareRequestItem` TypedDict `{recipe_name: str, fab_name: str}` in contracts.py
  - `get_recipe_compare_data(tool_type: ToolType, recipes: Sequence[CompareRequestItem]) -> RecipeCompareResponse`
  - `RecipeCompareResponse` meta: `fab_names: list[str]` (distinct, first-seen order) replacing `fab_name`
  - POST body: `{"recipes": [{"recipe_name": str, "fab_name": str}]}` — old `recipe_names`+`fab_name` body is GONE (400)

- [ ] **Step 1: Write the failing tests**

```python
def test_mock_compare_cross_fab_recipes_differ():
    payload = mock.get_recipe_compare_data("cd-sem", [
        {"recipe_name": "SAME/NAME_ABC123_STD_00001", "fab_name": "R3"},
        {"recipe_name": "SAME/NAME_ABC123_STD_00001", "fab_name": "M16B"},
    ])
    assert payload["fab_names"] == ["R3", "M16B"]
    assert [r["fab_name"] for r in payload["recipes"]] == ["R3", "M16B"]
    # Same name, different fab => genuinely different generated tables.
    assert payload["recipes"][0]["parameters"] != payload["recipes"][1]["parameters"]
```

Route test (in `tests/test_routes.py`):

```python
def test_compare_route_takes_per_recipe_fabs(client):
    res = client.post("/api/cdsem/recipe-search/compare", json={
        "recipes": [
            {"recipe_name": "A/B_ABC123_STD_00001", "fab_name": "r3"},
            {"recipe_name": "A/B_ABC123_STD_00001", "fab_name": "m16b"},
        ]
    })
    assert res.status_code == 200
    body = res.get_json()
    assert body["fab_names"] == ["R3", "M16B"]


def test_compare_route_rejects_legacy_body(client):
    res = client.post("/api/cdsem/recipe-search/compare", json={
        "recipe_names": ["A"], "fab_name": "R3"
    })
    assert res.status_code == 400
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q`

- [ ] **Step 3: Implement**

`contracts.py`:

```python
class CompareRequestItem(TypedDict):
    recipe_name: str
    fab_name: str
```

`RecipeCompareResponse`: replace `fab_name: str | None` with `fab_names: list[str]` (comment: distinct fabs of the compared recipes, first-seen order).

`routes.py` compare endpoint:

```python
@bp.post("/<tool_slug>/recipe-search/compare")
def recipe_search_compare(tool_slug: str):
    tool_type = _resolve_tool_type(tool_slug)
    if not tool_type:
        return jsonify({"error": "tool_slug must be 'cdsem' or 'hvsem'"}), 400

    payload = request.get_json(silent=True) or {}
    raw_recipes = payload.get("recipes")
    if not isinstance(raw_recipes, list) or not raw_recipes:
        return jsonify({"error": "recipes must be a non-empty list"}), 400
    if len(raw_recipes) > 200:
        return jsonify({"error": "recipes exceeds the 200-recipe limit"}), 400

    recipes: list[CompareRequestItem] = []
    for item in raw_recipes:
        if not isinstance(item, dict):
            return jsonify({"error": "recipes items must be objects"}), 400
        name = str(item.get("recipe_name") or "").strip()
        if not name:
            return jsonify({"error": "recipes items need a recipe_name"}), 400
        fab = str(item.get("fab_name") or "").strip().upper()
        recipes.append({"recipe_name": name, "fab_name": fab})

    promote_request_fab_names(*(item["fab_name"] for item in recipes))
    return jsonify(get_recipe_compare_data(tool_type, recipes))
```

`data.py`:

```python
def get_recipe_compare_data(
    tool_type: ToolType,
    recipes: Sequence[CompareRequestItem],
) -> RecipeCompareResponse:
    return _provider().get_recipe_compare_data(tool_type, recipes)
```

(import `CompareRequestItem` from `.contracts`.)

`providers/mock.py` — keep the parameter-extraction body, change the loop head and envelope:

```python
def get_recipe_compare_data(
    tool_type: ToolType,
    recipes: Sequence[CompareRequestItem],
) -> RecipeCompareResponse:
    out: list[CompareRecipe] = []
    fab_order: list[str] = []
    for item in recipes:
        name = (item.get("recipe_name") or "").strip()
        if not name:
            continue
        fab = (item.get("fab_name") or "").strip().upper() or None
        detail = get_recipe_open_data(
            recipe_id=name, fab_name=fab, tool_category=tool_type
        )
        # ... existing seen/parameters extraction unchanged ...
        out.append({
            "recipe_id": detail["recipe_id"],
            "fab_name": detail["fab_name"],
            "locator": detail["locator"],
            "parameters": parameters,
        })
        if detail["fab_name"] not in fab_order:
            fab_order.append(detail["fab_name"])
    return {"tool_type": tool_type, "fab_names": fab_order, "recipes": out}
```

`office_example.py`: compare is re-exported from the mock — confirm the re-export line still imports a name that exists and leave it.

- [ ] **Step 4: Run the feature suite** — `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_search -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/recipe_search
git commit -m "feat(recipe-search): compare body carries per-recipe fab, enabling cross-fab compare"
```

---

### Task 3: Backend — recipe_tat ranking rows gain contributing fab_names

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/contracts.py` (`RankingRow` ~line 40)
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/providers/mock.py` (`get_ranking` ~line 342)
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/providers/office_example.py` (`get_ranking` ~line 83)
- Modify: `docs/api-contracts/recipe-tat.yaml` (ranking row schema)
- Test: `back_dev_home/ebeam/hitachi/recipe_tat/tests/test_contract.py`

**Interfaces:**
- Consumes: `FAB_NAME_KW = "fab_name.keyword"` from `back_dev_home/ebeam/hitachi/_office_meas_hist.py:85`.
- Produces: `RankingRow` gains `fab_names: list[str]` — fabs contributing ANY execution, sorted ascending. Frontend (Task 8) relies on the key name `fab_names`.

- [ ] **Step 1: Write the failing test**

```python
def test_ranking_rows_carry_contributing_fabs():
    rows = mock.get_ranking("cd-sem", ("R3", "M16B"), None, None, limit=20)
    assert rows
    for row in rows:
        assert row["fab_names"] == sorted(row["fab_names"])
        assert row["fab_names"]
        assert set(row["fab_names"]) <= {"R3", "M16B"}


def test_single_fab_ranking_tags_that_fab_only():
    rows = mock.get_ranking("cd-sem", ("R3",), None, None, limit=5)
    assert all(row["fab_names"] == ["R3"] for row in rows)
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_tat -q`

- [ ] **Step 3: Implement**

`contracts.py` `RankingRow` — add:

```python
    # Fabs whose measurements entered this aggregate, sorted asc. The detail
    # link uses this to route to the owning fab's registry (multi-fab spec §6.1).
    fab_names: list[str]
```

`providers/mock.py` `get_ranking` — in the bucket setdefault add `"fabs": set()`; after the setdefault add `bucket["fabs"].add(str(row["fab_name"]).upper())`; in the output dict add `"fab_names": sorted(bucket["fabs"])`.

`providers/office_example.py` `get_ranking` — import `FAB_NAME_KW` from `back_dev_home.ebeam.hitachi._office_meas_hist` (extend the existing import), add to `sub_aggs`:

```python
        "fabs": {"terms": {"field": FAB_NAME_KW, "size": 16}},
```

and in the row-build loop:

```python
        fab_buckets = bucket.get("fabs", {}).get("buckets", [])
        fab_names = sorted({str(b["key"]).upper() for b in fab_buckets})
```

then `fab_names=fab_names` in the `RankingRow(...)` call.

`docs/api-contracts/recipe-tat.yaml`: add `fab_names` (array of string, sorted asc, "fabs contributing to the aggregate") to the ranking row schema.

- [ ] **Step 4: Run** — `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_tat -q` → PASS. Then `npm run lint:md` from the repo root (YAML is not Markdown, but run it anyway if any .md changed; skip otherwise).

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/recipe_tat docs/api-contracts/recipe-tat.yaml
git commit -m "feat(recipe-tat): ranking rows carry contributing fab_names"
```

---

### Task 4: Backend — fail_issue ranking rows gain contributing fab_names

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/fail_issue/contracts.py` (`AlignRankingRow` ~line 72, `MeasRankingRow` ~line 84)
- Modify: `back_dev_home/ebeam/hitachi/fail_issue/providers/mock.py` (`get_align_ranking` ~line 314, `get_meas_ranking` ~line 369)
- Modify: `back_dev_home/ebeam/hitachi/fail_issue/providers/office_example.py` (`_ranked_recipe_buckets` ~line 223, both `get_*_ranking`)
- Modify: `docs/api-contracts/fail-issue.yaml`
- Test: `back_dev_home/ebeam/hitachi/fail_issue/tests/test_contract.py`

**Interfaces:**
- Consumes: `FAB_NAME_KW` (as Task 3).
- Produces: `AlignRankingRow.fab_names: list[str]` and `MeasRankingRow.fab_names: list[str]` — same semantics as Task 3 (ALL executions, sorted asc).

- [ ] **Step 1: Write the failing tests**

```python
def test_align_ranking_rows_carry_contributing_fabs():
    rows = mock.get_align_ranking("cd-sem", ("R3", "M16B"), None, None, limit=20)
    assert rows
    for row in rows:
        assert row["fab_names"] == sorted(row["fab_names"])
        assert row["fab_names"]
        assert set(row["fab_names"]) <= {"R3", "M16B"}


def test_meas_ranking_rows_carry_contributing_fabs():
    rows = mock.get_meas_ranking("cd-sem", ("R3", "M16B"), None, None, limit=20)
    assert rows
    for row in rows:
        assert row["fab_names"] == sorted(row["fab_names"])
        assert row["fab_names"]
        assert set(row["fab_names"]) <= {"R3", "M16B"}


def test_single_fab_rankings_tag_that_fab_only():
    align = mock.get_align_ranking("cd-sem", ("R3",), None, None, limit=5)
    meas = mock.get_meas_ranking("cd-sem", ("R3",), None, None, limit=5)
    assert all(row["fab_names"] == ["R3"] for row in align)
    assert all(row["fab_names"] == ["R3"] for row in meas)
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/fail_issue -q`

- [ ] **Step 3: Implement**

`contracts.py`: add the same `fab_names: list[str]` field + comment to both ranking row TypedDicts.

`providers/mock.py`: in BOTH ranking functions, add `"fabs": set()` to the bucket template, `bucket["fabs"].add(str(row["fab_name"]).upper())` next to the `exec_count` increment (so non-failing executions count too), and `"fab_names": sorted(bucket["fabs"])` in the output row.

`providers/office_example.py`: in `_ranked_recipe_buckets`, add to `sub_aggs` (recipe level — NOT under the `fail` filter, because contributing fabs count every execution):

```python
        "fabs": {"terms": {"field": FAB_NAME_KW, "size": 16}},
```

Add a shared parser next to `_sample_eqp_ids`:

```python
def _bucket_fab_names(bucket: dict[str, Any]) -> list[str]:
    fab_buckets = bucket.get("fabs", {}).get("buckets", [])
    return sorted({str(b["key"]).upper() for b in fab_buckets})
```

and pass `fab_names=_bucket_fab_names(bucket)` in both `AlignRankingRow(...)` and `MeasRankingRow(...)` constructions.

`docs/api-contracts/fail-issue.yaml`: add `fab_names` to both ranking row schemas.

- [ ] **Step 4: Run** — `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/fail_issue -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/fail_issue docs/api-contracts/fail-issue.yaml
git commit -m "feat(fail-issue): align/meas ranking rows carry contributing fab_names"
```

---

### Task 5: Backend — live_alarm multi-fab board

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/live_alarm/contracts.py` (`AlarmEvent` ~line 82, `LiveAlarmPayload` ~line 117)
- Modify: `back_dev_home/ebeam/hitachi/live_alarm/board.py` (`payload` ~line 56; add `merged_meta`)
- Modify: `back_dev_home/ebeam/hitachi/live_alarm/routes.py` (~line 16)
- Modify: `back_dev_home/ebeam/hitachi/live_alarm/data.py` (`get_board`)
- Modify: `back_dev_home/ebeam/hitachi/live_alarm/providers/mock.py` (`get_board` ~line 242)
- Modify: `back_dev_home/ebeam/hitachi/live_alarm/providers/office_example.py` (`_build_board` ~line 85, `get_board` ~line 131)
- Test: `back_dev_home/ebeam/hitachi/live_alarm/tests/test_board.py`, `tests/test_mock.py`, `tests/test_contract.py`, `tests/test_office_reader.py`

**Interfaces:**
- Consumes: `roster.RosterIndex.fac_id_for(fab, tool_type)`, `roster.norm(fab)`, `refresh.ensure_fresh(client, fac_id, now, fetch)`, `refresh.keys(fac_id)`, `board.parse_members` (requires only `id`+`occurred_epoch`, so stamping an extra key at read time is safe), `board.dedupe_by_id`, `feed_status_for` (unchanged).
- Produces:
  - `AlarmEvent` + `fab_name: str` (reader-stamped; never stored in ZSET members)
  - `LiveAlarmPayload`: `fab_name: str` → `fab_names: list[str]`, + `not_configured_fabs: list[str]`
  - `board.payload(*, tool_type, fab_names: Sequence[str], now, configured, meta=None, unmatched_count=0, not_configured_fabs=(), events=())`
  - `board.merged_meta(metas: Sequence[dict | None]) -> dict | None`
  - `get_board(tool_type: ToolType, fab_names: Sequence[str]) -> LiveAlarmPayload` (data.py + both providers)
  - Route accepts `?fab_name=R3,M16B`; empty still → 400. Values are NOT uppercased in the route (roster.norm normalizes downstream, matching today).

- [ ] **Step 1: Write the failing tests**

`tests/test_board.py`:

```python
def test_merged_meta_none_when_any_fac_never_fetched():
    assert board.merged_meta([{"fetched_at": 100}, None]) is None
    assert board.merged_meta([]) is None


def test_merged_meta_takes_oldest_fetch():
    assert board.merged_meta([{"fetched_at": 100}, {"fetched_at": 40}]) == {"fetched_at": 40}


def test_payload_lists_fabs_and_not_configured():
    p = board.payload(
        tool_type="cd-sem", fab_names=["R3", "M16B"], now=1000, configured=True,
        meta={"fetched_at": 990}, not_configured_fabs=["M16B"],
    )
    assert p["fab_names"] == ["R3", "M16B"]
    assert p["not_configured_fabs"] == ["M16B"]
    assert p["feed_status"] == "live"
```

`tests/test_mock.py` (adapt names to the file's existing fixtures — it freezes time / uses the roster):

```python
def test_mock_board_stamps_event_fab():
    payload = mock.get_board("cd-sem", ("R3", "M16B"))
    assert payload["fab_names"] == ["R3", "M16B"]
    for event in payload["events"]:
        assert event["fab_name"] in {"R3", "M16B"}


def test_mock_board_partial_not_configured():
    payload = mock.get_board("cd-sem", ("R3", "NOPE"))
    assert payload["not_configured_fabs"] == ["NOPE"]
    assert payload["feed_status"] != "not_configured"


def test_mock_board_all_unconfigured_is_not_configured():
    payload = mock.get_board("cd-sem", ("NOPE1", "NOPE2"))
    assert payload["feed_status"] == "not_configured"
    assert payload["not_configured_fabs"] == ["NOPE1", "NOPE2"]
```

- [ ] **Step 2: Run to verify failure** — `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm -q`

- [ ] **Step 3: Implement**

`contracts.py` `AlarmEvent` — add at the end:

```python
    # Which fab this event belongs to, derived by the READER from the roster's
    # placement_of(eqp_id) at board-build time. Never written into the stored
    # ZSET member: members outlive roster changes, and the roster at read time
    # is the authority on placement.
    fab_name: str
```

`LiveAlarmPayload` — replace `fab_name: str` with:

```python
    # The requested fabs, echoed verbatim (order preserved).
    fab_names: list[str]
```

and add after `unmatched_count`:

```python
    # Requested fabs holding no tool of this family — the board still renders
    # for the configured ones; the frontend names these in a footnote.
    not_configured_fabs: list[str]
```

`board.py` — `payload` becomes:

```python
def payload(
    *,
    tool_type: ToolType,
    fab_names: Sequence[str],
    now: int,
    configured: bool,
    meta: dict[str, Any] | None = None,
    unmatched_count: int = 0,
    not_configured_fabs: Sequence[str] = (),
    events: Iterable[AlarmEvent] = (),
) -> LiveAlarmPayload:
    # (docstring unchanged in spirit; `configured` now means "at least one
    # requested fab is configured".)
    return {
        "fab_names": list(fab_names),
        "tool_type": tool_type,
        "feed_status": feed_status_for(meta, configured, now=now),
        "fetched_at": iso(meta["fetched_at"]) if meta else None,
        "covered_since": iso(now - BOARD_WINDOW_SEC) if configured else None,
        "server_now": iso(now),
        "board_window_sec": BOARD_WINDOW_SEC,
        "unmatched_count": unmatched_count,
        "not_configured_fabs": list(not_configured_fabs),
        "events": list(events),
    }
```

Add:

```python
def merged_meta(metas: Sequence[dict[str, Any] | None]) -> dict[str, Any] | None:
    """Worst-of merge across facilities: None if ANY fac has never fetched
    (feed_status_for then says stale), else the OLDEST fetched_at — so one
    stale fac makes the merged board stale rather than hiding behind a
    fresher sibling."""
    if not metas or any(m is None or "fetched_at" not in m for m in metas):
        return None
    return {"fetched_at": min(int(m["fetched_at"]) for m in metas)}
```

(`Sequence` import from `collections.abc`.)

`routes.py`:

```python
    raw = request.args.get("fab_name") or ""
    fab_names = tuple(part.strip() for part in raw.split(",") if part.strip())
    if not fab_names:
        return jsonify(error="fab_name is required"), 400

    return jsonify(get_board(tool_type, fab_names))
```

`data.py`: `get_board(tool_type: ToolType, fab_names: Sequence[str]) -> LiveAlarmPayload` forwarding to the provider (add the `Sequence` import).

`providers/mock.py` `get_board` — new shape (keep `_COUNTS`/`_HOT_BURST`/`_STALE_ENV` mechanics; import `roster` if not already):

```python
def get_board(tool_type: ToolType, fab_names: Sequence[str]) -> LiveAlarmPayload:
    import os

    now = int(time.time())
    index = _index()

    placements = [(fab, index.fac_id_for(fab, tool_type)) for fab in fab_names]
    configured = [(fab, fac) for fab, fac in placements if fac is not None]
    not_configured = [fab for fab, fac in placements if fac is None]
    if not configured:
        return board.payload(
            tool_type=tool_type, fab_names=list(fab_names), now=now,
            configured=False, not_configured_fabs=not_configured,
        )

    stale = os.environ.get(_STALE_ENV, "").strip().lower() in {"1", "true", "yes"}
    slot = (now // 60) % len(_COUNTS)
    count = _COUNTS[slot]
    model = "TP4000" if tool_type == "hv-sem" else "CG6300"

    events = []
    for offset, (fab, _fac) in enumerate(configured):
        eqp_ids = index.eqp_ids_in(fab, tool_type) or [_UNROSTERED_EQP_ID]
        # offset*100_000 keeps ids distinct across fabs without changing the
        # per-fab shape the existing tests describe.
        fab_events = [
            _event(now, offset * 100_000 + i, eqp_ids[i % len(eqp_ids)], model)
            for i in range(count)
        ]
        if offset == 0:
            # The grouping burst stays on the first configured fab only.
            fab_events += [
                _event(
                    now, offset * 100_000 + count + n, eqp_ids[0], model,
                    alid="9007" if n % 2 else "9035",
                    recipe_id=_RECIPES[0],
                )
                for n in range(_HOT_BURST if count else 0)
            ]
        for event in fab_events:
            event["fab_name"] = roster.norm(fab)
        events += fab_events

    # Withheld unrostered events: one per DISTINCT fac, so sibling fabs that
    # share a facility do not double-count the same roster gap.
    distinct_facs = list(dict.fromkeys(fac for _fab, fac in configured))
    withheld = (
        [_event(now, 900_000 + i, _UNROSTERED_EQP_ID) for i in range(len(distinct_facs))]
        if slot == len(_COUNTS) - 1
        else []
    )

    return board.payload(
        tool_type=tool_type,
        fab_names=list(fab_names),
        now=now,
        configured=True,
        meta={"fetched_at": now - 2000 if stale else now},
        unmatched_count=len(withheld),
        not_configured_fabs=not_configured,
        events=sorted(events, key=lambda e: e["occurred_epoch"], reverse=True),
    )
```

`providers/office_example.py` — `_build_board` reads N facs and stamps fabs:

```python
def _build_board(
    client,
    index: roster.RosterIndex,
    tool_type: ToolType,
    *,
    fab_names: list[str],
    wanted_fabs: set[str],
    fac_ids: Sequence[str],
    not_configured_fabs: Sequence[str],
    now: int,
    meta: dict | None,
) -> LiveAlarmPayload:
    """Merge the selected fabs' boards out of their facilities' ZSETs."""
    mine: list = []
    unmatched = 0
    for fac_id in fac_ids:
        raw = client.zrangebyscore(
            refresh.keys(fac_id).events,
            now - BOARD_WINDOW_SEC,
            now + FUTURE_TOLERANCE_SEC,
        )
        for event in board.dedupe_by_id(board.parse_members(raw)):
            placement = index.placement_of(event.get("eqp_id", ""))
            if placement is None:
                # (existing roster-gap comment stays)
                unmatched += 1
            elif placement[1] == tool_type and placement[0] in wanted_fabs:
                stamped = dict(event)
                stamped["fab_name"] = placement[0]
                mine.append(stamped)

    mine.sort(key=lambda e: e["occurred_epoch"], reverse=True)
    return board.payload(
        tool_type=tool_type, fab_names=fab_names, now=now, configured=True,
        meta=meta, unmatched_count=unmatched,
        not_configured_fabs=not_configured_fabs, events=mine,
    )
```

`get_board`:

```python
def get_board(tool_type: ToolType, fab_names: Sequence[str]) -> LiveAlarmPayload:
    index = _index()
    placements = [(fab, index.fac_id_for(fab, tool_type)) for fab in fab_names]
    configured = [(fab, fac) for fab, fac in placements if fac is not None]
    not_configured = [fab for fab, fac in placements if fac is None]
    if not configured:
        return board.payload(
            tool_type=tool_type, fab_names=list(fab_names),
            now=int(time.time()), configured=False,
            not_configured_fabs=not_configured,
        )

    fetch = _office_fetch()
    try:
        client = redis_client()
        now = int(client.time()[0])
        # Distinct facs: sibling fabs share one feed and must not double-fetch.
        distinct_facs = list(dict.fromkeys(fac for _fab, fac in configured))
        metas = [
            refresh.ensure_fresh(client, fac, now=now, fetch=fetch)
            for fac in distinct_facs
        ]
        return _build_board(
            client, index, tool_type,
            fab_names=list(fab_names),
            wanted_fabs={roster.norm(fab) for fab, _fac in configured},
            fac_ids=distinct_facs,
            not_configured_fabs=not_configured,
            now=now,
            meta=board.merged_meta(metas),
        )
    except STORE_ERRORS as exc:
        raise unreachable("live_alarm board is unreachable", exc) from exc
```

Update every existing test that calls `get_board(tool, "R3")` to `get_board(tool, ("R3",))` and payload assertions from `fab_name` to `fab_names`/`not_configured_fabs` (in `test_mock.py`, `test_contract.py`, `test_office_reader.py`).

- [ ] **Step 4: Run** — `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/live_alarm -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add back_dev_home/ebeam/hitachi/live_alarm
git commit -m "feat(live-alarm): board merges N fac feeds, stamps event fab, reports partial config"
```

---

### Task 6: Frontend — catalog API types + match plumbing

**Files:**
- Modify: `front-dev-home/app/composables/useRecipeSearchApi.ts` (types lines 6–20, `fetchRecipeList` lines 112–132)
- Modify: `front-dev-home/app/utils/recipeSearchMatch.ts` (`RecipeSearchResult` line 107, `toRecipeSearchResults` line 112)
- Test: `front-dev-home/app/utils/recipeSearchMatch.test.ts`

**Interfaces:**
- Consumes: `canonicalFabList(fabs)` from `~/utils/fab` (Phase 1).
- Produces:
  - `RecipeSearchRow { recipe_name: string, fab_name: string }`
  - `RecipeSearchResponse { tool_type, fab_names: string[], total: number, rows: RecipeSearchRow[] }`
  - `RecipeSearchParams { toolType, fabNames?: string[] }`; `fetchRecipeList` sends `fab_name=<join(',')>`
  - `RecipeSearchResult { recipe_name: string, fab_name: string, source: RecipeSearchSource }`
  - `toRecipeSearchResults(rows: Array<{recipe_name: string, fab_name: string}>, source)` — dedupe key is the `(fab, name)` pair
  - `fetchRecipeDetail` / `RecipeDetailParams` UNCHANGED (single owner fab)

- [ ] **Step 1: Write the failing tests** (`recipeSearchMatch.test.ts`, node:test style used in the file):

```ts
test('toRecipeSearchResults keeps both fab copies of a duplicate name', () => {
  const rows = [
    { recipe_name: 'A/B_1', fab_name: 'R3' },
    { recipe_name: 'A/B_1', fab_name: 'M16B' },
    { recipe_name: 'A/B_1', fab_name: 'R3' }
  ]
  const results = toRecipeSearchResults(rows, 'redis')
  assert.deepEqual(results, [
    { recipe_name: 'A/B_1', fab_name: 'R3', source: 'redis' },
    { recipe_name: 'A/B_1', fab_name: 'M16B', source: 'redis' }
  ])
})

test('toRecipeSearchResults blank fab is allowed (opensearch fallback)', () => {
  const results = toRecipeSearchResults([{ recipe_name: 'X', fab_name: '' }], 'opensearch')
  assert.deepEqual(results, [{ recipe_name: 'X', fab_name: '', source: 'opensearch' }])
})
```

- [ ] **Step 2: Run to verify failure** — `cd front-dev-home && npm test`

- [ ] **Step 3: Implement**

`useRecipeSearchApi.ts` types:

```ts
export interface RecipeSearchRow {
  recipe_name: string
  fab_name: string
}

export interface RecipeSearchResponse {
  tool_type: RecipeSearchToolType
  fab_names: string[]
  total: number
  rows: RecipeSearchRow[]
}

export interface RecipeSearchParams {
  toolType: RecipeSearchToolType
  fabNames?: string[]
}
```

`fetchRecipeList`:

```ts
  const fetchRecipeList = async (params: RecipeSearchParams): Promise<RecipeSearchResponse> => {
    const slug = TOOL_TO_BACKEND_SLUG[params.toolType]
    const fabKey = canonicalFabList(params.fabNames ?? []).join(',')
    const cacheKey = `${params.toolType}:${fabKey || 'ALL'}`
    const existing = inFlightRecipeLists.get(cacheKey)

    if (existing) {
      return await existing
    }

    const query = fabKey ? { fab_name: fabKey } : undefined
    // ... rest unchanged ...
  }
```

(import `canonicalFabList` from `~/utils/fab`; `normalizeFab` stays for `fetchRecipeDetail`.)

`recipeSearchMatch.ts`:

```ts
export interface RecipeSearchResult {
  recipe_name: string
  fab_name: string
  source: RecipeSearchSource
}

export const toRecipeSearchResults = (
  rows: Array<{ recipe_name: string, fab_name: string }>,
  source: RecipeSearchSource
): RecipeSearchResult[] => {
  const seen = new Set<string>()
  const results: RecipeSearchResult[] = []
  for (const row of rows) {
    const recipeName = row.recipe_name.trim()
    if (!recipeName) continue
    const fabName = (row.fab_name ?? '').trim().toUpperCase()
    const key = `${fabName} ${recipeName}`
    if (seen.has(key)) continue
    seen.add(key)
    results.push({ recipe_name: recipeName, fab_name: fabName, source })
  }
  return results
}
```

Update existing `toRecipeSearchResults` tests (they currently pass `string[]`).

- [ ] **Step 4: Run** — `npm test` → PASS (RecipeSearchView still compiles against old call shapes only at typecheck time; typecheck is deferred to Task 9 when the view is updated — do NOT run `npm run typecheck` in this task).

- [ ] **Step 5: Commit**

```bash
git add app/composables/useRecipeSearchApi.ts app/utils/recipeSearchMatch.ts app/utils/recipeSearchMatch.test.ts
git commit -m "feat(recipe-search): fab-tagged row types in catalog API and match utils"
```

---

### Task 7: Frontend — selection/recent v2 + compare API

**Files:**
- Modify: `front-dev-home/app/utils/recipeSelection.ts` (whole-file interface change)
- Modify: `front-dev-home/app/composables/useRecipeSelectionSet.ts`
- Modify: `front-dev-home/app/composables/useRecipeRecentSearches.ts`
- Modify: `front-dev-home/app/composables/useRecipeCompareApi.ts`
- Test: `front-dev-home/app/utils/recipeSelection.test.ts`

**Interfaces:**
- Produces:
  - `RecipeSelectionEntry { name: string, fab_name: string, source: RecipeSearchSource }`
  - `upsertRecipeSelection(entries, rawName, fabName, source)`, `removeRecipeSelection(entries, name, fabName)`
  - `promoteRecipeSelectionsToRedis(entries, rows: Array<{recipe_name, fab_name}>)` — opensearch entries adopt the first matching catalog row's fab and become redis, then re-normalize
  - `recipesForCompare(entries) -> Array<{recipe_name, fab_name}> | null` (REPLACES `recipeNamesForCompare`)
  - `useRecipeSelectionSet(toolType)` — fab arg GONE; storage key `skewnono:recipe-search.selection.v2.{toolType}`; exposes `has(name, fabName)`, `add(name, fabName, source?)`, `remove(name, fabName)`, `toggle(name, fabName, source?)`, `sourceOf(name, fabName)`, plus unchanged `entries/selected/capabilities/count/clear/promoteRedis`
  - `useRecipeRecentSearches(toolType)` — fab arg GONE; key `skewnono:recipe-search.recent.v2.{toolType}`
  - `useRecipeCompareApi`: `RecipeCompareParams { toolType, recipes: Array<{recipe_name, fab_name}> }`, body `{ recipes }`, `RecipeCompareResponse.fab_names: string[]`

- [ ] **Step 1: Write the failing tests** (`recipeSelection.test.ts` — update existing cases to the new signatures and add):

```ts
test('same name in two fabs are two distinct selections', () => {
  let entries: RecipeSelectionEntry[] = []
  entries = upsertRecipeSelection(entries, 'A/B_1', 'R3', 'redis')
  entries = upsertRecipeSelection(entries, 'A/B_1', 'M16B', 'redis')
  assert.equal(entries.length, 2)
  entries = removeRecipeSelection(entries, 'A/B_1', 'R3')
  assert.deepEqual(entries, [{ name: 'A/B_1', fab_name: 'M16B', source: 'redis' }])
})

test('promotion adopts the catalog row fab and dedupes', () => {
  const entries: RecipeSelectionEntry[] = [
    { name: 'X', fab_name: '', source: 'opensearch' },
    { name: 'X', fab_name: 'R3', source: 'redis' }
  ]
  const next = promoteRecipeSelectionsToRedis(entries, [{ recipe_name: 'X', fab_name: 'R3' }])
  assert.deepEqual(next, [{ name: 'X', fab_name: 'R3', source: 'redis' }])
})

test('recipesForCompare returns (name, fab) pairs', () => {
  const entries: RecipeSelectionEntry[] = [
    { name: 'A', fab_name: 'R3', source: 'redis' },
    { name: 'A', fab_name: 'M16B', source: 'redis' }
  ]
  assert.deepEqual(recipesForCompare(entries), [
    { recipe_name: 'A', fab_name: 'R3' },
    { recipe_name: 'A', fab_name: 'M16B' }
  ])
})
```

- [ ] **Step 2: Run to verify failure** — `npm test`

- [ ] **Step 3: Implement**

`recipeSelection.ts` — key points (rewrite the file keeping the same exported surface plus changes):

```ts
export interface RecipeSelectionEntry {
  name: string
  fab_name: string
  source: RecipeSearchSource
}

const entryKey = (name: string, fabName: string) => `${fabName} ${name}`
```

- `toEntry`: object form requires `name`; `fab_name` is a string defaulting to `''` (`typeof candidate.fab_name === 'string' ? candidate.fab_name.trim().toUpperCase() : ''`); legacy bare-string values become `{ name, fab_name: '', source: 'redis' }`.
- `normalizeRecipeSelectionEntries`: dedupe by `entryKey`, prefer `source === 'redis'` on collision (same rule as today).
- `upsertRecipeSelection(entries, rawName, fabName, source)`: match on `entryKey(name, fab)`; same redis-wins update rule.
- `removeRecipeSelection(entries, name, fabName)`: filter by key.
- `promoteRecipeSelectionsToRedis(entries, rows)`: build `fabByName` map (first row wins per name); opensearch entries whose name is in the map become `{ ...entry, fab_name: map.get(name), source: 'redis' }`; if anything changed return `normalizeRecipeSelectionEntries(next)` else `entries`.
- `recipesForCompare(entries)`: gate on `canCompareRecipeSelection` (unchanged), map to `{ recipe_name: entry.name, fab_name: entry.fab_name }`. Delete `recipeNamesForCompare`.
- `capabilitiesForRecipeSelection` / `canCompareRecipeSelection`: unchanged.

`useRecipeSelectionSet.ts`:

```ts
const storageKey = (toolType: string) =>
  `skewnono:recipe-search.selection.v2.${toolType}`

export const useRecipeSelectionSet = (toolType: RecipeSearchToolType) => {
  const entries = usePersistedState<RecipeSelectionEntry[]>(
    `recipe-search:selection:v2:${toolType}`,
    storageKey(toolType),
    { default: () => [], normalize: normalizeRecipeSelectionEntries }
  )

  const selected = computed(() => entries.value.map(entry => entry.name))
  const capabilities = computed(() => capabilitiesForRecipeSelection(entries.value))
  const has = (name: string, fabName: string) =>
    entries.value.some(entry => entry.name === name && entry.fab_name === fabName)
  const sourceOf = (name: string, fabName: string): RecipeSearchSource =>
    entries.value.find(entry => entry.name === name && entry.fab_name === fabName)?.source ?? 'redis'

  const add = (name: string, fabName: string, source: RecipeSearchSource = 'redis') => {
    entries.value = upsertRecipeSelection(entries.value, name, fabName, source)
  }
  const remove = (name: string, fabName: string) => {
    entries.value = removeRecipeSelection(entries.value, name, fabName)
  }
  const toggle = (name: string, fabName: string, source: RecipeSearchSource = 'redis') => {
    if (has(name, fabName)) remove(name, fabName)
    else add(name, fabName, source)
  }
  // clear / promoteRedis / count unchanged in shape; promoteRedis now takes rows:
  const promoteRedis = (rows: Array<{ recipe_name: string, fab_name: string }>) => {
    entries.value = promoteRecipeSelectionsToRedis(entries.value, rows)
  }
  // ... same return object ...
}
```

`useRecipeRecentSearches.ts`: signature `(toolType: RecipeSearchToolType)`; `storageKey = (toolType: string) => \`skewnono:recipe-search.recent.v2.${toolType}\``; scope `recipe-search:recent:v2:${toolType}`; body otherwise unchanged. Update the header comment (per-toolType now — search terms are fab-agnostic).

`useRecipeCompareApi.ts`:

```ts
export interface CompareRecipeRef {
  recipe_name: string
  fab_name: string
}

export interface RecipeCompareResponse {
  tool_type: RecipeSearchToolType
  fab_names: string[]
  recipes: CompareRecipe[]
}

export interface RecipeCompareParams {
  toolType: RecipeSearchToolType
  recipes: CompareRecipeRef[]
}
```

`fetchCompare`: drop `normalizeFab`; `const refs = params.recipes.filter(r => r.recipe_name.trim())`; cache key ``const cacheKey = `${params.toolType}:${refs.map(r => `${r.fab_name}:${r.recipe_name}`).sort().join('|')}` ``; body `{ recipes: refs }`.

- [ ] **Step 4: Run** — `npm test` → PASS.

- [ ] **Step 5: Commit**

```bash
git add app/utils/recipeSelection.ts app/utils/recipeSelection.test.ts app/composables/useRecipeSelectionSet.ts app/composables/useRecipeRecentSearches.ts app/composables/useRecipeCompareApi.ts
git commit -m "feat(recipe-search): (name, fab) selection identity, v2 storage keys, per-recipe compare body"
```

---

### Task 8: Frontend — detail route builder, RowActions fab picker, ranking views

**Files:**
- Modify: `front-dev-home/app/utils/recipeView.ts` (`recipeDetailRoute` line 150, `buildRecipeDetailNavItems` line 181; add `readRecipeOwnerFabQuery`)
- Modify: `front-dev-home/app/components/ebeam/RecipeRowActions.vue`
- Modify: `front-dev-home/app/components/ebeam/RecipeDetailNav.vue` (prop rename `fab` → `fabSegment`, new `ownerFab`)
- Modify: `front-dev-home/app/components/ebeam/RecipeTatView.vue` (primaryFab downgrade ~line 311, RowActions usage ~line 243)
- Modify: `front-dev-home/app/components/ebeam/FailIssueView.vue` (same, ~lines 300/232/255)
- Modify: `front-dev-home/app/composables/useRecipeTatApi.ts` + `useFailIssueApi.ts` (ranking row interfaces gain `fab_names: string[]`)
- Modify: `front-dev-home/app/components/ebeam/skewvoir/workspace/LeftRail.vue` (line 270 — pass ownerFab explicitly)
- Test: `front-dev-home/app/utils/recipeView.test.ts`, `front-dev-home/app/utils/recipeDetailNavigation.test.ts`

**Interfaces:**
- Consumes: `buildFabSegment(fabs)` from `~/utils/fab`; Task 3/4's `fab_names` on ranking rows.
- Produces:
  - `recipeDetailRoute(toolType, fabSegment, screen, recipeName, source = 'redis', ownerFab = '')` — path keeps the (possibly comma) segment; `ownerFab` (uppercased) rides as `query.fab_name` when non-empty
  - `buildRecipeDetailNavItems(toolType, fabSegment, recipeName, activeScreen, setFlag, source = 'redis', ownerFab = '')`
  - `readRecipeOwnerFabQuery(route): string` (`''` when absent)
  - `RecipeRowActions` props: `{ toolType: string, fabSegment: string, fabNames: string[], recipeName: string }` — one contributing fab links directly; 2+ opens a per-fab dropdown

- [ ] **Step 1: Write the failing tests** (`recipeView.test.ts`):

```ts
test('recipeDetailRoute keeps the multi-fab segment and carries the owner fab', () => {
  const route = recipeDetailRoute('cd-sem', 'R3,M16B', 'open', 'A/B_1', 'redis', 'M16B')
  assert.equal(route.path, '/ebeam/cd-sem/r3,m16b/recipe-search/open')
  assert.equal(route.query.fab_name, 'M16B')
  assert.equal(route.query.recipe_name, 'A/B_1')
})

test('recipeDetailRoute omits fab_name when no owner is given', () => {
  const route = recipeDetailRoute('cd-sem', 'r3', 'lateral', 'A/B_1')
  assert.equal('fab_name' in route.query, false)
})
```

- [ ] **Step 2: Run to verify failure** — `npm test`

- [ ] **Step 3: Implement**

`recipeView.ts`:

```ts
export const recipeDetailRoute = (
  toolType: string,
  fabSegment: string,
  screen: RecipeDetailScreen,
  recipeName: string,
  source: RecipeSearchSource = 'redis',
  ownerFab = ''
) => {
  if (!isRecipeDetailScreenSupported(screen, source)) {
    throw new RangeError('OpenSearch recipes do not support the open detail view')
  }
  return {
    path: `/ebeam/${toolType}/${fabSegment.toLowerCase()}/recipe-search/${screen}`,
    query: {
      recipe_name: recipeName,
      ...(ownerFab ? { fab_name: ownerFab.toUpperCase() } : {}),
      ...(source === 'opensearch' ? { source } : {})
    }
  }
}
```

`buildRecipeDetailNavItems` gains the trailing `ownerFab = ''` param and passes it through to `recipeDetailRoute`. Add:

```ts
export const readRecipeOwnerFabQuery = (route: RouteLocationNormalizedLoaded): string => {
  const raw = route.query.fab_name
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' ? value.trim().toUpperCase() : ''
}
```

`RecipeRowActions.vue` — full replacement:

```vue
<template>
  <div class="flex items-center gap-2">
    <template
      v-for="action in RECIPE_ROW_ACTIONS"
      :key="action.screen"
    >
      <UDropdownMenu
        v-if="multiFab"
        :items="itemsFor(action.screen)"
      >
        <UTooltip :text="`${action.label} — FAB 선택`">
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            class="-my-1"
            :icon="action.icon"
            :aria-label="`${recipeName} ${action.label}`"
          />
        </UTooltip>
      </UDropdownMenu>
      <UTooltip
        v-else
        :text="action.label"
      >
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          class="-my-1"
          :icon="action.icon"
          :aria-label="`${recipeName} ${action.label}`"
          @click="open(action.screen, fabNames[0] ?? '')"
        />
      </UTooltip>
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  RECIPE_ROW_ACTIONS,
  recipeDetailRoute,
  type RecipeDetailScreen
} from '~/utils/recipeView'

// Compact icon-only variant of the recipe-search row buttons, for dense
// ranking tables (recipe-tat, fail-issue). Ranking rows aggregate across the
// selected fabs, so when more than one fab contributed the action opens a
// per-fab picker — the detail registries are per-fab.
const props = defineProps<{
  toolType: string
  fabSegment: string
  fabNames: string[]
  recipeName: string
}>()

const router = useRouter()
const multiFab = computed(() => props.fabNames.length > 1)

const open = (screen: RecipeDetailScreen, ownerFab: string) => {
  router.push(recipeDetailRoute(
    props.toolType, props.fabSegment, screen, props.recipeName, 'redis', ownerFab
  ))
}

const itemsFor = (screen: RecipeDetailScreen) =>
  props.fabNames.map(fab => ({ label: fab, onSelect: () => open(screen, fab) }))
</script>
```

`RecipeDetailNav.vue`: rename prop `fab` → `fabSegment`, add `ownerFab: string` prop, forward both into `buildRecipeDetailNavItems` in its new positions. Update `recipeDetailNavigation.test.ts` accordingly.

`RecipeTatView.vue` / `FailIssueView.vue`:
- delete the `primaryFab` computed and its "single-fab registry until Phase B" comment;
- add `const fabSegment = computed(() => buildFabSegment(props.fabs))` (import from `~/utils/fab`);
- every `<EbeamRecipeRowActions ... :fab="primaryFab" ...>` becomes `:fab-segment="fabSegment" :fab-names="row.fab_names ?? []"` (row = the ranking row in that table's cell scope).

`useRecipeTatApi.ts` / `useFailIssueApi.ts`: add `fab_names: string[]` to the ranking-row interfaces (`RankingRow` / `AlignRankingRow` / `MeasRankingRow` — match the existing interface names in those files).

`LeftRail.vue` line 270: `recipeDetailRoute(props.ws.toolType, props.fab, 'open', recipe, 'redis', props.fab)` — its single fab is both segment and owner.

- [ ] **Step 4: Run** — `npm test` → PASS. Do NOT run `npm run typecheck` yet: `RecipeSearchView.vue` / `RecipeCompareView.vue` still consume the pre-Phase-B signatures until Tasks 9–10 and would fail typecheck by design. The full typecheck gate runs in Task 9.

- [ ] **Step 5: Commit**

```bash
git add app/utils/recipeView.ts app/utils/recipeView.test.ts app/utils/recipeDetailNavigation.test.ts app/components/ebeam/RecipeRowActions.vue app/components/ebeam/RecipeDetailNav.vue app/components/ebeam/RecipeTatView.vue app/components/ebeam/FailIssueView.vue app/composables/useRecipeTatApi.ts app/composables/useFailIssueApi.ts app/components/ebeam/skewvoir/workspace/LeftRail.vue
git commit -m "feat(recipe-search): owner-fab detail routing + per-fab picker in ranking row actions"
```

---

### Task 9: Frontend — RecipeSearchView multi-fab + index pages

**Files:**
- Modify: `front-dev-home/app/components/ebeam/RecipeSearchView.vue`
- Modify: `front-dev-home/app/pages/ebeam/cd-sem/[fab]/recipe-search/index.vue`
- Modify: `front-dev-home/app/pages/ebeam/hv-sem/[fab]/recipe-search/index.vue`

**Interfaces:**
- Consumes: Tasks 6–8 (`fetchRecipeList({toolType, fabNames})`, `toRecipeSearchResults(rows, source)`, `useRecipeSelectionSet(toolType)`, `useRecipeRecentSearches(toolType)`, `recipeDetailRoute(..., ownerFab)`, `buildFabSegment`).
- Produces: `RecipeSearchView` props `{ fabs: string[], toolLabel: string, toolType: RecipeSearchToolType }` (the `fab: Fab` prop is GONE).

- [ ] **Step 1: Update `RecipeSearchView.vue`** — every `props.fab` usage:

```ts
const props = defineProps<{
  fabs: string[]
  toolLabel: string
  toolType: RecipeSearchToolType
}>()

const fabsKey = computed(() => props.fabs.join(','))
const multiFab = computed(() => props.fabs.length > 1)
const fabSegment = computed(() => buildFabSegment(props.fabs))
```

(import `buildFabSegment` from `~/utils/fab`; drop the now-unused `Fab` type import if nothing else uses it.)

- `useRecipeRecentSearches(props.toolType)` (line 34)
- `cacheKey`: `` `recipe-search:${props.toolType}:${fabsKey.value || 'ALL'}` `` (line 56)
- `emptyResponse`: `{ tool_type: props.toolType, fab_names: [...props.fabs], total: 0, rows: [] }` (line 58)
- fetch: `fetchRecipeList({ toolType: props.toolType, fabNames: props.fabs })` (line 67)
- Rename `recipeNames` → `recipeRows` (line 75; it now holds `RecipeSearchRow[]`)
- `searchableRows`: `recipeRows.value.map(row => ({ value: row, searchText: row.recipe_name.trim().toLowerCase() }))` (line 83)
- `redisMatchedNames` → `redisMatchedRows` (`rankRecipeMatches` returns the row objects now); the `watch(redisMatchedNames, ...)` at line 255 watches `redisMatchedRows` (only `.length` is read — no other change)
- `redisResults`: `toRecipeSearchResults(redisMatchedRows.value, 'redis')`
- `fallbackResults`: `toRecipeSearchResults(historyMatches.value.map(name => ({ recipe_name: name, fab_name: '' })), 'opensearch')` — fallback names have no owner fab (the meas-hist snapshot is names-only); their badge stays hidden and detail routing falls back to the primary fab
- `identity`: `` `${props.toolLabel} · ${props.fabs.join(' + ') || '—'}` `` (line 146)
- `fallbackScopeKey`: `` `${props.toolType}:${fabsKey.value || 'ALL'}:${normalizedQuery.value}` `` (line 220)
- probe call: `fab: props.fabs.length ? [...props.fabs] : undefined` (line 280)
- `recipeSubpath`: `` `/ebeam/${props.toolType}/${fabSegment.value}/recipe-search/${subpath}` `` (line 376)
- route builders now take the row (they need its fab):

```ts
const getRecipeDetailRoute = (row: RecipeSearchResult) =>
  recipeDetailRoute(props.toolType, fabSegment.value, 'open', row.recipe_name, row.source, row.fab_name)
const getLateralRoute = (row: RecipeSearchResult) =>
  recipeDetailRoute(props.toolType, fabSegment.value, 'lateral', row.recipe_name, row.source, row.fab_name)
const getMeasHistRoute = (row: RecipeSearchResult) =>
  recipeDetailRoute(props.toolType, fabSegment.value, 'meas-hist', row.recipe_name, row.source, row.fab_name)
```

- selection: `useRecipeSelectionSet(props.toolType)`; `watch(recipeRows, rows => promoteRedis(rows), { immediate: true })`
- `togglePageSelection` / checkbox templates: `has(row.recipe_name, row.fab_name)` / `toggle(row.recipe_name, row.fab_name, row.source)` (template lines 749–761 pass `row.original.*`)
- `openSet*` handlers: entries carry `fab_name` — e.g. `getRecipeDetailRoute({ recipe_name: first.name, fab_name: first.fab_name, source: first.source })`; `openRecipeDetail/openLateral/openMeasHist(row)` already receive the full row — just pass `row` through to the new builders
- Fab badge in the `#recipe_name-cell` template (before the OpenSearch chip):

```vue
                  <span
                    v-if="multiFab && row.original.fab_name"
                    class="inline-flex items-center rounded bg-zinc-100 px-1.5 py-0.5 font-sans text-[9px] font-semibold text-zinc-600 dark:bg-zinc-500/15 dark:text-zinc-300"
                  >
                    {{ row.original.fab_name }}
                  </span>
```

- [ ] **Step 2: Update both index pages** — full content (hv-sem swaps `cd-sem`→`hv-sem`, `CD-SEM`→`HV-SEM`):

```vue
<script setup lang="ts">
const { fabs } = useFabRoute('cd-sem')
</script>

<template>
  <AppAsyncBoundary title="Recipe 목록을 불러오는 중입니다.">
    <EbeamRecipeSearchView
      :fabs="fabs"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </AppAsyncBoundary>
</template>
```

(NavFabScopeNotice and the wrapper div are gone; the boundary is the single root.)

- [ ] **Step 3: Verify** — `npm test && npm run typecheck && npm run lint` from `front-dev-home/`. Typecheck is the gate here: it must be clean for every file touched in Tasks 6–9.

- [ ] **Step 4: Commit**

```bash
git add app/components/ebeam/RecipeSearchView.vue app/pages/ebeam/cd-sem/\[fab\]/recipe-search/index.vue app/pages/ebeam/hv-sem/\[fab\]/recipe-search/index.vue
git commit -m "feat(recipe-search): multi-fab catalog with per-row fab badges"
```

---

### Task 10: Frontend — compare/detail views, detail pages, RecipeSwitcher

**Files:**
- Modify: `front-dev-home/app/components/ebeam/RecipeCompareView.vue`
- Modify: `front-dev-home/app/components/ebeam/RecipeOpenView.vue`, `RecipeLateralView.vue`, `RecipeMeasHistView.vue` (backRoute + RecipeDetailNav usage only)
- Modify: `front-dev-home/app/components/ebeam/RecipeSwitcher.vue`
- Modify: 8 pages — `pages/ebeam/{cd-sem,hv-sem}/[fab]/recipe-search/{compare,open,lateral,meas-hist}.vue`

**Interfaces:**
- Consumes: `recipesForCompare(entries)`, `fetchCompare({toolType, recipes})`, `useRecipeSelectionSet(toolType)`, `readRecipeOwnerFabQuery(route)`, `buildFabSegment`.
- Produces: `RecipeCompareView` props `{ fabs: string[], toolLabel, toolType }`. Detail views KEEP `fab: Fab` (it now means the owning fab).

- [ ] **Step 1: `RecipeCompareView.vue`**

- props: `fabs: string[]` (replace `fab: Fab`); `const fabSegment = computed(() => buildFabSegment(props.fabs))`
- `useRecipeSelectionSet(props.toolType)`
- `backRoute`: `` `/ebeam/${props.toolType}/${fabSegment.value}/recipe-search` ``
- `const compareRecipes = computed(() => recipesForCompare(entries.value))` (replaces `compareNames`); `compareAllowed = computed(() => compareRecipes.value !== null)`
- `cacheKey`: `` refs ? `recipe-compare:${props.toolType}:${refs.map(r => `${r.fab_name}:${r.recipe_name}`).sort().join('|')}` : `recipe-compare:unsupported:${props.toolType}` `` (where `refs = compareRecipes.value`)
- fetch: `fetchCompare({ toolType: props.toolType, recipes: refs })`
- any identity/eyebrow using `props.fab` → `props.fabs.join(' + ')`; export filename (~line 371) → `props.fabs.join('+').toLowerCase()`
- `remove(name)` call sites gain the entry's fab: `remove(entry.name, entry.fab_name)` (the selected-chips list iterates entries)
- Per-recipe fab chip: in the template's per-recipe column header (search for where `recipe.recipe_id` renders), add after the id:

```vue
            <span
              v-if="(data?.fab_names.length ?? 0) > 1"
              class="inline-flex items-center rounded bg-zinc-100 px-1.5 py-0.5 font-sans text-[9px] font-semibold text-zinc-600 dark:bg-zinc-500/15 dark:text-zinc-300"
            >
              {{ recipe.fab_name }}
            </span>
```

- [ ] **Step 2: Detail views (Open/Lateral/MeasHist)** — three small edits each:

1. `backRoute` must NOT collapse to the owner fab (it would clobber the sidebar selection). Replace:

```ts
const routeFabSegment = computed(() => String(route.params.fab || props.fab.toLowerCase()))
const backRoute = computed(() => `/ebeam/${props.toolType}/${routeFabSegment.value}/recipe-search`)
```

(`RecipeOpenView.vue:270`, `RecipeLateralView.vue` back link ~line 142, `RecipeMeasHistView.vue` back link ~line 197 — MeasHist/Lateral build the link in the template; give them the same `routeFabSegment` computed.)

2. Wherever the view renders `RecipeDetailNav` / `RecipeSwitcher`, pass `:fab-segment="routeFabSegment"` and `:owner-fab="props.fab"` per Task 8's new props.

3. Everything else (cacheKey, fetches with `fabName: props.fab`, xlsx `fabName: props.fab`) stays — `props.fab` IS the owner fab now.

- [ ] **Step 3: `RecipeSwitcher.vue`** — `useRecipeSelectionSet(props.toolType)` (drop the fab arg, line 36); when it builds per-entry routes, use each entry's own `fab_name` as `ownerFab` with the current route's segment (mirror Step 2's `routeFabSegment` pattern; read its existing code for the exact call sites).

- [ ] **Step 4: The 8 pages** — compare pages get `:fabs` (root = boundary, notice gone):

```vue
<script setup lang="ts">
const { fabs } = useFabRoute('cd-sem')
</script>

<template>
  <AppAsyncBoundary title="Recipe 비교 화면을 불러오는 중입니다.">
    <EbeamRecipeCompareView
      :fabs="fabs"
      tool-label="CD-SEM"
      tool-type="cd-sem"
    />
  </AppAsyncBoundary>
</template>
```

(Keep each compare page's existing boundary `title` text if it differs — only the props/notice change.)

The 6 detail pages (open/lateral/meas-hist × 2 tools) resolve the owner:

```vue
<script setup lang="ts">
import { readRecipeOwnerFabQuery } from '~/utils/recipeView'

const { primaryFab } = useFabRoute('cd-sem')
const route = useRoute()
const ownerFab = computed(() => readRecipeOwnerFabQuery(route) || primaryFab.value)
</script>

<template>
  <div class="flex h-full min-h-0 flex-col gap-3">
    <AppAsyncBoundary title="Recipe 내용을 불러오는 중입니다.">
      <EbeamRecipeOpenView
        :fab="ownerFab"
        tool-label="CD-SEM"
        tool-type="cd-sem"
      />
    </AppAsyncBoundary>
  </div>
</template>
```

Substitutions per page: view component (`EbeamRecipeOpenView`/`EbeamRecipeLateralView`/`EbeamRecipeMeasHistView`), boundary title (keep each page's current title text), tool label/type (`CD-SEM`/`cd-sem` vs `HV-SEM`/`hv-sem`). **Keep each page's existing wrapper element**: open pages use the `flex h-full min-h-0 flex-col gap-3` div (height-load-bearing — do not remove); lateral/meas-hist pages keep whatever wrapper they have today minus the notice (if the notice was the only sibling, collapse to the boundary as root).

- [ ] **Step 5: Verify** — `npm test && npm run typecheck && npm run lint` → all clean.

- [ ] **Step 6: Commit**

```bash
git add app/components/ebeam/RecipeCompareView.vue app/components/ebeam/RecipeOpenView.vue app/components/ebeam/RecipeLateralView.vue app/components/ebeam/RecipeMeasHistView.vue app/components/ebeam/RecipeSwitcher.vue app/pages/ebeam/cd-sem/\[fab\]/recipe-search app/pages/ebeam/hv-sem/\[fab\]/recipe-search
git commit -m "feat(recipe-search): owner-fab detail screens, cross-fab compare with fab chips"
```

---

### Task 11: Frontend — live-alarm multi-fab

**Files:**
- Modify: `front-dev-home/app/utils/liveAlarm.ts` (`LiveAlarmEvent` line 9, `LiveAlarmPayload` line 36)
- Modify: `front-dev-home/app/composables/useLiveAlarmFeed.ts`
- Modify: `front-dev-home/app/components/ebeam/LiveAlarmView.vue`
- Modify: `front-dev-home/app/components/live-alarm/AlarmRow.vue`, `front-dev-home/app/components/live-alarm/MeasGroup.vue`
- Modify: `front-dev-home/app/pages/ebeam/cd-sem/[fab]/live-alarm.vue`, `.../hv-sem/[fab]/live-alarm.vue`
- Test: `front-dev-home/app/composables/useLiveAlarmFeed.test.ts`, `front-dev-home/app/utils/liveAlarm.test.ts`

**Interfaces:**
- Consumes: Task 5's payload (`fab_names`, `not_configured_fabs`, `events[].fab_name`); `buildFabSegment`.
- Produces:
  - `LiveAlarmEvent` + `fab_name: string`; `LiveAlarmPayload`: `fab_name` → `fab_names: string[]`, + `not_configured_fabs: string[]`
  - `useLiveAlarmFeed(toolSlug: string, fabNames: string[])` — one request with `fab_name=<join(',')>`, state key `live-alarm:{toolSlug}:{join(',')}`, new `notConfiguredFabs` computed
  - `LiveAlarmView` props `{ fabs: string[], toolLabel, toolType }`
  - `AlarmRow` / `MeasGroup` new optional prop `fabBadge?: string` (chip rendered when non-empty)

- [ ] **Step 1: Write the failing test** (`useLiveAlarmFeed.test.ts` tests `applyPoll` — extend a payload fixture):

```ts
test('applyPoll carries not_configured_fabs and per-event fab', () => {
  const payload = makePayload({
    fab_names: ['R3', 'M16B'],
    not_configured_fabs: ['M16B'],
    events: [makeEvent({ id: 'a', fab_name: 'R3' })]
  })
  const state = applyPoll({}, payload, 0)
  assert.deepEqual(state.notConfiguredFabs, ['M16B'])
  assert.equal(state.events[0]?.fab_name, 'R3')
})
```

(Adapt `makePayload`/`makeEvent` to the fixture helpers the file already has; update existing fixtures from `fab_name: 'R3'` to `fab_names: ['R3'], not_configured_fabs: []`.)

- [ ] **Step 2: Run to verify failure** — `npm test`

- [ ] **Step 3: Implement**

`utils/liveAlarm.ts`: add `fab_name: string` to `LiveAlarmEvent`; in `LiveAlarmPayload` replace `fab_name: string` with `fab_names: string[]` and add `not_configured_fabs: string[]`.

`useLiveAlarmFeed.ts`:

```ts
export const useLiveAlarmFeed = (toolSlug: string, fabNames: string[]) => {
  const fabsKey = fabNames.join(',')
  const key = `live-alarm:${toolSlug}:${fabsKey}`
```

- `FeedState` + `notConfiguredFabs: string[]` (default `[]` in the initial state); `applyPoll` sets `notConfiguredFabs: payload.not_configured_fabs`
- poll params: `{ fab_name: fabsKey }`
- return adds `notConfiguredFabs: computed(() => state.value.notConfiguredFabs)`

`LiveAlarmView.vue`:

- props `{ fabs: string[], toolLabel: string, toolType: string }`
- `const fabSegment = computed(() => buildFabSegment(props.fabs))` replaces `fabSlug`; `const multiFab = computed(() => props.fabs.length > 1)`
- `useLiveAlarmFeed(props.toolType, props.fabs)` + destructure `notConfiguredFabs`
- identity/eyebrow (search `toolLabel` in the template/script, ~line 78): `` `${props.toolLabel} · ${props.fabs.join(' + ')}` ``
- `not_configured` sentence (template line ~193): `{{ fabs.join(' + ') }} 팹은 아직 라이브 알람 수집 대상이 아닙니다.`
- rows: `:fab="fabSegment"` (link segment keeps the multi selection) and `:fab-badge="multiFab ? event.fab_name : ''"`; meas groups: `:fab="fabSegment"` `:fab-badge="multiFab ? (group.events[0]?.fab_name ?? '') : ''"`
- partial-config footnote, next to the unmatched-count paragraph (~line 236):

```vue
    <p
      v-if="notConfiguredFabs.length"
      class="sk-meta"
    >
      {{ notConfiguredFabs.join(', ') }} 팹은 아직 라이브 알람 수집 대상이
      아니라 이 보드에 포함되지 않습니다.
    </p>
```

`AlarmRow.vue`: add `fabBadge?: string` to props; render next to the row's leading identity (eqp/alarm label — read the template and place beside `eqp_id`):

```vue
    <span
      v-if="fabBadge"
      class="inline-flex items-center rounded bg-zinc-100 px-1.5 py-0.5 font-sans text-[9px] font-semibold text-zinc-600 dark:bg-zinc-500/15 dark:text-zinc-300"
    >
      {{ fabBadge }}
    </span>
```

`MeasGroup.vue`: add `fabBadge?: string`; render the same chip in the group header; keep forwarding `:fab="fab"` to inner rows and forward `:fab-badge="fabBadge"` too (a meas group is one eqp = one fab).

Both pages (hv-sem swaps labels):

```vue
<script setup lang="ts">
// Nuxt reuses this page component across fab param changes by default (R3 ->
// M11 does not remount), which would leave useLiveAlarmFeed polling the fab
// it was first created with. Keying on the full path forces a remount, and
// therefore a fresh feed, whenever the fab segment changes.
definePageMeta({ key: route => route.fullPath })

const { fabs } = useFabRoute('cd-sem')
</script>

<template>
  <EbeamLiveAlarmView
    :fabs="fabs"
    tool-label="CD-SEM"
    tool-type="cd-sem"
  />
</template>
```

- [ ] **Step 4: Verify** — `npm test && npm run typecheck && npm run lint` → clean.

- [ ] **Step 5: Commit**

```bash
git add app/utils/liveAlarm.ts app/utils/liveAlarm.test.ts app/composables/useLiveAlarmFeed.ts app/composables/useLiveAlarmFeed.test.ts app/components/ebeam/LiveAlarmView.vue app/components/live-alarm/AlarmRow.vue app/components/live-alarm/MeasGroup.vue app/pages/ebeam/cd-sem/\[fab\]/live-alarm.vue app/pages/ebeam/hv-sem/\[fab\]/live-alarm.vue
git commit -m "feat(live-alarm): merged multi-fab board with per-row fab badges"
```

---

### Task 12: Docs, conveyance notes, full suites

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/recipe_search/MIGRATION.md`, `back_dev_home/ebeam/hitachi/live_alarm/MIGRATION.md`, `back_dev_home/ebeam/hitachi/recipe_tat/MIGRATION.md`, `back_dev_home/ebeam/hitachi/fail_issue/MIGRATION.md`
- Modify: `docs/superpowers/specs/2026-08-07-multi-fab-phase-b-design.md` (section 10)

**Interfaces:** none — documentation of Tasks 1–5's signatures.

- [ ] **Step 1: MIGRATION.md updates** (Korean, formal endings, MD060 compact tables):

- `recipe_search/MIGRATION.md`: catalog returns `(recipe, fab)` rows (`get_recipe_catalog(tool_type, fab_names)`); the all-fab `HGETALL` path tags by hash field; compare takes `recipes: [{recipe_name, fab_name}]`; office에서는 `office.py` 재복사 필요.
- `live_alarm/MIGRATION.md`: `get_board(tool_type, fab_names)`; distinct-fac merge (fac당 20초 1회 상한 유지, K개 fac = K배); `AlarmEvent.fab_name`은 reader stamping (ZSET member에는 없음); `merged_meta` worst-of 의미론; 재복사 필요.
- `recipe_tat/MIGRATION.md` + `fail_issue/MIGRATION.md`: ranking 행 `fab_names` sub-agg (`terms` on `fab_name.keyword`, size 16, recipe 레벨) — office_example이 바뀌었으므로 재복사 필요.
- Spec section 10: replace the "국한되면 불필요합니다" hedge — ranking aggregation lives in each provider, so **recipe_search, live_alarm, recipe_tat, fail_issue 네 feature 모두** 같은 office 배포에서 `office.py` 재복사가 필요합니다 (부팅 로그의 `STALE office.py` 표시가 재확인 수단).

- [ ] **Step 2: Run everything**

```bash
npm run lint:md
.venv/bin/python -m pytest -q
cd front-dev-home && npm test && npm run typecheck && npm run lint
```

Expected: all clean (~2740+ backend, ~1220+ frontend).

- [ ] **Step 3: Commit**

```bash
git add back_dev_home/ebeam/hitachi/recipe_search/MIGRATION.md back_dev_home/ebeam/hitachi/live_alarm/MIGRATION.md back_dev_home/ebeam/hitachi/recipe_tat/MIGRATION.md back_dev_home/ebeam/hitachi/fail_issue/MIGRATION.md docs/superpowers/specs/2026-08-07-multi-fab-phase-b-design.md
git commit -m "docs(multi-fab): Phase B MIGRATION notes — four office.py copies need re-cp"
```

---

## Post-plan verification (controller, after merge)

Not a task for an implementer subagent — the controller drives Playwright MCP per the `verify` skill after the branch merges:

1. `/ebeam/cd-sem/r3,m16b/recipe-search` — duplicate name shows two rows with different badges; single-fab URL hides badges.
2. Click an M16B row's 열어 보기 — detail opens with `?fab_name=M16B`, header shows M16B data, back button returns to the comma URL.
3. Select the same name in both fabs → compare shows two columns with distinct fab chips and different parameter tables.
4. recipe-status ranking row with 2 contributing fabs → action opens the fab picker.
5. `/ebeam/cd-sem/r3,m16b/live-alarm` — merged board with badges; `r3` alone — no badges; a fab with no tools listed in the footnote.
6. NavFabScopeNotice remains ONLY on skew-check and pm-planning.
