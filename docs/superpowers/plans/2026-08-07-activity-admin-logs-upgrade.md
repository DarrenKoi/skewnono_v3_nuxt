# Activity · Admin Logs Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/admin/logs` usable for error triage (one-click 4XX/5XX, names beside employee numbers) and make `/activity` say what it means (recent-first user table, a feature ranking with no unexplained entries).

**Architecture:** Six independent changes against the spec at `docs/superpowers/specs/2026-08-07-activity-admin-logs-upgrade-design.md`. Tasks 1–2 change the page-view slug vocabulary and MUST move backend, frontend and the shared fixture together — that fixture is read by a pytest contract test and a node test, and they disagree the moment one side lands alone. Tasks 3–4 are frontend-only. Task 5 adds a directory join in the Flask route. Task 6 is frontend-only.

**Tech Stack:** Flask blueprints + TypedDict contracts (CPython 3.14, `.venv`), Nuxt 4 + NuxtUI SPA, `node --test` for pure TS functions, pytest for the backend.

## Global Constraints

- **Work in a git worktree.** This touches ~12 files across both trees. Per `CLAUDE.md`, create `git worktree add ../skewnono-activity-logs -b work/activity-logs` from the repo root, do everything there, then `git -C . merge --ff-only work/activity-logs && git push`, then `git worktree remove` and `git branch -d`. The task is not done until `git worktree list` shows the main tree alone.
- **Never stage broadly.** `git add -A`, `git add .`, `git commit -a` and bare `git stash` are banned — other agent sessions share this working tree. Every commit passes explicit pathspecs.
- **Slug vocabulary is append-only.** `back_dev_home/_logging/feature_map.py` writes into the OpenSearch `usage_events` index. Never rename a slug that has already been written. `tool_inventory` is a NEW slug; `cdsem`/`hvsem`/`provision`/`verity_sem`/`home` stop being written but their labels stay.
- **Do not edit `data.py` in any feature folder.** It is a stable dispatcher.
- **Do not edit `providers/mock.py` or `providers/office_example.py` for Task 5.** The directory join belongs in the route — the OpenSearch document holds employee numbers and no names.
- **Backend commands run from the repo root** with `.venv/bin/python -m pytest` (the `-m` is what puts the root on `sys.path`).
- **Frontend commands run from `front-dev-home/`.**
- **Run `npm run lint:md` from the repo root after any Markdown edit.**
- **Comment density matches the surrounding code.** Both files being edited most (`feature_map.py`, `pageIdentity.ts`) carry long explanatory comments on every non-obvious rule. Match that; a bare `return "tool_inventory"` will look wrong beside its neighbours.

## File Structure

| File | Responsibility | Tasks |
| --- | --- | --- |
| `back_dev_home/_logging/feature_map.py` | Route/page → slug. Owns the vocabulary. | 1, 2 |
| `back_dev_home/_logging/tests/test_feature_map.py` | Unit pins on that vocabulary. | 1, 2 |
| `front-dev-home/app/utils/pageIdentity.ts` | Frontend half of the same partition. | 1, 2 |
| `front-dev-home/app/utils/pageIdentity.test.ts` | Unit pins + the fixture contract. | 1, 2 |
| `front-dev-home/app/utils/__fixtures__/pageIdentityContract.json` | The shared table both halves are tested against. | 1, 2 |
| `front-dev-home/app/utils/activity.ts` | Feature labels, fab-row filtering. | 1, 3 |
| `front-dev-home/app/utils/activity.test.ts` | Unit pins for the above. | 3 |
| `front-dev-home/app/pages/activity.vue` | 사용 통계 page. | 3 |
| `front-dev-home/app/composables/useActivityUserTable.ts` | Admin user-table search/sort/export. | 4 |
| `back_dev_home/admin_logs/contracts.py` | Response shapes. | 5 |
| `back_dev_home/admin_logs/routes.py` | Blueprint + the directory join. | 5 |
| `back_dev_home/admin_logs/tests/test_routes.py` | **New.** Pins the join. | 5 |
| `front-dev-home/app/composables/useAdminLogsApi.ts` | Response types + fetch. | 5 |
| `front-dev-home/app/pages/admin/logs.vue` | 운영 로그 page. | 5, 6 |

---

### Task 0: Create the worktree

- [ ] **Step 1: Create an isolated worktree**

From the repo root:

```bash
git worktree add ../skewnono-activity-logs -b work/activity-logs
```

- [ ] **Step 2: Confirm the venv is reachable**

All backend commands in this plan use the MAIN checkout's venv, which the worktree does not have. Run backend commands with an explicit interpreter path:

```bash
cd ../skewnono-activity-logs
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest back_dev_home/_logging -q
```

Expected: PASS. If it errors on imports, you are in the wrong directory — `python -m pytest` must run from the worktree root.

- [ ] **Step 3: Install frontend deps in the worktree**

```bash
cd front-dev-home && npm install
```

Note: some `back_dev_home/**/providers/office.py` files are gitignored and therefore absent from a fresh worktree. Skip counts in pytest will legitimately differ from the main checkout. Compare `passed + skipped` totals, not `passed` alone.

---

### Task 1: `tool_inventory` slug for the 장비 상태 page

**Files:**
- Modify: `back_dev_home/_logging/feature_map.py:186-212`
- Modify: `back_dev_home/_logging/tests/test_feature_map.py:150-215`
- Modify: `front-dev-home/app/utils/pageIdentity.ts:38-65, 87-102`
- Modify: `front-dev-home/app/utils/pageIdentity.test.ts` (the `tool landing pages keep their tool` test)
- Modify: `front-dev-home/app/utils/__fixtures__/pageIdentityContract.json`
- Modify: `front-dev-home/app/utils/activity.ts:30-62`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: the slug string `tool_inventory` and the frontend constant `TOOL_INVENTORY_PATH = '/tool-inventory'`. Task 2 edits the same three files and must not revert these.

**Background the implementer needs:** `/ebeam/<tool>/[<fab>/]` with no page segment after it resolves to `[fab]/index.vue`, which renders `EbeamToolInventoryView` — the 장비 상태 page. All four tool families (`cd-sem`, `hv-sem`, `provision`, `verity-sem`) render the identical component, so it is ONE page currently split across four slugs by a fallback that was never meant to catch it.

- [ ] **Step 1: Write the failing backend tests**

In `back_dev_home/_logging/tests/test_feature_map.py`, add these five rows to the `test_page_to_feature_maps_frontend_paths` parametrize list, immediately after the `# Fabless ebeam pages.` group:

```python
        # The fab hub: /ebeam/<tool>[/<fab>] with no page after it is
        # [fab]/index.vue, which renders EbeamToolInventoryView for every tool
        # family. One page, one slug — the tool-segment fallback used to split
        # it four ways.
        ("/ebeam/cd-sem", "tool_inventory"),
        ("/ebeam/cd-sem/M14", "tool_inventory"),
        ("/ebeam/hv-sem/R3", "tool_inventory"),
        ("/ebeam/provision/R3", "tool_inventory"),
        ("/ebeam/verity-sem/M14", "tool_inventory"),
```

Then replace the body of `test_unknown_pages_fall_back_to_a_derived_slug` (its current `/ebeam/verity-sem/M14` case now resolves to `tool_inventory`, so it must move to a genuinely unmapped path):

```python
def test_unknown_pages_fall_back_to_a_derived_slug():
    """Same policy as route_to_feature: a new page groups sanely until mapped.

    The fallback deliberately stays the TOOL slug rather than tool_inventory:
    a future e-beam page nobody mapped must not be counted as 장비 상태, which
    would be a confident wrong answer instead of a vague one.
    """
    assert page_to_feature("/thickness") == "thickness"
    assert page_to_feature("/ebeam/verity-sem/M14/unmapped-page") == "verity_sem"
    assert page_to_feature("/ebeam/cd-sem/M14/unmapped-page") == "cdsem"
```

And add a new test directly below it:

```python
def test_bare_ebeam_is_not_the_tool_inventory_page():
    """/ebeam alone names no tool, so it is not the fab hub.

    Not a real route — pinned because the tool_inventory rule keys on "nothing
    left after the fab", and a bare /ebeam also has nothing left. The frontend
    returns its own /ebeam identity for this shape, so the two halves would
    disagree if this drifted.
    """
    assert page_to_feature("/ebeam") == "ebeam"
```

- [ ] **Step 2: Run the backend tests to verify they fail**

```bash
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest back_dev_home/_logging/tests/test_feature_map.py -q
```

Expected: FAIL. The five new parametrize rows return `cdsem`/`hvsem`/`provision`/`verity_sem` instead of `tool_inventory`; `test_unknown_pages_fall_back_to_a_derived_slug` passes already.

- [ ] **Step 3: Implement the backend rule**

In `back_dev_home/_logging/feature_map.py`, inside `page_to_feature`'s `parts[0] == "ebeam"` branch, insert the new rule immediately after the fab segment is dropped (currently line 194-195), before the `recipe-status` check:

```python
        rest = parts[2:]
        if rest and _FAB_SEGMENT.match(rest[0]):
            rest = rest[1:]
        # Nothing left after the fab: /ebeam/<tool> and /ebeam/<tool>/<fab> are
        # both [fab]/index.vue, which renders EbeamToolInventoryView (장비 상태)
        # for all four tool families. One page, so one slug — the tool-segment
        # fallback at the bottom of this branch used to catch it and split it
        # four ways, which is the whole reason CD-SEM appeared in the ranking.
        #
        # `len(parts) >= 2` because a bare /ebeam names no tool and is not that
        # page; it keeps the fallback, which the frontend matches with its own
        # /ebeam early return.
        if len(parts) >= 2 and not rest:
            return "tool_inventory"
        if rest and rest[0] == "recipe-status":
```

- [ ] **Step 4: Run the backend tests**

```bash
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest back_dev_home/_logging -q
```

Expected: `test_feature_map.py` PASSES. `test_feature_map_contract.py` FAILS on the three landing rows, because the shared fixture still claims `cdsem`/`hvsem` for them — Step 5 fixes that. If anything OTHER than those contract rows fails, stop and investigate.

- [ ] **Step 5: Update the shared fixture**

In `front-dev-home/app/utils/__fixtures__/pageIdentityContract.json`, change these three rows:

```json
  {
    "path": "/ebeam/cd-sem",
    "query": {},
    "slug": "tool_inventory",
    "comment": "Fab hub, fabless shape — redirects to the fab shape below"
  },
  {
    "path": "/ebeam/cd-sem/M14",
    "query": {},
    "slug": "tool_inventory",
    "comment": "Fab hub: [fab]/index.vue renders EbeamToolInventoryView (장비 상태)"
  },
  {
    "path": "/ebeam/hv-sem/R3",
    "query": {},
    "slug": "tool_inventory",
    "comment": "Same page under a different tool family, so the same slug"
  },
```

And add these three rows after them:

```json
  {
    "path": "/ebeam/provision/R3",
    "query": {},
    "slug": "tool_inventory"
  },
  {
    "path": "/ebeam/verity-sem/M14",
    "query": {},
    "slug": "tool_inventory"
  },
  {
    "path": "/ebeam/cd-sem/M14/unmapped-page",
    "query": {},
    "slug": "cdsem",
    "comment": "Unmapped e-beam page still falls back to its tool, NOT to tool_inventory"
  },
```

- [ ] **Step 6: Run the backend contract test to verify it passes**

```bash
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest back_dev_home/_logging -q
```

Expected: PASS, all of it.

- [ ] **Step 7: Run the frontend tests to verify they now fail**

```bash
cd front-dev-home && npm test
```

Expected: FAIL in `pageIdentity.test.ts` — the fixture now claims `tool_inventory` for rows the frontend still resolves to `/ebeam/cd-sem`, and `/ebeam/cd-sem/M14/unmapped-page` collides with them.

- [ ] **Step 8: Implement the frontend half**

In `front-dev-home/app/utils/pageIdentity.ts`, add the constant directly above `IDENTITY_RULES`:

```ts
// The canonical path for the fab-hub shape: /ebeam/<tool> and
// /ebeam/<tool>/<fab> with no page segment after them, which is
// [fab]/index.vue — EbeamToolInventoryView, 장비 상태.
//
// Unlike every other entry in IDENTITY_RULES this is NOT a route fragment.
// The four tool families share no path segment for this page, so the identity
// they must all collapse onto has to be synthesized. Matches the backend's
// `tool_inventory` slug.
const TOOL_INVENTORY_PATH = '/tool-inventory'
```

Add it to `IDENTITY_RULES`, at the end of the `// E-beam pages.` group (after `'/skewvoir'`):

```ts
  '/skewvoir',
  TOOL_INVENTORY_PATH,
```

And change the empty-remainder branch of `canonicalize` (currently line 97):

```ts
    // /ebeam/<tool> and /ebeam/<tool>/<fab> are the same page. Returning
    // `landing` here would make them share an identity with any UNMAPPED page
    // of the same tool, which falls back to `landing` below — two different
    // slugs, one identity. The synthetic path keeps them apart.
    if (rest.length === 0) return { path: TOOL_INVENTORY_PATH, landing }
```

- [ ] **Step 9: Rewrite the frontend unit test**

In `front-dev-home/app/utils/pageIdentity.test.ts`, replace the whole `test('tool landing pages keep their tool and stay off the home identity', ...)` block with these two tests. Leave the `/` assertion out entirely — Task 2 owns it and `/` still resolves to `home` at this point.

```ts
test('the fab hub is one identity across every tool family', () => {
  // /ebeam/<tool> and /ebeam/<tool>/<fab> both land on [fab]/index.vue, which
  // renders EbeamToolInventoryView (장비 상태) for all four tool families.
  // One page, so one identity — matching the backend's tool_inventory slug.
  const identities = new Set([
    resolvePageIdentity('/ebeam/cd-sem', {}),
    resolvePageIdentity('/ebeam/cd-sem/M14', {}),
    resolvePageIdentity('/ebeam/hv-sem/R3', {}),
    resolvePageIdentity('/ebeam/provision/R3', {}),
    resolvePageIdentity('/ebeam/verity-sem/M14', {})
  ])

  assert.equal(identities.size, 1)
  assert.ok(identities.has('/tool-inventory'))
})

test('an unmapped e-beam page falls back to its tool, not to the fab hub', () => {
  // Otherwise a page nobody mapped would be counted as 장비 상태 — a confident
  // wrong answer where the tool fallback gives a vague right one.
  const unmapped = resolvePageIdentity('/ebeam/cd-sem/M14/unmapped-page', {})

  assert.ok(unmapped)
  assert.notEqual(unmapped, resolvePageIdentity('/ebeam/cd-sem/M14', {}))
})
```

- [ ] **Step 10: Run the frontend tests to verify they pass**

```bash
cd front-dev-home && npm test
```

Expected: PASS.

- [ ] **Step 11: Add the label**

In `front-dev-home/app/utils/activity.ts`, add to `FEATURE_LABELS` between `thickness` and `verity_sem` (the map is alphabetical by key):

```ts
  thickness: 'Thickness Metrology',
  tool_inventory: '장비 상태',
  verity_sem: 'VeritySEM'
```

Then update the comment block above `FEATURE_LABELS` (currently lines 30-34) so it stops describing the old fallback behaviour:

```ts
// Page-level slugs — see back_dev_home/_logging/feature_map.py, which owns both
// the API-path map and the frontend-path map used by the page-view beacon.
// `cdsem`, `hvsem`, `provision`, `verity_sem` and `home` are no longer written:
// the fab hub became `tool_inventory` and `/` stopped being ranked. Their labels
// STAY — rows already in OpenSearch keep ranking until the 30-day window rolls
// past them, and a missing label renders them as `Cdsem`.
```

- [ ] **Step 12: Typecheck and lint**

```bash
cd front-dev-home && npm run typecheck && npm run lint
```

Expected: both clean.

- [ ] **Step 13: Commit**

```bash
git add back_dev_home/_logging/feature_map.py \
        back_dev_home/_logging/tests/test_feature_map.py \
        front-dev-home/app/utils/pageIdentity.ts \
        front-dev-home/app/utils/pageIdentity.test.ts \
        front-dev-home/app/utils/__fixtures__/pageIdentityContract.json \
        front-dev-home/app/utils/activity.ts
git commit -m "feat(activity): give the 장비 상태 page its own slug

/ebeam/<tool>[/<fab>] with no page after it is [fab]/index.vue, which renders
EbeamToolInventoryView for all four tool families. It had no rule, so the
tool-segment fallback caught it and split one page across cdsem, hvsem,
provision and verity_sem — which is why CD-SEM showed up in the ranking looking
like an unnamed feature.

The fallback itself stays the tool slug: a future unmapped e-beam page must not
be counted as 장비 상태. Old labels stay too, so rows already indexed remain
readable until the 30-day window rolls past them."
```

---

### Task 2: Drop 홈 from the feature ranking

**Files:**
- Modify: `back_dev_home/_logging/feature_map.py:180-181`
- Modify: `back_dev_home/_logging/tests/test_feature_map.py`
- Modify: `front-dev-home/app/utils/pageIdentity.ts:38-65, 119-142`
- Modify: `front-dev-home/app/utils/pageIdentity.test.ts`
- Modify: `front-dev-home/app/utils/__fixtures__/pageIdentityContract.json`

**Interfaces:**
- Consumes: `TOOL_INVENTORY_PATH` from Task 1 (already in `IDENTITY_RULES`; do not remove it).
- Produces: nothing later tasks depend on.

**Background the implementer needs:** `/` is a real page (tool-type overview, fab picker, service health), but everyone passes through it, so ranking it answers a question DAU already answers while pushing a genuine feature out of the Top 10. When `resolvePageIdentity` returns `null`, `plugins/pageView.client.ts` returns before its `$fetch` — so no beacon is sent and **no log row exists at all**, which is stronger than a weight-0 row.

- [ ] **Step 1: Write the failing backend test**

In `back_dev_home/_logging/tests/test_feature_map.py`, delete the `("/", "home"),` row from the `test_page_to_feature_maps_frontend_paths` parametrize list (it sits in the `# Standalone pages.` group), and add this test immediately after `test_ops_pages_are_not_ranked`:

```python
def test_the_home_hub_is_not_ranked():
    """/ is a real page but a waypoint: everyone passes through it.

    Not an ops page — it is product surface — so it is excluded here rather
    than via _OPS_PAGE_PREFIXES. Ranking it answers "who opened the app", which
    DAU already answers, while costing a real feature its Top 10 slot. None
    means the frontend beacon never fires, so no row is written at all.
    """
    assert page_to_feature("/") is None
```

- [ ] **Step 2: Run the backend test to verify it fails**

```bash
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest back_dev_home/_logging/tests/test_feature_map.py -q
```

Expected: FAIL — `test_the_home_hub_is_not_ranked` gets `'home'` instead of `None`.

- [ ] **Step 3: Implement the backend change**

In `back_dev_home/_logging/feature_map.py`, replace the root-path branch of `page_to_feature` (currently lines 180-181):

```python
    if clean == "/":
        # The hub everyone passes through on the way somewhere else. A real
        # page, but not a rankable one: its count is "who opened the app",
        # which DAU/WAU/MAU already report, and leaving it in pushes a genuine
        # feature out of the Top 10.
        #
        # Not in _OPS_PAGE_PREFIXES because it is product surface, not an ops
        # screen — the exclusion is for a different reason and says so here.
        return None
```

- [ ] **Step 4: Run the backend tests to verify**

```bash
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest back_dev_home/_logging -q
```

Expected: `test_feature_map.py` PASSES; `test_feature_map_contract.py` FAILS on the `/` row (the fixture still says `home`). Step 5 fixes it.

- [ ] **Step 5: Update the shared fixture**

In `front-dev-home/app/utils/__fixtures__/pageIdentityContract.json`, change the `/` row:

```json
  {
    "path": "/",
    "query": {},
    "slug": null,
    "comment": "The hub is a waypoint, not a ranked feature — no beacon fires"
  },
```

- [ ] **Step 6: Run the backend tests again**

```bash
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest back_dev_home/_logging -q
```

Expected: PASS, all of it.

- [ ] **Step 7: Run the frontend tests to verify they now fail**

```bash
cd front-dev-home && npm test
```

Expected: FAIL — the fixture's `contract: null slug rows must produce null identity` assertion, because `resolvePageIdentity('/', {})` still returns `'/'`.

- [ ] **Step 8: Implement the frontend half**

In `front-dev-home/app/utils/pageIdentity.ts`, remove the trailing `'/'` entry from `IDENTITY_RULES` (it is the last item in the `// Standalone pages.` group). Removing it changes nothing for other paths — the rule only ever matched the root exactly, since `startsWith('//')` is never true.

Then add the early return in `resolvePageIdentity`, immediately after the `canonicalize` call and before the `recipe-status` check:

```ts
  const { path: canonical, landing } = canonicalize(path)

  // The hub at / is a waypoint everyone passes through, not a ranked feature.
  // The backend returns None for it, so the beacon must not fire either — and
  // a null here means report() returns before its $fetch, so no row is written
  // at all rather than a weight-0 one.
  if (canonical === '/') return null
```

- [ ] **Step 9: Add the frontend unit test**

In `front-dev-home/app/utils/pageIdentity.test.ts`, add this beside the existing `test('ops pages have no rankable identity', ...)`:

```ts
test('the home hub has no rankable identity', () => {
  // Not an ops page — product surface excluded for a different reason: it is
  // a waypoint, and DAU already counts how many people passed through.
  assert.equal(resolvePageIdentity('/', {}), null)
})
```

- [ ] **Step 10: Run the frontend tests to verify they pass**

```bash
cd front-dev-home && npm test && npm run typecheck && npm run lint
```

Expected: all PASS and clean.

- [ ] **Step 11: Commit**

```bash
git add back_dev_home/_logging/feature_map.py \
        back_dev_home/_logging/tests/test_feature_map.py \
        front-dev-home/app/utils/pageIdentity.ts \
        front-dev-home/app/utils/pageIdentity.test.ts \
        front-dev-home/app/utils/__fixtures__/pageIdentityContract.json
git commit -m "feat(activity): stop ranking the home hub

/ is a real page but a waypoint — everyone passes through it, so its rank
answers a question DAU already answers while pushing a genuine feature out of
the Top 10.

page_to_feature returns None and resolvePageIdentity returns null, so
pageView.client.ts returns before its \$fetch: no beacon, no row. The `home`
label stays in FEATURE_LABELS for rows already indexed."
```

---

### Task 3: Drop the 미지정 bucket from the Fab card

**Files:**
- Modify: `front-dev-home/app/utils/activity.ts`
- Modify: `front-dev-home/app/utils/activity.test.ts`
- Modify: `front-dev-home/app/pages/activity.vue:249-263, 774-779`

**Interfaces:**
- Consumes: nothing.
- Produces: `UNASSIGNED_FAB: string` and `rankableFabRows<T extends { fab: string }>(rows: readonly T[]): T[]`, both exported from `~/utils/activity`.

**Background the implementer needs:** the backend groups documents whose `fab_name_list` is empty into a bucket literally named `미지정` (`back_dev_home/activity/providers/opensearch_reader.py:566-570`). Those are not users who skipped a fab — they are requests from pages that have no fab: `device_statistics` queries by `fac_id`, AFM and parts of skewvoir never send one. Listing it beside M14 and R3 invites reading it as an unattributed remainder of the same population.

- [ ] **Step 1: Write the failing test**

In `front-dev-home/app/utils/activity.test.ts`, add the import and the tests. Extend the existing import on line 3 to include the new names:

```ts
import { activityFeatureLabel, summarizePersonalActivity, pageViewNotice, PAGE_VIEW_SINCE, rankableFabRows, UNASSIGNED_FAB, userDisplayName, userSearchText, userTeamLabel } from './activity.ts'
```

Then append:

```ts
test('rankableFabRows drops the fab-less bucket and preserves order', () => {
  const rows = [{ fab: 'M14' }, { fab: UNASSIGNED_FAB }, { fab: 'R3' }]

  assert.deepEqual(rankableFabRows(rows), [{ fab: 'M14' }, { fab: 'R3' }])
})

test('rankableFabRows is a no-op when the backend sent no fab-less bucket', () => {
  const rows = [{ fab: 'M14' }, { fab: 'R3' }]

  assert.deepEqual(rankableFabRows(rows), rows)
})

test('rankableFabRows can empty the list entirely', () => {
  // A window in which only fab-less pages were used. The card must render its
  // empty state, not a one-row chart of nothing.
  assert.deepEqual(rankableFabRows([{ fab: UNASSIGNED_FAB }]), [])
})
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd front-dev-home && npm test
```

Expected: FAIL — `rankableFabRows` is not exported from `./activity.ts`.

- [ ] **Step 3: Implement the helper**

In `front-dev-home/app/utils/activity.ts`, add directly below `userSearchText`:

```ts
/** The FAB bucket name the backend gives documents that carry no fab_name.
 *
 *  The same literal lives in
 *  back_dev_home/activity/providers/opensearch_reader.py, which writes it.
 *  Two copies of one string, so changing either alone silently stops the
 *  filter below from matching and the bucket reappears. */
export const UNASSIGNED_FAB = '미지정'

/** Fab rows worth showing in the Fab별 페이지 사용 card.
 *
 *  Drops the 미지정 bucket. It is NOT "users who did not pick a fab" — it is
 *  traffic from pages that have no fab at all: device_statistics queries by
 *  fac_id, and AFM and parts of skewvoir never send one. Sitting beside M14
 *  and R3 it reads as an unattributed remainder of the same population, which
 *  is the opposite of what it is.
 *
 *  Generic over the row so the test can pass `{ fab }` alone rather than
 *  building a whole FabUsageRow. */
export const rankableFabRows = <T extends { fab: string }>(
  rows: readonly T[]
): T[] => rows.filter(row => row.fab !== UNASSIGNED_FAB)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd front-dev-home && npm test
```

Expected: PASS.

- [ ] **Step 5: Apply the filter on the page**

In `front-dev-home/app/pages/activity.vue`, extend the existing import from `~/utils/activity` (line 601) to include `rankableFabRows`:

```ts
import { activityFeatureLabel, summarizePersonalActivity, pageViewNotice, rankableFabRows, userDisplayName, userTeamLabel } from '~/utils/activity'
```

Then wrap `fabsForWindow` (currently lines 775-779):

```ts
const fabsForWindow = computed<FabUsageRow[]>(() =>
  rankableFabRows(
    fabWindowKey.value === '7d'
      ? fabs.value?.fabs_7d ?? []
      : fabs.value?.fabs_30d ?? []
  )
)
```

The `selectedFab` `watchEffect` below already handles an empty list and a selection that no longer exists, so no other change is needed.

- [ ] **Step 6: State the omission in the card header**

In the same file, in the `Fab별 페이지 사용` card's `#header` template (currently lines 250-263), add the caption inside the title span:

```html
      <template #header>
        <div class="flex items-center justify-between gap-3">
          <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
            <UIcon name="i-lucide-factory" />
            Fab별 페이지 사용
            <!-- rankableFabRows drops the 미지정 bucket. Saying so matters:
                 a silent omission reads as "this is all the traffic", and
                 device-statistics and AFM are missing from this card entirely. -->
            <span class="sk-meta font-normal">· FAB 무관 페이지 제외</span>
          </span>
          <UTabs
            v-model="fabWindowKey"
            :items="windowTabs"
            variant="pill"
            size="xs"
          />
        </div>
      </template>
```

- [ ] **Step 7: Typecheck and lint**

```bash
cd front-dev-home && npm test && npm run typecheck && npm run lint
```

Expected: all PASS and clean.

- [ ] **Step 8: Commit**

```bash
git add front-dev-home/app/utils/activity.ts \
        front-dev-home/app/utils/activity.test.ts \
        front-dev-home/app/pages/activity.vue
git commit -m "fix(activity): drop the fab-less bucket from the Fab card

The 미지정 bucket is not users who skipped a fab — it is requests from pages
that have no fab: device_statistics queries by fac_id, AFM and parts of
skewvoir never send one. Beside M14 and R3 it read as an unattributed
remainder of the same population.

Frontend-only, so the API and the office adapter are untouched and this is one
line to revert. The card header now states the omission; a silent one reads as
'this is all the traffic'."
```

---

### Task 4: Default the user table to 최근 활동 순

**Files:**
- Modify: `front-dev-home/app/composables/useActivityUserTable.ts:15, 55-58, 71, 77`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing.

**Background the implementer needs:** three call sites hold the default sort and they must move together. If only line 15 changes, `hasActiveControls` is true on first render (so the 초기화 button lights up before the admin has touched anything) and `resetControls` restores `requests` — a reset that does not reset.

- [ ] **Step 1: Change the default**

In `front-dev-home/app/composables/useActivityUserTable.ts`, line 15:

```ts
  // 최근 활동 순 by default: the question that opens this table is almost
  // always "who is using it right now", not "who used it most over 30 days".
  // Three places hold this default — this ref, hasActiveControls and
  // resetControls — and they must agree, or the 초기화 button lights up on
  // first render and then resets to something that was never the default.
  const sort = ref<UserSort>('recent')
```

- [ ] **Step 2: Move the other two call sites**

Line 71:

```ts
  const hasActiveControls = computed(() =>
    Boolean(query.value) || featureFilter.value !== 'all' || sort.value !== 'recent'
  )
```

Line 77:

```ts
    sort.value = 'recent'
```

- [ ] **Step 3: Add the tiebreak**

In `filteredRows`, the `recent` branch (currently lines 55-58):

```ts
      if (sort.value === 'recent') {
        return (right.last_seen ? Date.parse(right.last_seen) : 0)
          - (left.last_seen ? Date.parse(left.last_seen) : 0)
          // Ties are ordinary — several people last active in the same second,
          // and every row with a null last_seen scores 0. Without a tiebreak
          // their order is whatever the backend happened to send, which it
          // does not promise to keep stable between refreshes.
          || left.user_id.localeCompare(right.user_id)
      }
```

Leave `sortOptions` in its current order. The dropdown order and the default are separate decisions, and reshuffling a list an admin already knows costs more than it gains.

- [ ] **Step 4: Typecheck and lint**

```bash
cd front-dev-home && npm run typecheck && npm run lint
```

Expected: both clean. There is no unit test for this file — `npm test` covers pure functions only, and this sort lives behind Vue refs. It is verified in the browser in Task 7.

- [ ] **Step 5: Commit**

```bash
git add front-dev-home/app/composables/useActivityUserTable.ts
git commit -m "feat(activity): default the admin user table to 최근 활동 순

The question that opens this table is 'who is using it now', not 'who used it
most in 30 days'. All three call sites holding the default move together —
changing only the ref would light up 초기화 on first render and then reset to
a value that was never the default.

Adds a user_id tiebreak to the recent branch: rows sharing a timestamp, and
every row with a null last_seen, were previously left in whatever order the
backend sent."
```

---

### Task 5: Show member names in the 운영 로그 User column

**Files:**
- Modify: `back_dev_home/admin_logs/contracts.py`
- Modify: `back_dev_home/admin_logs/routes.py`
- Create: `back_dev_home/admin_logs/tests/test_routes.py`
- Modify: `front-dev-home/app/composables/useAdminLogsApi.ts`
- Modify: `front-dev-home/app/pages/admin/logs.vue:228-233, 275-277`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `NamedLogQueryResponse` (= `LogQueryResponse` + `members: dict[str, str]`) on the backend, and `AdminLogsResponse.members: Record<string, string>` on the frontend. Task 6 edits the same `.vue` file and must not revert the User cell.

**Background the implementer needs:** `activity/routes.py:52-82` already solved this exact problem and its docstring records why the join lives in the route: the logging store records employee numbers and no names, so the provider contract must not promise either, and `lookup_members` decides for itself whether to dial office Redis or fabricate a home row. `lookup_members` never raises — a directory outage costs the names and not the rows.

- [ ] **Step 1: Write the failing route test**

Create `back_dev_home/admin_logs/tests/test_routes.py`:

```python
"""The member-name join on the admin log page.

The join lives in the route rather than a provider because OpenSearch stores
employee numbers and no names — see activity/routes.py, which made the same
call for the same reason. These pin that a directory that cannot answer costs
the names and never the rows.
"""

import pytest
from flask import Flask, g

from back_dev_home._auth.directory import bare_member
from back_dev_home._auth.provider import SOURCE_LOCAL
from back_dev_home._core.contract_check import assert_matches
from back_dev_home.admin_logs import routes
from back_dev_home.admin_logs.contracts import NamedLogQueryResponse


def _item(user_id):
    """A full LogItem — every key is part of the contract, values may be None."""
    return {
        "id": f"doc-{user_id}",
        "index": "skewnono_log_local-2026.08.07",
        "timestamp": "2026-08-07T04:00:00Z",
        "level": "INFO",
        "event": "request",
        "logger": "skewnono.activity",
        "user_id": user_id,
        "method": "GET",
        "path": "/api/sem-list",
        "status": 200,
        "latency_ms": 12,
        "feature": "sem_list",
        "message": None,
        "exception": None,
        "raw": {"user_id": user_id},
    }


def _page(*user_ids):
    return {
        "generated_at": "2026-08-07T04:00:00Z",
        "page": 1,
        "page_size": 50,
        "total": len(user_ids),
        "page_count": 1,
        "filters": {},
        "items": [_item(user_id) for user_id in user_ids],
    }


@pytest.fixture
def make_client(monkeypatch):
    """Client factory with a stubbed provider, a stubbed directory, and admin."""

    monkeypatch.delenv("SKEWNONO_ADMIN_USERS", raising=False)

    def build(page, members):
        """``members`` is the directory's answer: a dict, or a callable taking
        the ids it was asked about (for the test that inspects them)."""
        resolve = members if callable(members) else (lambda ids: members)
        monkeypatch.setattr(routes, "query_logs", lambda params: page)
        monkeypatch.setattr(routes, "lookup_members", resolve)

        app = Flask(__name__)

        @app.before_request
        def identity():
            # local-dev is the home default admin; `local` is a trusted source.
            g.user_id = "local-dev"
            g.identity_source = SOURCE_LOCAL

        app.register_blueprint(routes.bp, url_prefix="/api")
        return app.test_client()

    return build


def _named(empno, name):
    return {**bare_member(empno), "emp_nm": name}


def test_named_users_are_carried_in_a_sibling_map(make_client):
    client = make_client(
        _page("2067928", "1234567"),
        {"2067928": _named("2067928", "고대영"), "1234567": _named("1234567", "홍길동")},
    )

    payload = client.get("/api/admin/logs").get_json()

    assert payload["members"] == {"2067928": "고대영", "1234567": "홍길동"}
    assert_matches(payload, NamedLogQueryResponse)


def test_the_name_stays_out_of_the_row_and_out_of_raw(make_client):
    """LogItem is the OpenSearch document. A joined name must not look like one."""
    client = make_client(
        _page("2067928"), {"2067928": _named("2067928", "고대영")}
    )

    item = client.get("/api/admin/logs").get_json()["items"][0]

    assert "emp_nm" not in item
    assert "emp_nm" not in item["raw"]


def test_unnamed_employees_are_omitted_rather_than_mapped_to_none(make_client):
    """The caller falls back to the number, so an entry would say nothing.

    Ordinary, not exceptional: contractors and service accounts hold a
    LASTUSER cookie with no directory row.
    """
    client = make_client(_page("9999999"), {"9999999": bare_member("9999999")})

    payload = client.get("/api/admin/logs").get_json()

    assert payload["members"] == {}
    assert len(payload["items"]) == 1


def test_a_directory_outage_costs_the_names_and_not_the_rows(make_client):
    """lookup_members degrades to bare rows rather than raising."""
    client = make_client(
        _page("2067928", "1234567"),
        {"2067928": bare_member("2067928"), "1234567": bare_member("1234567")},
    )

    payload = client.get("/api/admin/logs").get_json()

    assert payload["members"] == {}
    assert payload["total"] == 2
    assert len(payload["items"]) == 2


def test_rows_without_a_user_id_do_not_reach_the_directory(make_client):
    """Anonymous rows are ordinary. Asking about None would be a wasted lookup."""
    asked = []

    def record(ids):
        asked.extend(ids)
        return {}

    client = make_client(_page(None, "2067928"), record)

    payload = client.get("/api/admin/logs").get_json()

    assert asked == ["2067928"]
    assert payload["members"] == {}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest back_dev_home/admin_logs -q
```

Expected: FAIL on the import of `NamedLogQueryResponse`.

- [ ] **Step 3: Add the contract**

In `back_dev_home/admin_logs/contracts.py`, extend `__all__` and add the class at the end:

```python
__all__ = ["LogItem", "LogQueryResponse", "NamedLogQueryResponse"]
```

```python
class NamedLogQueryResponse(LogQueryResponse):
    """A log page with its employee numbers expanded into names.

    What the ROUTE returns; the providers return ``LogQueryResponse``. The
    logging store records employee numbers and no names, so LogItem must not
    promise one — see activity/routes.py, which split the same way.

    ``members`` is a sibling map rather than a field on each row for two
    reasons. A 200-row page usually holds fewer than ten distinct users, so
    per-row names would repeat the same string dozens of times. And LogItem
    already carries the verbatim source document as ``raw`` — an ``emp_nm``
    sitting beside a ``raw`` that has no such field would read as an
    OpenSearch field it is not.

    Employee numbers the directory could not name are OMITTED rather than
    mapped to None: the caller falls back to the number, so an entry would say
    nothing, and the value type stays a plain str.
    """

    members: dict[str, str]
```

- [ ] **Step 4: Implement the join**

Rewrite `back_dev_home/admin_logs/routes.py`:

```python
import logging

from flask import Blueprint, jsonify, request

from back_dev_home._auth.admin import require_admin
from back_dev_home._auth.directory import lookup_members
from back_dev_home._auth.errors import error_json

from .contracts import NamedLogQueryResponse
from .data import query_logs

bp = Blueprint("admin_logs", __name__)
logger = logging.getLogger("skewnono.admin_logs")


def _named_logs(params) -> NamedLogQueryResponse:
    """The log page with each employee number expanded into a name.

    The join lives here rather than in the providers because it is the same
    join on both sides of the swap: ``lookup_members`` decides for itself
    whether to dial office Redis or fabricate a home row, so neither
    ``mock.py`` nor ``office.py`` has anything to contribute.

    A directory that cannot answer costs the names and not the page:
    ``lookup_members`` never raises, and the map simply comes back empty.
    """
    payload = query_logs(params)
    members = lookup_members(
        item["user_id"] for item in payload["items"] if item.get("user_id")
    )
    return {
        **payload,
        # Only the ones that resolved. An id the directory could not name is
        # absent, not None — the caller shows the number either way.
        "members": {
            user_id: member["emp_nm"]
            for user_id, member in members.items()
            if member.get("emp_nm")
        },
    }


@bp.get("/admin/logs")
@require_admin
def admin_logs():
    try:
        return jsonify(_named_logs(request.args))
    except ValueError as exc:
        return error_json("invalid_log_query", str(exc), 400)
    except Exception:  # Admin view must fail closed without leaking details.
        logger.exception("Failed to query OpenSearch logs")
        return error_json(
            "log_query_failed",
            "Could not query OpenSearch logs",
            503,
        )
```

- [ ] **Step 5: Run the backend tests to verify they pass**

```bash
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest back_dev_home/admin_logs -q
```

Expected: PASS.

- [ ] **Step 6: Add the frontend response type**

In `front-dev-home/app/composables/useAdminLogsApi.ts`, add to `AdminLogsResponse` after `filters`:

```ts
  /** Employee number → directory name, for the rows on this page only.
   *
   * A sibling map rather than a field on AdminLogItem: the backend joins it in
   * the route, so it is not part of the OpenSearch document each row carries in
   * `raw`. Employee numbers the directory could not name are absent — fall
   * back to the number itself. */
  members: Record<string, string>
  items: AdminLogItem[]
```

- [ ] **Step 7: Render the name in the User cell**

In `front-dev-home/app/pages/admin/logs.vue`, add this helper to the `<script setup>` block, beside `formatTime`:

```ts
// Name leads, employee number underneath rather than instead of — the same
// rule the /activity user table uses, and for the same reason: the log filters
// and every other screen key on the empno, so it has to stay readable. No
// second line when there is no name; the id is already the first one.
const userCell = (userId: string | null) => {
  if (!userId) return { name: '-', empno: null }
  const name = logs.value?.members?.[userId]
  return name ? { name, empno: userId } : { name: userId, empno: null }
}
```

Then replace the User `<td>` (currently lines 275-277):

```html
                <td class="whitespace-nowrap px-3 py-2">
                  <div class="text-[11px]">
                    {{ userCell(row.user_id).name }}
                  </div>
                  <div
                    v-if="userCell(row.user_id).empno"
                    class="font-mono text-[10px] text-(--sk-ink-muted)"
                  >
                    {{ userCell(row.user_id).empno }}
                  </div>
                </td>
```

The name drops `font-mono` because it is Korean text; the employee number keeps it because it is a fixed-width identifier that gets scanned down a column.

- [ ] **Step 8: Typecheck and lint**

```bash
cd front-dev-home && npm run typecheck && npm run lint
```

Expected: both clean.

- [ ] **Step 9: Commit**

```bash
git add back_dev_home/admin_logs/contracts.py \
        back_dev_home/admin_logs/routes.py \
        back_dev_home/admin_logs/tests/test_routes.py \
        front-dev-home/app/composables/useAdminLogsApi.ts \
        front-dev-home/app/pages/admin/logs.vue
git commit -m "feat(admin-logs): name the employee numbers in the User column

Joined in the route with lookup_members, the way activity/routes.py does and
for the same reason: OpenSearch stores employee numbers and no names, so
LogItem must not promise one.

Carried as a sibling members map rather than per-row. A 200-row page usually
holds fewer than ten distinct users, and LogItem already ships the verbatim
document as raw — a top-level emp_nm beside a raw that lacks it would read as
a source field. Ids the directory could not name are omitted, so the value
type stays str and the caller falls back to the number.

Filtering BY name is deliberately not included: the directory is an
HGET-by-empno hash with no reverse index."
```

---

### Task 6: One-click 4XX/5XX filter on 운영 로그

**Files:**
- Modify: `front-dev-home/app/pages/admin/logs.vue:45-97, 417-464`

**Interfaces:**
- Consumes: the `draft`, `applyFilters` and `DraftFilters` symbols already in the file; the User cell from Task 5 must survive untouched.
- Produces: nothing.

**Background the implementer needs:** the backend already accepts a status range (`admin_logs/query.py:145-153` builds `{"range": {"status": {...}}}` from `status_min`/`status_max`), so this is frontend-only. The presets write into those two fields rather than holding state of their own — that is what keeps the segmented control and the manual number inputs from ever disagreeing, and it means the active preset is *derived*, so typing a custom range deselects every chip on its own.

- [ ] **Step 1: Add the preset table and handlers**

In `front-dev-home/app/pages/admin/logs.vue`, add to `<script setup>` directly above `applyFilters`:

```ts
// Status presets. This page exists to find what broke, and status_min/max
// already express that as a range — so a preset WRITES those two fields
// instead of holding a state of its own. The active preset is read back out of
// them, which is why editing the numbers by hand deselects every chip without
// any extra wiring.
const statusPresets = [
  { label: '전체', value: 'all', min: '', max: '' },
  { label: '4XX', value: '4xx', min: '400', max: '499' },
  { label: '5XX', value: '5xx', min: '500', max: '599' },
  { label: '오류 전체', value: 'error', min: '400', max: '599' }
] as const

// '' when the range matches no preset — chips render unselected, which is the
// honest display for a hand-typed range.
const statusPreset = computed(() =>
  statusPresets.find(
    preset => preset.min === draft.status_min && preset.max === draft.status_max
  )?.value ?? ''
)

// Applies immediately, unlike every other control in this card. A one-click
// "show me the errors" that needs a second click on Search is not one click.
// The cost is that it carries along whatever else is sitting unapplied in the
// draft — accepted, because a second apply path would be a second place for
// the two to drift.
const applyStatusPreset = (value: string) => {
  const preset = statusPresets.find(item => item.value === value)
  if (!preset) return
  draft.status_min = preset.min
  draft.status_max = preset.max
  applyFilters()
}
```

- [ ] **Step 2: Add the chip row to the template**

In the same file, insert this as the first child of the filter `<section>`, immediately above the existing `<div class="grid grid-cols-1 gap-2 md:grid-cols-4 xl:grid-cols-6">` (line 46):

```html
      <div class="mb-2 flex flex-wrap items-center gap-1.5">
        <span class="sk-eyebrow mr-1">상태</span>
        <UButton
          v-for="preset in statusPresets"
          :key="preset.value"
          size="xs"
          :color="statusPreset === preset.value ? 'primary' : 'neutral'"
          :variant="statusPreset === preset.value ? 'solid' : 'outline'"
          @click="applyStatusPreset(preset.value)"
        >
          {{ preset.label }}
        </UButton>
      </div>
```

Chips rather than `UTabs`: a preset can be inactive (a hand-typed range matches none of them) and `UTabs` has no unselected state to express that.

- [ ] **Step 3: Typecheck and lint**

```bash
cd front-dev-home && npm run typecheck && npm run lint
```

Expected: both clean.

- [ ] **Step 4: Commit**

```bash
git add front-dev-home/app/pages/admin/logs.vue
git commit -m "feat(admin-logs): add 4XX/5XX status presets

Error triage is what this page is for, and it was buried behind two free-text
number inputs. The backend already takes a status range, so this is
frontend-only.

The presets write status_min/status_max rather than holding their own state,
and the active chip is read back out of those two fields — so a hand-typed
range deselects every chip with no extra wiring. They apply immediately,
unlike the rest of the card: a one-click filter that needs a second click on
Search is not one."
```

---

### Task 7: Browser verification and full suite

**Files:** none modified unless a defect is found.

**Interfaces:**
- Consumes: everything from Tasks 1–6.
- Produces: nothing.

**Background the implementer needs:** there is no automated E2E suite in this repo — no Playwright config, no component tests. Browser verification is driving Playwright MCP by hand; follow the `verify` skill for the launch recipe. Identity is the `LASTUSER` cookie: `local-dev` is the admin, so both `/activity`'s admin panels and `/admin/logs` need it. `/api/*` is rate-limited to 20 requests per 5 seconds per user.

- [ ] **Step 1: Run the full backend suite**

```bash
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest -q
```

Expected: PASS (~2180 tests, ~72 s). Skip counts will differ from the main checkout because gitignored `office.py` files are absent here — compare `passed + skipped`, not `passed`.

- [ ] **Step 2: Run the full frontend suite**

```bash
cd front-dev-home && npm test && npm run typecheck && npm run lint
```

Expected: all PASS and clean.

- [ ] **Step 3: Lint Markdown**

From the repo root:

```bash
npm run lint:md
```

Expected: `0 error(s)`.

- [ ] **Step 4: Start both servers**

```bash
/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python index.py     # :5050
cd front-dev-home && npm run dev                                      # :3000
```

If every route renders `<!---->` with no console errors, Flask is down — check :5050 before blaming a component.

- [ ] **Step 5: Verify `/admin/logs` as `local-dev`**

Check, with a screenshot saved under `.playwright-mcp/screenshots/`:

1. The 상태 chip row renders above the filter grid; 전체 is selected on load.
2. Clicking 5XX filters the table without pressing Search, and `status_min`/`status_max` show `500`/`599`.
3. Typing `418` into `status_min` by hand deselects every chip.
4. The User column shows a name over an employee number. At home the directory fabricates `홍길동(<사번>)`, so that is the expected name — it is a placeholder standing in for the shape, not office data.

- [ ] **Step 6: Verify `/activity` as `local-dev`**

1. The 사용자 table is sorted most-recent-first on load and the **새로고침** button
   (the control-reset button beside the CSV export — relabelled from 초기화 by
   commit `69c60c6`, behaviour unchanged) is **disabled**.
2. Changing the sort enables 새로고침; pressing it returns to 최근 활동 순.
3. The `Fab별 페이지 사용` card header reads `· FAB 무관 페이지 제외` and no `미지정` entry appears in the fab list.
4. Navigate to `/`, then to `/ebeam/cd-sem/M14`, and confirm in the network panel that a `POST /api/page-view` fires for the second and **not** the first.

- [ ] **Step 7: Merge and tear down the worktree**

From the main checkout:

```bash
git -C /Users/daeyoung/Codes/skewnono_v3_nuxt merge --ff-only work/activity-logs
git -C /Users/daeyoung/Codes/skewnono_v3_nuxt push
git -C /Users/daeyoung/Codes/skewnono_v3_nuxt worktree remove ../skewnono-activity-logs
git -C /Users/daeyoung/Codes/skewnono_v3_nuxt branch -d work/activity-logs
```

Confirm `git worktree list` shows the main tree alone. The task is not done until it does.

If `merge --ff-only` refuses, `main` moved while you worked. Do NOT force it — rebase `work/activity-logs` onto the new `main` and re-run the full suite before merging. A clean auto-merge can still produce broken code here, because the two halves of the page-identity contract live in different trees.
