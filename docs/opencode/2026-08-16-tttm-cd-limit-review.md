# oc-review — TTTM CD 한계 작업 (f47fcf05...4b0874c4)

- 일자: 2026-08-16
- 스킬: `oc-review` (2축 — Standards / Spec)
- 티어: `heavy` (glm-5.3). 근거: 16개 파일이며 `**/contracts.py` 라는
  escalation surface 를 건드립니다.
- 대상: `git diff f47fcf05...HEAD` — 커밋 4개
  (`5db142e4`, `e94ce425`, `d2f58f05`, `4b0874c4`)
- Standards 근거 문서: `CLAUDE.md`, `DESIGN.md`,
  `back_dev_home/ebeam/tttm/MIGRATION.md`, `docs/back-end/provider-selection.md`
- Spec: 별도 스펙이 없어 대화에서 확정된 요구사항을
  `.scratch/tttm-cd-limit/spec.md` 에 사용자 발언 그대로 기록한 뒤 그것을
  대상으로 삼았습니다. 구현에서 역산한 스펙이 아닙니다.
- 두 축 모두 exit 0 으로 정상 종료했습니다.

## Standards (glm-5.3, 원문)

> **Verdict: no HARD breaches.** All colors in touched Vue files go through
> `--sk-*` tokens (DESIGN.md ✓); `data.py`/dispatch untouched
> (provider-selection.md ✓); fabricated CDs covered by the blanket
> `OFFICE-VERIFY: every number here is fabricated`, the 1% ratio carries
> `user-confirmed 2026-08-16`, and the pairwise extension is marked
> `OFFICE-VERIFY` in MIGRATION.md; MIGRATION.md's "Edit ONLY
> `providers/office.py`" rule binds the office-migration task, and this is
> contract evolution with MIGRATION.md updated in lockstep — not a breach.
> `office_example.py` is a `NotImplementedError` stub, so no mock/office
> formula drift is possible yet.
>
> **JUDGEMENT findings:**
>
> 1. **Value-domain narrowing** (project smell; CLAUDE.md: "Copy every
>    confirmed property — … whether nulls appear"). The contract makes
>    `median_cd_nm` nullable and the client ships a whole assumed-CD path
>    (`"CD 미상 · 모니터 wafer {{ MONITOR_WAFER_CD_NM }} nm 가정"` in
>    PairMatrix, `cdBasis` assumed branch in FleetStatus), but the fixture
>    emits `32.4 / 31.8 / 68.0 / 15.1` — never a null CD on an occupied cell.
>    The only null is in the `available: false` empty payload, which renders no
>    cells. → add one occupied cell with `"median_cd_nm": null` so the assumed
>    path is exercised at home.
> 2. **Duplicated Code** — `(PM_BM_ACTION_LIMIT_RATIO * 100).toFixed(0)`
>    appears three times in PairMatrix.vue's template (header ×2, `:title` ×1),
>    while FleetStatus.vue extracted the identical expression into a `percent`
>    computed. → extract once in PairMatrix.
> 3. **Mysterious Name** — PairMatrix.vue:
>    `const indexOf = (cell: SkewCondition) => worstFractionOfLimit(...)` reads
>    as a position lookup (`Array.prototype.indexOf`) but returns a CD-relative
>    severity multiple. → `cdIndexOf` or `severityIndexOf`.
> 4. Minor (same file): `resolveNominalCd(cell.median_cd_nm).nm` is recomputed
>    in `thresholdOf`, `indexOf`, and `pairTitle` — three walks of the same
>    fallback per cell; resolve once per cell where `rankedCells` is built.
>
> Test coverage is otherwise strong: the contract tests pin band/median
> coherence, and the index-vs-nm reordering is tested on both engine and
> ranking sides.

## Spec (glm-5.3, 원문)

> ### (a) Missing / partly done
>
> - **R4 combination index — partly done.** The worst-fraction reduction exists
>   (`worstFractionOfLimit`, grouping `worst()`), but recipe-level combination
>   is only a code comment ("the recipe-level version is this function applied
>   one level up"). Covered by the spec's explicit deferral ("여러 recipe 를
>   동시에 불러오는 UI. 현재 picker 는 단일 recipe 입니다"), so no action forced
>   — but nothing user-visible combines recipes yet.
> - Otherwise R1–R3, R5, R6 are present: ratio 1% (`actionLimitNm`), CD-scaled
>   FleetStatus line, generic page via nullable `median_cd_nm`,
>   `tolerance_range.max` still 0.2, index drives sorting (`rankedCells`) and
>   `pickPrimary`.
>
> ### (b) Scope creep
>
> - **New office-adapter contract law.**
>   `test_median_cd_agrees_with_the_band_it_is_filed_under`
>   (back_dev_home/ebeam/tttm/tests/test_contract.py) mandates
>   median-inside-`cd_band`. Spec only says "CD 중앙값은 **MSR 의 CD
>   데이터**에서 옵니다" (R4); same-row-set is implied, but this adds an
>   enforceable invariant nobody quoted.
> - **`weakestPairSkew` redefinition.** Changed from max-nm to nm-of-worst-index
>   pair. Defensible under R6 ("N배화 판정·정렬에 실제로 반영해야 합니다"), but
>   it alters an existing reported metric beyond what R6 quotes.
> - **Non-positive-CD defense** (`resolveNominalCd` treating 0/−5 as missing)
>   plus its contract test — unrequested hardening.
>
> ### (c) Implemented but looks wrong
>
> - **The tolerance knob is now denominated in the fab's per-tool action
>   limit.** `toleranceIndexFromNm = fractionOfLimit(nm, 15)` divides the
>   pairwise knob by 1%-of-CD — the rule the spec assigns to one tool vs. median
>   (R1: "we manage the tools running inside +-0.15nm from median"). The
>   tolerance knob is a separate pairwise quantity, yet its per-cell threshold
>   is now `index × 1% × CD`. The diff itself concedes this ("장비쌍에 적용하는
>   것은 … 공장이 말한 바가 아닙니다", MIGRATION.md) — and then applies that
>   ratio to every pair judgment anyway (adjacency in `groupFromCells`,
>   `cellStyle` in PairMatrix, FleetMap's red rule).
> - **Consequence: R5's ceiling is only nominally kept.** Spec: "0.20 ceiling is
>   reasonable" / "tolerance 상한 0.20 nm 은 유지한다". The slider still stops at
>   0.2 nm, but effective tolerance is `nm × CD/15`: at the fixture's 68 nm cell
>   the default 0.05 nm knob becomes 0.227 nm — already past the 0.20 ceiling —
>   and knob-max becomes 0.907 nm. If R2 ("한계는 패턴 크기에 따라 커져야
>   한다") was meant for the management limit only, the knob rescale is
>   unasked-for; if it was meant for the knob too, R5 is effectively abandoned
>   above the monitor wafer. Either way one of the two spec lines is not honored
>   in behaviour.

## Claude 의 판단

### 동의하고 고친 것

Standards 1·2·3·4 는 코드를 직접 확인한 뒤 모두 사실로 확인되어 `aa28ac89` 에서
고쳤습니다.

- **null CD 경로가 죽어 있었다** — fixture 의 점유 셀 CD 는
  `[32.4, 31.8, 68.0]` 로, null 이 하나도 없었습니다. 즉 `resolveNominalCd` 의
  fallback 과 그것을 설명하는 화면 문구는 집에서 한 번도 실행되지 않고 사무실에서
  처음 돌 코드였습니다. 직전 보고에서 저 스스로 "assumed 분기는 브라우저에서
  확인하지 못했다"고 적었으므로, 이것은 알면서 남겨둔 구멍이었습니다.
  `bc3-X-lt25-e7` 셀을 `median_cd_nm: null` 로 추가했습니다.
- **중복 파생** — `PM_BM_ACTION_LIMIT_RATIO * 100` 이 PairMatrix 에 3회
  (`grep -c` 로 확인), 같은 식이 FleetStatus 에는 이미 `percent` computed 로
  추출되어 있었습니다. `resolveNominalCd` 도 셀당 3회 재계산되고 있었습니다.
  `RankedCell` 로 셀당 한 번만 해석하도록 바꿨습니다. 성능보다 중요한 이유는
  **세 곳이 서로 다른 CD 를 쓰는 일이 불가능해진다**는 점입니다.
- **`indexOf` 이름** — `Array.prototype.indexOf` 로 읽힙니다. `RankedCell.severity`
  필드로 대체했습니다.

### 동의하지 않는 것 (Spec (b) 3건)

- **band/median 계약 테스트가 scope creep 이라는 지적** — 기각합니다. 이 계약
  필드를 도입한 것이 이 diff 이므로, 그 필드의 불변식을 같이 넣는 것은 범위 밖이
  아니라 범위의 일부입니다. 게다가 overlay 가 escalation surface 를 정의한 이유가
  정확히 이것입니다 — 집의 테스트는 어느 쪽이든 통과하고, 틀리면 사무실에서
  드러납니다.
- **`weakestPairSkew` 재정의** — 유지합니다. 지수로 순위를 매기면서 nm 최대값을
  같이 보여주면 화면의 숫자가 그 정렬을 설명하지 못합니다. 커밋 메시지와
  contracts 주석에 재정의를 명시했습니다.
- **음수·0 CD 방어** — 유지합니다. 아무도 요청하지 않았다는 이유로 나눗셈
  가드를 빼는 것은 개선이 아닙니다. 3줄이고, 0 이면 한계가 무한대가 되어 모든
  장비를 조용히 통과시킵니다.

### 옳지만 제가 임의로 고칠 수 없는 것 — Spec (c)

**이 리뷰에서 가장 중요한 발견이며, 산술적으로 확인했습니다.**

| knob | index | CD 15 nm | CD 31.8 nm | CD 68 nm |
| --- | --- | --- | --- | --- |
| 0.05 nm | 0.333 | 0.050 nm | 0.106 nm | 0.227 nm |
| 0.20 nm | 1.333 | 0.200 nm | 0.424 nm | 0.907 nm |

즉 사용자가 명시적으로 유지하라고 한 0.20 nm 상한이 큰 패턴에서는 실효적으로
지켜지지 않습니다. 원인은 "ceiling" 이라는 단어가 대화에서 두 가지 대상에
쓰였다는 데 있습니다 — R5 는 `tolerance_range.max` 를, R2 는 PM/BM 관리 한계를
가리켰습니다. 저는 R2 의 확장을 knob 에도 적용했지만 그 선택을 밝히지 않았습니다.

두 해석 모두 자체적으로는 일관됩니다.

1. 0.20 nm 도 모니터 wafer 기준값이므로 같이 비례해야 한다 → 현재 구현
2. 0.20 nm 은 절대 상한이며 셀별 실효 tolerance 를 여기서 잘라야 한다

어느 쪽인지는 사용자 결정 사항이므로 코드를 다시 조용히 바꾸지 않고 질문했습니다.
현재 화면은 최소한 이 사실을 숨기지는 않습니다 — knob 캡션이
"CD 68 nm 셀에서는 0.227 nm" 라고 직접 말하고, 셀마다 "기준 N nm" 을 표시합니다.

#### 결론 (2026-08-16, 사용자 확정)

> "0.20 is a monitor wafer figure, let it scale"

**해석 1 채택.** 동작 변경은 없습니다 — 구현이 이미 그 해석이었습니다. 바꾼 것은
그 사실이 기록되지 않아 다음 사람이 "0.20 을 넘겼으니 버그"라고 읽을 수 있었던
자리들입니다.

| 자리 | 갱신 내용 |
| --- | --- |
| `contracts.py` `ToleranceRange` | docstring 신설 — 이 nm 은 모니터 wafer 기준값이며 클라이언트가 셀 CD 로 환산한다는 것, 그리고 knob max 의 실효값 표 |
| `MIGRATION.md` | office adapter 용 절 신설 — `max` 를 절대 상한으로 읽고 0.20 에서 자르는 "수정"이 바로 기각된 동작임을 명시 |
| `providers/mock.py` | 0.24 nm 짝이 "0.20 상한 초과"라던 설명이 이제 거짓이므로 정정 (knob 눈금의 약 54% 구간에서 red, 전체 travel 에서는 통과) |
| `.scratch/tttm-cd-limit/spec.md` | R7 로 확정 기록 |

`mock.py` 정정이 이 결정의 실제 부작용입니다. 예전 문구는 "full travel 에서
실패하는 짝이 하나 있어야 tolerance 컨트롤에 negative state 가 보인다"였는데,
상한이 함께 비례하면 그 짝은 full travel 에서 통과합니다. 데이터를 올리는 대신
문구를 고쳤습니다 — 0.424 nm 를 넘기는 짝은 자기 PM/BM 한계(0.318 nm)도 넘기게
되어, 바로 다음 bullet 이 가르치려는 "tolerance ≠ action limit" 대비가 무너지기
때문입니다.

### 두 축이 모두 놓친 것

- `.scratch/tttm-cd-limit/spec.md` 는 이 리뷰를 위해 방금 만든 문서입니다.
  대화 발언을 그대로 옮겼을 뿐이지만, 스펙이 리뷰 대상보다 나중에 쓰였다는 점은
  독자가 알아야 합니다.
- `../skewnono-tttm-tools` worktree 가 `d2f58f05` 에 남아 있습니다. 다른 세션의
  것으로 보여 건드리지 않았으나, 이 작업이 `GroupCell` 과 컴포넌트 prop 3개를
  바꿨으므로 그 세션이 병합할 때 충돌할 수 있습니다.

## 축별 요약

| 축 | 발견 수 | 최악 항목 |
| --- | --- | --- |
| Standards | HARD 0건 · JUDGEMENT 4건 | null CD 경로가 집에서 실행되지 않음 (고침) |
| Spec | 6건 (미완 1 · scope creep 3 · 오구현 2) | 0.20 nm 상한이 실효적으로 지켜지지 않음 → 2026-08-16 사용자 확정으로 해소 (비례가 맞음, 문서만 갱신) |
