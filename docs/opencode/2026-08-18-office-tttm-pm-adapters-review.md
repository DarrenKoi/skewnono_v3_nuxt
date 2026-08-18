# oc-review — tttm · pm_planning office 어댑터 구현

- 실행일: 2026-08-18
- 스킬: `oc-review`
- 티어: `heavy` (`glm-5.3`, variant `high`)
- 고정점: `main` (`8150a214`) → `f50fbcf9`
- 대상: 8개 파일, +3,079 / −31
- 티어 근거: `**/providers/`, `back_dev_home/_runtime/`, office DB 접근을 동시에
  건드립니다. 세 곳 모두 오버레이의 escalation surface 이며, 집의 테스트 스위트는
  어느 쪽으로든 통과하므로 크기와 무관하게 상위 티어를 씁니다.

## 표준 근거로 삼은 문서

`CLAUDE.md`, `docs/back-end/provider-selection.md`,
`back_dev_home/ebeam/{tttm,pm_planning}/MIGRATION.md`,
`docs/datatables/README.md` 및 개별 스키마 파일,
`back_dev_home/ebeam/hardware/providers/bsm/office_example.py`(하우스 스타일 기준).

## 스펙으로 삼은 문서

`.scratch/` 에 해당 이슈가 없어, 두 feature 의 `MIGRATION.md` 와
`docs/research/2026-08-16-skew-tttm-feasibility.md` 를 스펙으로 지정했습니다.
셋 다 저장소 안에 있고 어댑터가 만족해야 하는 요구사항을 실제로 기술하므로,
diff 에서 역으로 스펙을 만들어 낸 경우가 아닙니다.

## Standards 축 (exit 0) — 모델 원문

> **Review: office adapters for tttm + pm_planning (f50fbcf9)**
>
> **What checks out** (DB-focus list): `.keyword` sub-fields used on every
> exact-match/aggregation field (`msr_check/recipe_name/class_name/full_name/eqp_id/fab_name.keyword`,
> `type.keyword`, `fdc_category.keyword`) per meas_hist.txt §주의사항1,
> hardware_beam_shape.txt, hardware_bm_pm.txt. `terms` size = `len(fleet)` is
> query-scoped and pre-bounded (`_MAX_TOOLS`). `recent_runs` detects truncation
> via `doc_count > len(hits)` and surfaces it (`RunSet.truncated`, `raw`). MinIO
> keys are PREFIX-relative with bucket from `minio_config.py` (`pkl.lstrip("/")`,
> `hitachi_sem/...`) per msr_file_pickle.txt / hardware_mdc_setting.txt. Archive
> dates are discovered, not computed (SCE rule). MDC empty reads warn per
> hardware_mdc_setting.txt's abnormal-empty rule. Unknowns are marked
> `OFFICE-VERIFY`/`user-confirmed`.
>
> **HARD findings**
>
> 1. **Timezone defect, `_epoch_history`** (pm_planning office_example.py):
>    `opened = datetime.combine(change.on, …).replace(tzinfo=KST)` is compared
>    against BSM `at` values from `parse_dt`, which labels the stored offset-less
>    KST wall clock as **UTC** (`_office_search.py:118`). Per
>    `_office_meas_hist.py`'s own convention (all comparisons on KST-as-UTC),
>    `opened` must be UTC-labelled. As written, wall-clock readings 15:00–24:00
>    the day *before* the epoch count as "after" the change, and the 7-day window
>    runs 9 h long. The test doubles carry `tzinfo=KST`, so the home suite
>    structurally cannot catch it.
> 2. **Silent truncation, `_bsm_by_tool`**: `top_hits(size=BSM_DOCS_PER_TOOL=40)`
>    with no `doc_count` check. hardware_beam_shape.txt documents ~3 runs/day over
>    a 30-day window (~90 docs > 40) and states "상한에 닿으면 조용히 자르지 않고
>    감지합니다". Consequence: `_epoch_history`'s week-after-the-change average
>    silently falls back to `after[0]` — a ~day-13 level reported as the
>    epoch-opening level. `recent_runs` implements the detection correctly; the
>    pattern was not applied here.
>
> **JUDGEMENT findings**
>
> 3. **Same smell, lower risk**: `_office_bm_pm.maintenance_events`
>    `_DOCS_PER_TOOL=24` top_hits, no `doc_count` check — contradicts
>    hardware_bm_pm.txt's "잘린 이력을 조용히 보여주지 않고" (unlikely at 24/60
>    days, but silent).
> 4. **Fragile cross-index comparison**: `_prev_post_delta` lexically compares
>    `run.at.isoformat()` (carries `+00:00`) against the raw stored `equp_dt`
>    string (offset-less; tz UNVERIFIED per the module's own docstring). Parse
>    both sides instead.
> 5. **Misleading empty**: tttm's empty-cells summary always blames the axis;
>    when `parameter` matches nothing (`dropped["no_parameter"] > 0`,
>    `no_axis == 0`) the same summary renders and the `_LOG.warning` never fires.
> 6. **Duplicated Code**: `_as_float` is byte-identical in `_office_msr_cd.py`
>    and pm_planning's `office_example.py`.
> 7. **Speculative Generality**: `_office_mdc.latest_snapshot` is exported with
>    no caller in this change.
> 8. **Mysterious (wrong) doc**: `recent_runs` docstring says "newest first"; it
>    sorts ascending. pm_planning depends on oldest-first — code right, doc wrong.
> 9. **Error-handling asymmetry**: `maintenance_events` degrades to `{}` on
>    unreadable index, but `snapshot_on` re-raises non-404 MinIO failures and
>    502s the whole page. Defensible (MDC is load-bearing here) but the choice is
>    unstated; hardware_mdc_setting.txt says the tab shouldn't die over it.

## Spec 축 (exit 0) — 모델 원문

> **(a) Missing / partly done**
>
> 1. **No "성질" answer — the page's own question.** Feasibility §7.3: "장비 그룹
>    TTTM 페이지… 답하는 질문 **성질** — 그 차이가 재현되는가"; §2.3 requires the
>    국소선형추세 filter and "σ²_proc / (σ²_proc + σ²_obs) 가 곧 '일관 대 랜덤'
>    비율". The adapter computes only magnitudes; no filter, no consistency ratio,
>    no prediction interval. The docstring defers the rollup (§5.1) but the filter
>    itself (§7.7 item 6) is absent with no seam.
> 2. **Epoch-wise connectivity only partly.** §3.5: "연결성 검사는 epoch 단위로
>    하고, 연결 성분과 경로 길이를 화면에 드러냅니다. 경로 길이가 곧 신뢰도의
>    근거입니다." Cells are epoch-keyed (good), but no components/path lengths are
>    surfaced, and `_fleet_today`/`_trend`/`_corroboration` pool runs across MDC
>    boundaries — rule 3 is applied only inside `_cells`.
> 3. **No uncertainty anywhere.** §2.4: "군집-강건(cluster-robust) 표준오차를 써야
>    합니다"; §4 flags "`confidence` 가 장식입니다". Run-count-based confidence is
>    still decoration; §4's fallback ("브리지 셀을 그룹화에서 빼고") not taken.
> 4. **MDC 역적용 absent** (§2.5). Permitted pre-verification ("역적용을 켜지
>    않습니다"), but no seam, and the "경계에 점프가 남으면… 로그에 남겨야 합니다"
>    signal check is missing.
> 5. **pm `epoch_history` effectively always empty.** MIGRATION mock: "3 past MDC
>    epoch points, each 60+ days apart"; office reads only `WINDOW_DAYS = 30`, and
>    MDC changes are rare — a tool will almost never show any point.
>
> **(b) Scope creep**
>
> - `"raw"` diagnostics dict on the tttm payload (contract `NotRequired`, but
>   nobody asked).
> - `__main__` staged CLI diagnostics in both providers; two new env knobs
>   (`SKEWNONO_CD_MONITOR_RECIPE`, `SKEWNONO_AXIS_PARAM_MAP`) plus `.env.example`
>   and `_runtime/data_provider.py` dependency registration — three tracked shared
>   modules outside the "edit ONLY `providers/office.py`" rule's letter, against
>   its spirit.
> - pm's invented fleet-relative BSM band (median±3·MAD) and derived ±1% CD spec —
>   replacements for sources the spec never provided (documented, but new
>   behaviour).
>
> **(c) Implemented but looks wrong**
>
> 1. **Parameter pooling breaks cd_band meaning.** `_observations`/`_cell_values`
>    pool *all* parameters resolving to an axis into one run median. §3.2: "한 실행
>    안에 서로 다른 공칭 CD 를 가진 parameter 가 여러 개 들어 있습니다" — a median
>    straddling 31 nm and 68 nm features lands in an arbitrary band; the
>    same-row-set law is satisfied formally while the band is a mixture.
> 2. **`_fleet_today` folds tiers.** Comment: "One block, both tiers folded" —
>    bridged estimates enter with equal standing, the exact §4 failure ("2-hop
>    브리지 추정치가 직접 측정과 동일한 자격으로 clique 에 들어갑니다").
> 3. **`_prev_post_delta` lexicographic ISO compare** between tz-aware KST strings
>    and `post_pm_at` whose timezone the module itself calls UNVERIFIED — "A stored
>    `Z` suffix slides every window by nine hours."
> 4. Correct on the headline laws: run-as-unit (§2.4), median-not-mean,
>    zero-diagonal symmetric matrices, None-not-zero (`median_cd_nm`, matrix
>    cells), echo of fab/recipe/parameter on every branch, unique `eqp_id`,
>    `eqp_model_cd` present, `tolerance_range` max kept at 0.20 and documented as
>    monitor-wafer-relative.

## Claude 의 판단

인용된 근거를 모두 열어 확인했습니다. `_office_search.py:118` 의 `parse_dt` 는
실제로 naive 문자열을 UTC 로 라벨링하고, `hardware_beam_shape.txt` 53–55행과
`hardware_bm_pm.txt` 214행은 모델이 인용한 문장을 그대로 담고 있으며,
`latest_snapshot` 은 호출자가 없습니다. 잘못 인용된 항목은 없었습니다.

### 반영한 지적

| 항목 | 조치 |
| --- | --- |
| Standards 1 (시간대) | `_epoch_history` 의 경계를 UTC 라벨로 고쳤습니다. 테스트 double 도 UTC 라벨로 바꿔야 잡히므로 함께 고쳤습니다 |
| Standards 2 | `BSM_DOCS_PER_TOOL` 40 → 200, 그리고 `doc_count` 절단 감지를 추가했습니다 |
| Standards 3 | `maintenance_events` 에 절단 감지를 추가했습니다 |
| Standards 4 / Spec (c)3 | 양쪽을 파싱해 비교합니다 |
| Standards 5 | 빈 grid 의 세 가지 원인을 구분하는 `_empty_cells_summary` 를 추가했습니다 |
| Standards 6 | `as_float` 을 `_office_msr_cd` 의 공개 함수로 올리고 중복을 제거했습니다 |
| Standards 7 | `latest_snapshot` 과 그에 딸린 Redis 경로를 삭제했습니다 |
| Standards 8 | docstring 을 실제 정렬(oldest-first)에 맞췄습니다 |
| Standards 9 | 비대칭을 유지하되 `snapshot_on` docstring 에 이유를 적었습니다 — hardware 탭은 MDC 값을 **표시**하지만 여기서는 **어떤 측정끼리 비교해도 되는지**를 결정하므로, 보이지 않는 epoch 경계를 넘어 pool 하면 없는 값이 아니라 틀린 값이 나옵니다 |
| Spec (a)5 | MDC epoch 조회 창을 측정 창과 분리해 `EPOCH_LOOKBACK_DAYS = 240` 으로 두었습니다 |
| Spec (c)1 | observation 의 grain 을 (run × parameter) 로 바꿨습니다. 대비 키도 `recipe∥parameter` 입니다 |
| Spec (c)2 | `_fleet_today` 를 direct 쌍만 채우도록 바꿨습니다. 브리지 쌍은 null 입니다 |

각 수정마다 회귀 테스트를 붙였고, 수정 전 코드에서 실제로 실패하는지 되돌려
확인했습니다(시간대 건은 7.55 vs 8.00 으로 아홉 시간 누수가 그대로 드러납니다).

### 동의하지 않는 지적

- **Spec (b) `raw`·`__main__`·공유 모듈**: `raw` 는 계약이 `NotRequired` 로
  이미 마련해 둔 자리이고, staged `__main__` 진단은 `bsm`·`mdc` office 어댑터가
  이미 쓰는 하우스 패턴입니다. "`providers/office.py` 만 고칠 것" 규칙은 사무실에서
  swap 하는 사람에게 하는 말이지, 집에서 템플릿을 만드는 작업에 대한 제약이
  아닙니다. 공유 모듈을 tracked 로 둔 것은 오히려 `office.py` 가 낡는 문제
  (`CLAUDE.md` 의 STALE office.py 절)를 줄입니다.
- **Spec (b) BSM 밴드·CD spec**: 창작이 아니라 필수 계약 필드를 채울 유일한
  방법입니다. mock 의 절대 밴드(noise 6.65–6.95)를 그대로 쓰면 실데이터
  (`Ave. Noise` 6.277)에서 팹 전체가 hold 로 잠깁니다.
- **Spec (a)1·3 (일관성 필터·불확도)**: 옳은 지적이지만 `TttmCheckPayload` 에
  실을 자리가 없습니다. 계약 변경은 `MIGRATION.md` 가 금지하며, feasibility 문서
  §4 스스로 "계약 변경 비용이 듭니다" 라고 적고 있습니다. 야간 rollup(§5.1)과 함께
  다뤄야 할 별도 작업입니다.
- **Spec (a)2 (`_trend` 가 경계를 넘어 pool)**: `_trend` 는 날짜마다 그 날의
  recipe 집합으로 따로 센터링하므로 경계는 계단으로 나타나고, `epoch_markers` 가
  바로 그 지점을 표시합니다. `_fleet_today` 는 하루치이므로 경계를 넘을 수
  없고, `_corroboration` 은 skew 가 아니라 recipe 집합의 겹침입니다.

### 양쪽 축이 놓친 것

`_trend` 는 `TREND_DAYS`(30) × 장비 수만큼 점을 만듭니다. 18대 fab 이면 540점이며,
`recent_runs` 의 `per_tool` 상한 때문에 실제로는 그보다 적습니다. 다만 상한을
올리면 payload 가 조용히 커지는 구조라, rollup 작업 때 함께 봐야 합니다.


## 2차: Claude 자체 `/code-review low` (같은 고정점)

opencode 지적을 반영한 코드를 대상으로, 같은 두 축을 Claude 의 서브에이전트로
한 번 더 돌렸습니다. **1차가 놓친 결함 6건이 더 나왔습니다.** 두 번 돌린 값어치가
있었다는 뜻이므로, 다음에도 외부 모델 1회로 끝내지 않는 편이 좋겠습니다.

### Standards 축

| 지적 | 판정 | 조치 |
| --- | --- | --- |
| ruff 게이트가 red (`B905`, `tests/…:238`) | **맞습니다** | `ruff check back_dev_home/` 만 돌리고 `tests/` 를 빼먹었습니다. `strict=True` 추가, 이후 저장소 전체 `ruff check .` clean |
| `docs/back-end/provider-selection.md` §7 이 stale | **맞습니다** | `_OFFICE_DEPENDENCIES` 에 두 줄을 넣고 문서 표는 그대로 뒀습니다. 표에 2행 추가 + pm-tune 조인이 왜 더 나쁜지 서술 추가 |
| "office DB 지식은 두 곳에" 규칙 미이행 | **맞습니다** | `msr_file_pickle.txt`·`hardware_mdc_setting.txt`·`meas_hist.txt` 에 소비 규약 절을 추가하고, `README.md` 의 소스 없음 목록에 3건을 등재했으며, 양쪽 `mock.py` docstring 에 대응 사실을 적었습니다 |
| 두 어댑터에 `OFFICE-VERIFY` 블록이 0건 | **맞습니다** | `bsm/office_example.py` 형식대로 각각 6항목·5항목 추가 |
| 두 `MIGRATION.md` 미수정 | **맞습니다** | `<!-- OFFICE: … -->` placeholder 를 실제 소스 표로 대체하고, 환경변수 절과 "빈 grid 읽는 순서" 표를 추가 |
| mock 은 `BC1`, office 는 `500V` | **맞습니다** | 실제 어휘는 전압 쪽입니다(MDC 키). mock 이 틀렸으나 fixture·프론트 테스트로 파급되므로 이번에는 **표시만** 했습니다 — mock docstring 의 OFFICE-VERIFY |
| `TOLERANCE_RANGE` 중복 | **맞습니다** | `contracts.py` 로 올리고 mock·office 양쪽이 import |
| 테스트 double 의 value-domain 협소 | **맞습니다** | `None` CD 와 `vac=0` 을 내보내는 케이스 추가 |

### Spec 축 — 여기서 실제 버그 4건이 더 나왔습니다

| 지적 | 판정 | 조치 |
| --- | --- | --- |
| (c1) `confidence` 가 실행이 아니라 **행**을 셈 | **버그** | 한 실행이 feature 6개를 재면 혼자 `High` 가 됩니다. 추정기는 유사반복을 피하는데 그것을 보증하는 숫자가 다시 끌어들이고 있었습니다. `_Observation` 에 `msr` 을 실어 distinct run 을 셉니다 |
| (c2) `fleet_today.median_cd_nm` 이 패턴 크기를 섞음 | **버그** | 계약이 "하루가 한 가지 패턴 크기일 때만 뜻이 있다" 고 적어 둔 값입니다. 그날 관측이 cd_band 두 개 이상에 걸치면 `None` 을 돌려주고 클라이언트의 모니터 wafer fallback 으로 보냅니다 |
| (c3) 대역 경계에서 반올림이 계약 법칙을 깸 | **버그** | 24.9997 은 `<25` 로 분류된 뒤 25.0 으로 반올림되어 `low <= median < high` 를 위반합니다. 관측을 만들 때 먼저 반올림하고 그 값으로 분류합니다 |
| (a1) 끊어진 성분끼리도 `predicted` 스큐를 냄 | **버그** | 서로 다른 연결 성분의 두 장비는 각자 다른 기준점에 센터링되므로 그 차이는 인공물입니다. `_Offsets.component` 를 union-find 로 계산해 같은 성분일 때만 브리지를 냅니다 (feasibility 3.5) |
| (a2) 부분 pooling(τ² 축소·공변량) 없음 | 맞지만 **보류** | 추정기 설계 자체의 확장이며 계약에 실을 자리가 없습니다. 야간 rollup(5.1) 과 함께 다룰 작업입니다 |
| (b) gate 재정의가 "조용하다" | 일부 수용 | module docstring 에만 있던 것을 `MIGRATION.md` 의 표와 `datatables/README.md` 로 끌어올렸습니다 |

네 버그 모두 회귀 테스트를 붙이고, 수정을 되돌려 실제로 실패하는지 확인했습니다.

## 최종 상태

- `ruff check .` clean (저장소 전체)
- `pytest -q` — 3,363 passed, 16 skipped
- `tests/test_office_tttm_pm_planning.py` — 36 tests, 사무실 접속 없이 두 어댑터의
  계산을 검증합니다
