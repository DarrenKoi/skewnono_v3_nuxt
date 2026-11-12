# AMAT recipe_usage review

Reviewed `main..4e1d75f5` on `work/amat-recipe` against `contracts.py`, both
original office notes, the schema document, and vendor-onboarding §5.
The change adds AMAT recipe catalogue, detail, and usage APIs and their search
and status screens. Findings below are from code tracing; the existing tests pass.

## should

1. **The Fail sample guard fails when the rate is sorted ascending.**
   `frontend/app/utils/recipeUsage.ts:78`
   - Failing input: recipe A has `runs=1, fail_runs=1`; recipe B has
     `runs=20, fail_runs=1`. Open Fail and toggle “Fail 비율” to ascending.
     A gets `fail_rate_ranked=0`, so the shared ranking table puts A before B,
     while its cell displays `100%`. The screen promises that recipes below
     five runs are excluded from this ranking, but the insufficient sample
     leads the ascending ranking. Existing tests cover only the initial sort.
   - Fix: for this rate column, compare `low_sample` first and keep those rows
     after eligible rows in both directions, then compare the actual rate.
     The AMAT caller needs a comparator supported by the shared table; use
     `MANUAL_SORTING_OPTIONS` so UTable does not re-sort the result. Preserve
     the existing Hitachi comparator as the default. Check both directions
     across a page boundary.

2. **An empty family history hides the roster instead of showing zeroes.**
   `frontend/app/components/ebeam/RecipeUsageStatusView.vue:45`
   - Failing input: sem_list contains VeritySEM tools, but its usage DataFrame
     has the expected columns and no rows. The backend correctly returns
     `anchor_date=null` and an `equipments` row with zeroes for every tool.
     The `!data.anchor_date` branch hides the entire results template,
     including the equipment table, even when `?tab=equipment` is selected.
     Users cannot see the roster tools that the office requirement says to
     retain with zero usage.
   - Fix: show the empty-history message without gating the equipment table
     or roster counts on `anchor_date`. Keep the chart and recipe rankings
     conditional on history. Check the no-rows response as well as an idle
     tool alongside active tools.

3. **Every AMAT date preset requests one extra calendar day.**
   `frontend/app/components/ebeam/RecipeUsageStatusView.vue:235`
   - Failing input: with `anchor_date=2026-11-11` and `data_start` before
     November, select “Last 7 days”. The new preset passes `days=7` to
     `DateRangePopover.vue:135`, which subtracts seven days and emits
     `2026-11-04..2026-11-11`. The API includes both endpoints, so it sums
     eight days. “Last 14 days” likewise differs from the server's default
     14-day window and can change the totals when merely reselecting it.
   - Fix: in the new AMAT preset mapping, retain the label's day count but
     pass `days: days - 1` to the existing popover. This leaves Hitachi
     behaviour unchanged. Check the emitted inclusive range for 7 and 14 days.

4. **A missing usage date escapes normalization and corrupts the date bounds.**
   `backend/ebeam/recipe_usage/providers/office_example.py:122`
   - Failing input: a usage DataFrame contains a valid roster tool and recipe
     with `dt=pd.NaT`, plus a valid row dated `2026-11-10`. `_day()` turns
     NaT into `""`, but `_normalize()` retains that row because only the tool
     and recipe are checked. `build_status()` then returns `data_start=""`
     instead of a date or null, disabling the picker floor. Recipe detail
     also includes a daily point with `date=""`. With only missing dates,
     status returns `anchor_date=""` and the UI reports no history despite
     retained usage rows.
   - Fix: require a valid KST calendar date for usage rows at the adapter
     boundary; reject an invalid upstream date with a diagnostic bare
     `LookupError` rather than returning a successful, partial history.
     Add a NaT-date case that reaches shaping, not only a missing timestamp
     case. This is a defensive-input issue; the office notes explicitly say
     the current usage keys contain no nulls.

## Validation and limits

- Backend feature tests: **65 passed**, using the permitted Python executable,
  with bytecode and pytest cache writes disabled.
- Frontend `npm test`: **2,231 passed** with installed Node 24.13.0. The default
  Homebrew Node first failed to load `libllhttp.9.3.dylib`.
- Traced list grain folding, roster deduplication and fab scope, zero-fill,
  anchor selection, zero-denominator calculations, chart option updates,
  reactive fetch keys, and catalogue pagination before rendering. No further
  concrete defect was found in those paths or in the documented mock facts.
- Checked the shared Hitachi changes and their callers. The optional calendar
  floor and table metadata leave existing callers' defaults intact; the added
  identity tabs preserve the existing tat/align/meas mappings.
- No servers, browser session, real Redis, office adapter, lint/typecheck, or
  full backend suite were run. The Provision hash names and serialization
  assumptions still require the documented office verification. Source and
  Git state were left unchanged; only this report was written.

FIX FIRST

## Author 응답 (2026-11-12, commit 위 `fix(recipe-usage): Codex 리뷰 4건 반영`)

1. 수용. `FailIssueRankingTable` 에 선택적 `pinLast` (정렬 열 → 술어) 를 추가하고 그 경우에만
   `manualSorting` 을 켭니다. `fail_rate_ranked` 는 실제 비율을 담습니다. 브라우저에서
   7일 창으로 확인: 표본 부족 행(2/3, 66.7%)이 오름·내림 모두 마지막 행입니다.
2. 수용. 빈 상태는 `anchor_date` 도 없고 `equipments` 도 비었을 때만 보입니다.
3. 수용. AMAT 프리셋만 `days - 1`. 브라우저 확인: Last 7 days → 2026-11-05 ~ 2026-11-11.
4. 수용. `_normalize` 가 유효한 dt 가 없는 usage 행에 `LookupError` 를 던집니다. 테스트 추가.

게이트: backend recipe_usage 66 passed, ruff clean, frontend 2231 passed, typecheck·lint 오류 0.

## 2차 확인

`5583584b`와 Author 응답을 대조했습니다.

1. **resolved** — `FailIssueRankingTable.vue:209`의 `pinLast` 비교가 정렬 방향보다
   먼저 적용됩니다. AMAT Fail 호출부는 `low_sample`을 전달하며 `manualSorting`으로
   재정렬을 막습니다. 따라서 오름·내림 모두 표본 부족 행이 뒤로 가고, 페이지 분할도
   그 이후에 수행됩니다. 실제 비율 표시와 기본 Fail 건수 정렬도 유지됩니다.
2. **resolved** — `RecipeUsageStatusView.vue:46`은 이력과 장비가 모두 없을 때만
   빈 화면을 표시합니다. `anchor_date=null`이어도 명부 장비가 있으면 0실적 장비 표와
   전체 장비 수를 표시할 수 있습니다.
3. **resolved** — `RecipeUsageStatusView.vue:237`의 AMAT 프리셋만 `days - 1`을
   전달합니다. 11월 11일 기준 7일은 11월 5일부터이며, Hitachi 프리셋은 그대로입니다.
4. **open, 부분 해결 (should)** — `office_example.py:124`에서 NaT/None/NaN은
   실제 실행으로 `LookupError`가 발생함을 확인했습니다. 다만 날짜 유효성은 길이만
   검사합니다. 새로 확인한 입력 `dt='2026-02-30'`은 정규화를 통과한 뒤 기본 status의
   `_window()`에서 `ValueError`가 발생합니다. 라우트는 이 호출의 `WindowError`만
   처리하므로 upstream 502 대신 500이 됩니다. 실제 오피스 발생 사례는 아닙니다.
   수정: 정규화에서 `date.fromisoformat()`으로 달력 날짜를 검증하고 실패를 진단용
   bare `LookupError`로 변환합니다. 길이가 10인 잘못된 날짜도 테스트에 추가합니다.

Hitachi 회귀는 발견하지 못했습니다. `RecipeTatView.vue:161` 및
`FailIssueView.vue:216,242`는 `pinLast`를 전달하지 않으므로 `manualSorting=false`이고,
기존 숫자 비교·검색·페이지 분할·내보내기·`update:state` 경로가 유지됩니다.

재실행: backend **66 passed**, frontend **2,231 passed**입니다.
브라우저·실제 Redis·lint/typecheck는 재실행하지 않았습니다. 추가 소스 수정은 없습니다.

FIX FIRST

## Author 응답 2 (2026-11-12)

4. 수용. `_is_date()` 가 `date.fromisoformat` 으로 달력 날짜를 검증합니다. `2026-02-30` 사례를
   테스트에 추가했습니다 (backend recipe_usage 67 passed, ruff clean). 이것으로 open 항목 없음.
