# tttm / pm-tune 수집 기간(window_weeks) — opencode oc-review 기록

- Run date: 2026-08-26
- Skill: oc-review
- Model: opencode-go/glm-5.3 variant=high (tier=heavy)
- Target: `git diff 310128c1...HEAD` 중 `fcd8b5eb`(창 선택 1~3주, 기본 3) + `45146de9`(선택지 1~4주, 기본 2). 같은 범위의 `f40e05c1`·`e9fecb6b`·`7e41731b`(다른 세션의 타이포그래피 수정)는 범위 밖으로 명시했습니다.
- Standards 출처: `CLAUDE.md`, `DESIGN.md`, `back_dev_home/ebeam/tttm/MIGRATION.md`, `back_dev_home/ebeam/pm_planning/MIGRATION.md`, `docs/back-end/provider-selection.md`
- Spec: `.scratch/window-weeks/spec.md` (사용자 요청 원문 두 건 + 구현자 가정)
- Elapsed: standards 279s · spec 194s · Session: ses_fc3454f2dffe8ldU9bse9gf7Ti / ses_fc3454f40ffe0tofbY3KKn3WC1

## 모델이 말한 것 — Standards 축 (원문 그대로)

Fixture diffs are key re-sorting; skipping those. Let me look at the code hunks.
## Review: fcd8b5eb + 45146de9 (window_weeks axis, tttm + pm_planning)

**HARD findings: none.** Additive contract changes only; response shapes preserved; env swap stays in `data.py` (positional/undefaulted, per convention); `window_days` lives in one shared module both providers import, so no formula drift there; `windowWeeks` persists via `useTttmSettings` → `usePersistedState` (no hand-rolled localStorage); `ScopeWindow.vue` uses `--sk-*` tokens; both MIGRATION.md files and DESIGN.md were updated in the same commits, including the default 3→2 change (stale "widest choice is the default" test comment also fixed).

**JUDGEMENT findings:**

1. **Unmarked office assumption** — `tttm/providers/office_example.py`: *"the fleet check is a daily monitor run, so 10/week is a week's worth with slack"* (and the same claim underpinning `RUNS_PER_TOOL_PER_WEEK = 8` in pm_planning). `docs/datatables/hitachi/meas_hist.txt` records CD_MONITOR recipes as "주기적으로 도는 일반 측정" (user-confirmed 2026-08-18) — periodic, not daily. The new per-week caps quantify an unconfirmed run frequency, and the frequency claim was not added to the module's OFFICE-VERIFY list nor the doc. → mark the daily-frequency assumption `OFFICE-VERIFY` (or cite a confirmation); consequence is mild since it's a cap, not a formula.

2. **Duplicated Code (cross-language)** — `WINDOW_WEEKS_CHOICES`/`DEFAULT_WINDOW_WEEKS` in `_analysis_window.py` mirrored as `WINDOW_WEEKS`/`DEFAULT_WINDOW_WEEKS` in `utils/analysisWindow.ts`. Commit 2 itself demonstrates the hazard ("두 곳이 같은 값을 들어야 하므로 함께 바꿉니다"). Each suite pins its own side; nothing ties them, so drift surfaces only as runtime 400s or silent normalize-to-default. → acceptable, but a one-line comment in each file naming its twin (the TS file has one; the Python file does not) or a shared-source test would close it.

3. **Duplicated Code (minor)** — the `cadence` computed and the `#window` slot block are byte-identical in `TttmView.vue` and `PmTuneView.vue`. Follows the pages' pre-existing `asOf` duplication pattern, so arguably the house style; noting for the record.

4. **Value-domain note, suppressed** — the pm_planning mock is an echo-only no-op for `window_weeks` (no idle-tool dropout at home), a mock/office divergence — but it is explicitly documented as deliberate in the mock docstring and MIGRATION.md, so the repo's rationale overrides the baseline smell.

Otherwise clean; the test coverage (route refusal, lookback+cap moving together per choice, echo on every unavailable branch) is unusually thorough.

## 모델이 말한 것 — Spec 축 (원문 그대로)

## Spec compliance — window-weeks change (fcd8b5eb, 45146de9)

**(a) Missing / partly done** — none. All five interpretation points check out: choices 1|2|3|4 with default 2 in both `_analysis_window.py` (`WINDOW_WEEKS_CHOICES = (1, 2, 3, 4)`, `DEFAULT_WINDOW_WEEKS = 2`) and `analysisWindow.ts:9-11`; 400 rejection of out-of-range values (`resolve_window_weeks` → `bad_window_weeks_response`, no clamping); one shared setting (`useTttmSettings` `windowWeeks` in the shared scope, both pages read/write it); office run cap scales with window (`runs_per_tool = RUNS_PER_TOOL_PER_WEEK × weeks` in both office adapters); recipe picker uses the same window (`/tttm/recipes` reads `window_weeks`, frontend refetches under `watch: [windowWeeks]`).

**(b) Scope creep**
1. **tttm's separate 30-day trend cut-off removed** ("tttm 의 별도 30일 trend cut-off 는 창 자체로 대체했습니다", fcd8b5eb body). No spec line asks for this; the spec's targets are the gather window and run cap. At 1주 the trend now shows 7 days where it showed 30 before — a visible narrowing beyond the spec's "창을 넓히면 실제로 더 많은 run 이 모여야 합니다".
2. Minor/internal (defensible, noting for completeness): LRU resize 768→2048, `unavailable_payload` keyword-only refactor, mock trend re-spanning. All support infra, not user-observable features.

**(c) Implemented but looks wrong**
1. **pm_planning BSM readings and PM events are now bounded by the window** — previously `start = anchor - timedelta(days=WINDOW_DAYS)` (30 days) fed both `_bsm_by_tool(...)` and `maintenance_events(...)` (old office_example.py:599,615,617); now that same `start` is `window_days(window_weeks)` = 7–28 days. The spec's complaint was "1 week window is too short. let's enlarge it", and line 20 says widening must gather more — but at the default 2주, and at every choice except none, pm-tune's BSM/PM evidence *shrinks* from 30 days to ≤28. Even 4주 (28일) never restores the old span. If "one span, one label" was intended to cover BSM/PM events, the spec doesn't say so — line 13-15 frames the problem as runs and run caps only. This deserves at least a spec-line or OFFICE-VERIFY note; MDC epochs got exactly such a deliberate carve-out, BSM/PM did not.

Everything else (contracts echo on all unavailable branches, cadence from payload echo, tests updated "4"→"5", docs) is consistent with the spec.

## 판정

인용을 모두 열어 본 뒤의 판정입니다.

| 축 | 항목 | 판정 | 근거 |
| --- | --- | --- | --- |
| Standards | 1. 일일 monitor run 가정 미표기 | **수용** | `docs/datatables/hitachi/meas_hist.txt:311` 은 CD_MONITOR 를 "주기적으로 도는 일반 측정" 이라고만 합니다. "daily" 는 구현자의 가정이었습니다. 두 office adapter 의 상한 주석에 `OFFICE-VERIFY` 를 달았습니다. |
| Standards | 2. Python/TS 상수 쌍둥이 | **수용** | TS 쪽만 짝을 명시하고 있었습니다. `_analysis_window.py` 에 짝 파일과 drift 의 증상을 적었습니다. 기계적 결합(공유 소스 테스트)은 두지 않습니다 — 두 언어 사이에 한 줄 상수를 위해 빌드 단계를 넣을 가치가 없습니다. |
| Standards | 3. 두 view 의 `cadence`·slot 중복 | **기각** | `asOf`·`metaStats` 가 이미 같은 방식으로 두 view 에 있습니다. 모델도 "house style" 로 인정했습니다. |
| Standards | 4. pm mock 의 echo-only | (모델이 스스로 억제) | 동의합니다. mock docstring 과 MIGRATION.md 에 의도를 적어 두었습니다. |
| Spec | (b)1. tttm 30일 trend cut-off 제거가 scope creep | **절반 기각** | 사무실에서는 예전 trend 도 30일이 아니었습니다 — 관측치가 장비당 10 run 에서 왔으므로 일일 측정 장비면 열흘 남짓이었고, 모델은 상수(`TREND_DAYS = 30`)를 읽고 데이터 흐름을 읽지 않았습니다. 창이 28일 이하인 지금 30일 cut-off 는 절대 작동하지 않는 죽은 코드라 제거가 맞습니다. 다만 **집(mock)에서는** 5주 간격 점(28일)이 1주 창에서 7일로 줄어 보이는 것은 사실입니다 — 이는 mock 이 office 의 결(장비·일 당 한 점)로 바뀐 결과이며 의도한 것입니다. |
| Spec | (c)1. PM 이벤트를 창으로 자른 것 | **수용 — 실질적 발견** | 예전 코드(`310128c1`)에서 `start`(30일)가 runs·BSM·`maintenance_events` 를 모두 먹였고, 창 도입 후 `start` 가 7~28일이 되면서 PM 이벤트도 함께 잘렸습니다. 기본 2주에서 3주 전 PM 은 `post_pm_at=None` 이 되고 `prev_post_delta` 도 사라져 pm-tune 의 "PM 직후 장비" 기본 선택이 바뀝니다. 스펙은 run 과 run 상한만 말했습니다. `PM_LOOKBACK_DAYS = 30`(예전 창이 주던 폭)으로 분리해 예전 동작을 되돌리고, 창 양끝에서 lookback 이 창과 무관함을 테스트로 고정했습니다. BSM 은 CD 와 같은 "현재 읽기" 이므로 창에 둡니다. |

## 후속

- 수용한 세 건을 적용한 commit: 이 기록과 같은 commit 입니다.
- 사무실에서 `pm_planning`·`tttm` 의 `office.py` 는 어제 변경과 함께 다시 cp 해야 합니다.
