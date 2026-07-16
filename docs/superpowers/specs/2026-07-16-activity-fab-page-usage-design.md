# Activity: Fab별 페이지 사용 (replaces SEM List 모델별 사용)

**Date:** 2026-07-16
**Status:** Approved — ready for implementation plan

## Problem

The 사용 통계 (activity) page carries a "SEM List 모델별 사용" card that ranks
SEM equipment models by usage. This answers a low-value question — model
popularity mirrors fleet size and tells us little about how the application is
actually used.

The more valuable question is **fab usage**: which fab the traffic comes from,
and which pages are frequently activated within that fab. We do **not** care
about individual user/engineer identity in this card.

## Goal

Replace the SEM-model card with a **Fab별 페이지 사용** card:

- A selectable fab list on the left (same interaction shape as the ebeam
  `FabSidebar`, but scoped inside the card).
- For the selected fab, a bar list of its most-activated pages on the right.
- A 7일 / 30일 window toggle, matching the other shared-usage cards.
- Only fabs with recorded activity appear, ranked by total requests. The
  busiest fab is selected by default.

## Non-goals

- No per-user / per-engineer breakdown inside this card (the existing 사용자
  table already covers user drill-down).
- No new office (cloud) reader implementation beyond a stub that falls back to
  the mock — the office Redis/OpenSearch rollup is deferred to Phase 2/3, same
  as the SEM-model reader it replaces.

## Data model

### Fab affiliation

`_UserState` gains a `fab: str | None` field. Fab affiliation is a property of
the **user**, assigned once (their home fab). Real `record_request()` traffic
leaves `fab=None`; those requests roll up under an "미지정" bucket so live dev
traffic still appears.

Seeded demo users each get a home fab drawn from the existing sem_list fleet
fabs (`M11, M12, M14, M15, M16, R3, R4`), assigned deterministically:

| user        | fab  |
| ----------- | ---- |
| kim.minju   | M14  |
| park.jinho  | M16B |
| lee.soyoung | M11  |
| choi.eunwoo | R3   |
| jung.hari   | M15  |

(Values are illustrative; the implementation fixes them in `seed_demo_users`.)

### Aggregation

The in-memory mock only carries **lifetime** `by_feature` totals plus per-day
`daily` totals — not per-feature-per-day. Per-window page counts are therefore
approximated by the existing `_scale_features()` helper: scale a user's
lifetime `by_feature` map by that user's share-of-activity within the window,
then accumulate into the user's fab bucket. This is the same approximation the
top-features summary already uses, so the two cards stay consistent.

## Backend

`back_dev_home/activity/data.py`:

- Add `fab` to `_UserState`.
- Add TypedDicts:

  ```python
  class FabPageCount(TypedDict):
      feature: str
      count: int

  class FabUsageRow(TypedDict):
      fab: str            # "미지정" for unaffiliated traffic
      total: int          # scaled request total in the window
      pages: list[FabPageCount]

  class FabUsageResponse(TypedDict):
      generated_at: str
      fabs_7d: list[FabUsageRow]
      fabs_30d: list[FabUsageRow]
  ```

- Add `get_fab_page_usage() -> FabUsageResponse`:
  - `_fab_page_usage_from_mock()` walks `_users`, computes each user's 7d/30d
    window sums (same loop as `_summary_from_mock`), scales `by_feature` into a
    per-fab feature dict, and emits rows sorted by `total` desc. Pages within a
    row are `_top_features(...)` (capped at 10). Fabs with zero total are
    omitted.
  - `is_cloud()` branch tries `_office_reader.fab_page_usage_from_backends()`
    and falls back to the mock on exception, mirroring the existing pattern.
- Update `seed_demo_users` to assign `fab`.
- Update `__all__`: add `FabPageCount`, `FabUsageRow`, `FabUsageResponse`,
  `get_fab_page_usage`; remove `SemModelCount`, `SemModelUsageResponse`,
  `get_sem_model_usage`.
- Delete `SemModelCount`, `SemModelUsageResponse`, `_sem_model_usage_from_mock`,
  `get_sem_model_usage`.

`back_dev_home/activity/routes.py`:

- Replace the `/activity/sem-models` route with `GET /activity/fabs` →
  `get_fab_page_usage()`.
- Update the import block accordingly.

Office reader: `_office_reader.py` does **not** exist today — the existing
`is_cloud()` branches import a not-yet-written module and rely on the
`try/except` to fall back to the mock. `get_fab_page_usage()` keeps that exact
pattern (`from ._office_reader import fab_page_usage_from_backends`), so no new
file is created; the import simply fails and the mock runs. This matches the
SEM-model reader it replaces.

## Frontend

`front-dev-home/app/composables/useActivityApi.ts`:

- Remove `SemModelCount`, `SemModelUsageResponse`, `useActivitySemModels`,
  `SEM_MODELS_KEY`, `inFlightSemModels`, `semModelsUrl`, and its
  `resetActivityCache` line.
- Add:

  ```ts
  export interface FabPageCount { feature: string; count: number }
  export interface FabUsageRow { fab: string; total: number; pages: FabPageCount[] }
  export interface FabUsageResponse {
    generated_at: string
    fabs_7d: FabUsageRow[]
    fabs_30d: FabUsageRow[]
  }
  ```

  plus `useActivityFabs()` (key `activity-fabs`, url `/activity/fabs`) following
  the exact in-flight-dedup + `getCachedData` shape of the other queries, and a
  matching `resetActivityCache` reset.

`front-dev-home/app/pages/activity.vue`:

- Swap `useActivitySemModels`/`semModels`/`SemModelCount` usage for
  `useActivityFabs`/`fabs`. Update `sharedQueries`, `loadError`, `refreshing`,
  and `refreshAll`.
- Replace the SEM-model card (currently lines ~225–261) with the Fab card:
  - Header: microscope→ `i-lucide-factory` icon, title "Fab별 페이지 사용",
    plus the 7d/30d `UTabs` bound to a new `fabWindowKey` ref.
  - Body: two-column layout. Left = fab list (`UButton`/list items, one per
    `FabUsageRow`, showing fab name + total, selected state highlighted).
    Right = `ActivityFeatureBarList :items="selectedFabPages"`.
  - `fabsForWindow` computed picks `fabs_7d`/`fabs_30d`; `selectedFab` ref
    defaults to the first (busiest) row and resets when the window changes if
    the current selection is absent; `selectedFabPages` maps the selected row's
    `pages`. Empty-state text when no fabs have activity.
- `ActivityModelBarList.vue` is referenced only by `activity.vue`, so it
  becomes dead after this change and is deleted.

## Testing

- `tests/` backend: adapt/replace the existing `activity/sem-models` test with
  a `/activity/fabs` test asserting: response has `fabs_7d`/`fabs_30d`, each row
  has `fab`/`total`/`pages`, rows sorted by `total` desc, seeded demo fabs
  present, and `total > 0` for every row.
- Verify the page renders and the fab selector switches page lists via the
  `verify` skill (Flask mock + Nuxt).

## Rollback

Revert is a single commit — the change is additive-then-substitutive within the
activity feature slice and the activity composable, with no shared-schema
migration.
