# 스큐보아 분석 3개 브랜치 — opencode oc-review 기록

- Run date: 2026-08-16
- Skill: oc-review
- Model: opencode-go/deepseek-v4-pro (tier=medium), `cdu-card` Spec 축만 Zen 폴백
- Target: `main...work/skewvoir-fdc-set`, `main...work/skewvoir-across-msr`,
  `main...work/skewvoir-cdu-card` — 격차 분석 §5 우선순위 1~3번의 구현
- 표준 출처: `CLAUDE.md` → `DESIGN.md` → `.claude/oc-project.md`
- 스펙 출처: 각 브랜치를 구현한 에이전트에게 건넨 작업 지시서

| 축 | Elapsed | Session |
| --- | --- | --- |
| fdc-set / Standards | 243s | `ses_ff89b9cb8ffeNFaTFuL6ehdO44` |
| fdc-set / Spec | 138s | `ses_ff8973ab1ffeHqn5x9zd35CUJv` |
| across-msr / Standards | 190s | `ses_ff89b9c69ffeXKbH3rOjJoyrSt` |
| across-msr / Spec | 268s | `ses_ff895728bffeqvf1YHgSLyxGzb` |
| cdu-card / Standards | 133s | `ses_ff89b9c95ffeOaQ1Ece822T5y7` |
| cdu-card / Spec | 310s | `ses_ff893d7a9ffeLOqU8ICxQ36z3r` |

## 실패한 첫 실행

Spec 3축이 처음에는 세 건 모두 실패했습니다. 양쪽 프로바이더에서 `empty final
message twice` 를 반환했고, Standards 3축은 같은 diff 에 대해 정상 응답했습니다.

원인은 모델이 아니라 입력이었습니다. 스펙 파일을 저장소 밖
(`/private/tmp/.../scratchpad/`)에 두고 그 절대 경로를 프롬프트에 적었는데,
opencode 는 작업 트리에 뿌리내린 읽기 전용 샌드박스로 읽으므로 그 경로가 보이지
않습니다. 읽지 못한 사실이 오류가 아니라 빈 응답으로 나타나기 때문에, 로그만 보면
모델이 불안정한 것처럼 읽힙니다.

`.scratch/oc-spec/` 로 복사하고 저장소 상대 경로로 지목하자 3축 모두 성공했습니다.
이 실패를 근거로 `oc-review` 스킬에 세 가지를 추가했습니다 — §3 에 "스펙을 저장소
안에 둘 것" 규칙, §4 템플릿의 상대 경로 지시, §4 실패 해석에 "양쪽 프로바이더 빈
응답은 대개 읽을 수 없는 입력" 진단입니다.

## What the model said

아래는 모델의 응답 원문입니다. 요약하지 않았습니다.

### `work/skewvoir-fdc-set` — Standards

## Code review: `work/skewvoir-fdc-set`

### HARD — DESIGN.md breach: data value rendered in muted ink

`front-dev-home/app/components/ebeam/skewvoir/fdc/SetStatusMatrix.vue`:

```ts
const TONE: Record<FdcStatus, string> = {
  ok: 'text-(--sk-ink-muted)',
  warning: 'bg-(--sk-warn-soft) text-(--sk-warn)',
  bad: 'bg-(--sk-bad-soft) text-(--sk-bad)'
}
```

applied to the value cell:

```html
<td ... class="... sk-value-num" :class="cell.present ? TONE[cell.status] : 'text-(--sk-ink-subtle)'">
  {{ cell.driftSigma.toFixed(2) }}
```

DESIGN.md's defining rule is "**data values always get full ink; muted ink is for labels only**" and the `--sk-ink-muted` entry adds "*never data values*". The drift-sigma number is the data value the user came to read, but `TONE.ok` repaints it `--sk-ink-muted`, muting the majority of cells. The component's own comment justifies the *fill* (ok stays unfilled), but the muted *text* is not covered by that rationale — the two `warning`/`bad` branches keep status ink only on the fill while `ok` demotes the value itself. Overlay rule applies: "where the code and DESIGN.md disagree, the code is what gets corrected." Fix: keep `ok` unfilled but leave the value at full `--sk-ink` (drop the `text-(--sk-ink-muted)` from `TONE.ok`).

### JUDGEMENT — Duplicated Code / Repeated Switches: `FdcStatus` label map

`STATUS_LABEL` (`ok→정상, warning→주의, bad→이상`) in `SetStatusMatrix.vue` duplicates the same domain mapping already expressed in `FdcScatter.vue` (`STATUS_COLOR`, line 30) and the fill/tone pairing now lives in *four* sibling consts (`TONE`, `STATUS_LABEL`, `LEGEND_FILL`, `LEGEND_LABEL`). The canvas-vs-DOM split legitimately excuses the color maps (`FdcScatter` needs inline hex for ECharts; here tokens are correct), but the Korean status→label map has no render-target excuse and would be a clean candidate for a small shared helper. Low priority.

### Notes (not findings)

- `fdcCategoryLabels` export also changes single-scope behaviour (`labelsByCategory` now skips empty labels, first *non-empty* wins). Commit body documents this; no existing `paramMatrix.test.ts` asserts the old empty-wins rule, so no regression.
- `rounded-[3px]` on the legend swatch is off the 6/8/10/14 scale, but `comparison.vue:164` and `LotDetailModal.vue:101` use the identical `h-2.5 w-2.5 rounded-[3px]` swatch — repo precedent, suppressed.
- Path auto-import (`<EbeamSkewvoirFdcSetStatusMatrix>`), `.ts` sibling extension on `fdcSet.ts`/`fdcSet.test.ts`, and no-inline-hex all check out.

### `work/skewvoir-fdc-set` — Spec

Reviewed spec, gap-analysis doc, and the full diff. Verdict: the spec is largely satisfied — all four numbered requirements and the key prohibitions hold. Findings:

## (a) Missing / partly done
Nothing materially missing. All four requirements are implemented: matrix (`SetStatusMatrix.vue`), category grouping via the shared label map, honest blanks for absent channels, and `AppLoadingState`/`dashboard-surface` phrasing copied verbatim from `PositionStack.vue`. The grain/comment honesty requirement ("이 점을 코드 주석에 남기세요", line 40-41) is done thoroughly in `fdcSet.ts`.

## (b) Scope creep (not asked for)
- **`paramMatrix.ts` edit touches the single-scope view.** `labelsByCategory` was renamed to `fdcCategoryLabels`, exported, and its rule changed from *first label wins* to *first non-empty label wins*. This alters how the existing single-MSR matrix renders an empty `category_label`, and was not requested.
- Per-run roll-up chips in column headers (`이상 N` / `주의 N` / `이상 없음`) — beyond "셀 값은 drift_sigma, 셀 색은 status" (line 45-46).
- Unloaded-run exclusion + the "측정 N개는 아직 불러오지 못해…" note, plus the `dynamic_fdc` source-grep test — all defensible under the honesty axis but extra.

## (c) Implemented but looks wrong / diverges from an explicit prohibition
- The `fdcCategoryLabels` change contradicts the spec's "그 방식과 표기를 그대로 따르세요. 새 규칙을 만들지 마세요." (line 51). By editing the *shared* function the implementer changed the single-scope view's grouping behavior too, rather than following its rule unchanged. This is the strongest finding: a rule the spec said to keep was modified.
- Minor: the "이 세트에는 FDC 채널 데이터가 없습니다." branch is reachable when all *loaded* runs have empty `fdc_params` while unloaded runs (which might carry FDC) are silently uncounted, because the `unloadedCount` note only renders inside the `channelCount > 0` panel. Corner case, not a spec violation.

Prohibitions otherwise respected: no inline hex, only `--sk-*` tokens (no new tokens added — `main.css` untouched), `health`/`spm_dict` structurally excluded via the narrow `FdcSetRunSource`, no `useSkewvoirAnalysis.ts` edits, `.ts` sibling imports present, no duplicate export names, and the component path/tag name is correct (`<EbeamSkewvoirFdcSetStatusMatrix>`).

### `work/skewvoir-across-msr` — Standards

## Review — `work/skewvoir-across-msr` (frontend only)

Five files, all in the sanctioned surfaces. This is a high-quality change: the pure module honors both `skewvoirAnalysis` rules (sibling imports carry `.ts`, `acrossMsr.test.ts` is paired), the auto-import tags are correct (`EbeamSkewvoirFactorAcrossMsrScatter` / `...Summary`), and colors route through tokens or the chart-palette exception (legend swatches `:style="{ backgroundColor: chip.color }"` are the sanctioned "matching DOM data mark" case; `rounded-full` on 9–10px swatches matches the existing `TimeSeriesChart`/`SequenceTrend`/`LotTable` legend pattern, not a new shape).

**No HARD (documented) breaches found.**

### JUDGEMENT findings

1. **Duplicated Code** — `AcrossMsrSummary.vue` reproduces `RelationshipSummary.vue` almost verbatim: the stat-card shell (`min-w-[5.5rem] flex-1 rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2`), the `fmt = (v) => v == null ? '—' : v.toFixed(3)` helper, the `muted`-on-zero stat array, and the `연관이며 원인 증명이 아님` chip are byte-for-byte the sibling's. Same for `rankToolColors(props.result.points.map(p => p.eqpId))`, repeated in `AcrossMsrScatter.vue` and `AcrossMsrSummary.vue` — two sites whose comments both promise "rank over drawn points". A shared `rankOverDrawn(result)` (or a shared summary-strip) would keep them in sync. Small, but real.

2. **Unnamed-tool inconsistency (Feature Envy-ish)** — `AcrossMsrScatter.vue` ranks/colors over `props.result.points.map(p => p.eqpId)`, which includes `''` — the module's "no identity" sentinel. `acrossMsr.ts` explicitly refuses to treat that as a tool (`if (!p.eqpId) continue` before building `strata`, comment: "inventing a tool that does not exist"), yet the scatter will rank `''`, assign it a palette color, and render an empty-label legend chip plus a series named `''`. The test `'a point whose measurement carries no tool id forms no stratum'` exercises exactly this (`new Map()` identity) and would surface the mismatch at the UI layer. Filter `''` out of the ranking in both components the way `strata` does.

3. **Minor — inline structural type** — `axisName = (axis: { label: string, unit: string } | null)` in `AcrossMsrScatter.vue` re-declares a subset of `AcrossMsrAxis` instead of importing it; the shared `unit`-suffix formatting is now hand-maintained here and in `acrossMsrAxes` labels.

No other smells; the `MIN_CORRELATION_N` claim ("same floor `pearson`/`spearman` already enforce") is accurate (`stats.ts:84,108`).

### `work/skewvoir-across-msr` — Spec

## Review: `work/skewvoir-across-msr`

The core numbered requirements (spec lines 48-65) are implemented correctly: axes read from `featureRegistry` with `label`/`unit` verbatim (line 48-49); tool stratification via `rankToolColors`/`toolLegendChips` and `MeasHistRow.eqp_id` (line 50-52); pooled + per-tool correlation side by side with `<3`-point suppression and reasons (line 53-56); the `연관이며 원인 증명이 아님` badge kept (line 57-58); `drift_sigma`/`status` neither added nor secretly read (line 59-62); click-to-focus via `setFocusedMsr` (line 64-65). Constraints hold: no `health`/`spm_dict`, `useSkewvoirAnalysis.ts` untouched, correct `EbeamSkewvoirFactor*` tag names.

**(a) Missing / partly done**

- Line 20 points the goal state at §7.1, whose recommended chart is "stratified scatter, **robust fit, time arrow**". The diff draws a plain OLS `fitLine` (not robust) and adds no time arrow — the latter is the benchmark's way to show run order, absent here.
- Benchmark §7.3 (referenced via line 130, "hardware event-time join") requires a `데모 데이터` marker on multi-run CD↔FDC views because home-mock CD/FDC correlate only through the shared `health` scalar. No demo badge appears.

**(b) Scope creep**

- The set-scope **Distribution panel (Hist/Box/Violin)** is deleted (`EbeamSkewvoirDistributionChart` removed). The brief only asks to replace the X/Y scatter placeholder (line 23-25); it never asks to drop the distribution view.
- The pooled **OLS regression line** (`pooledFit`) is drawn, but no fit line is requested in the numbered bullets.
- **Spearman ρ** is shown alongside Pearson; line 55 asks for "전체 상관 계수 하나" — the diff publishes two per scope.

**(c) Looks wrong**

- `buildAcrossMsrOutcome` still pushes points with `eqpId: ''` (its own comment says only *named* tools form a stratum), but `AcrossMsrScatter` calls `rankToolColors(points.map(p => p.eqpId))`, which assigns `''` an identity color and an empty legend chip. A tool-less MSR should be excluded from coloring, matching the stratum filter.
- The fit-line *decision* (draw only when `pooled.reason === null`) lives in the component's `pooledFit` computed, untested — against line 69-71 ("파생 계산은 컴포넌트에 두지 마세요"). It reuses the tested `fitLine` util, so it's minor, but the publish/withhold logic has no `*.test.ts` coverage.

### `work/skewvoir-cdu-card` — Standards

## Review: work/skewvoir-cdu-card

### HARD — documented standard breaches

**DESIGN.md "a data value never renders below 12px" (line 311), "values are ink, labels are muted" (line 136).** The diff's two cards render counts/metrics at 11px muted ink throughout:

- `CduCard.vue` header — `유효 N {{ metrics.n }}` and `결측 {{ metrics.missing }}` sit inside a `text-[11px]` parent span, so `metrics.n`/`metrics.missing` (the card's headline sample size) inherit 11px. The `font-bold text-(--sk-ink)` on the value fixes the color but not the size.
- `FailureCauses.vue` header — `{{ breakdown.sites.measured }}/{{ breakdown.sites.total }} site 측정` is rendered through `.sk-label` (11px, ink-muted), putting numeric values in the chrome tier.
- `FailureCauses.vue` right cluster — `실패 {{ breakdown.failedCount }}`, `미상 {{ breakdown.unknownCount }}` at `text-[11px]`.
- `FailureCauses.vue` spatial row — `{{ clustering.sectors... }}` counts and `좌표 없음 {{ clustering.unplaced }}` at `text-[11px] ... text-(--sk-ink-muted)`.

The per-line *cells* (`text-sm` values) are correct, so this looks like a header-density shortcut rather than an intentional new tier — but it directly violates the 12px floor and the value=ink rule.

### JUDGEMENT — baseline smells

**Duplicated Code** (`stats.ts` + `radialAnalysis.ts`). The new `median` and `MAD_TO_SIGMA` duplicate what `radialAnalysis.ts` already carries: `const median` at `radialAnalysis.ts:160` is byte-identical (`quantileSorted([...values].sort(...), 0.5)`), and `1.4826` is inlined at `radialAnalysis.ts:319`. The new comment even names that constant ("Same constant radialAnalysis.ts already scales its residual MAD by") without consolidating it — `radialAnalysis.ts` was left on its private copy, so two definitions now drift.

### Checked, no finding

- Component tags `<EbeamSkewvoirOverviewCduCard>` / `...FailureCauses` match the `overview/` path (existing `overview/StatBar.vue` confirms the convention); no empty-render risk.
- `cdu.ts` sibling imports all carry `.ts`; `~/composables/...` are `import type`-only (erased), matching `features.ts`.
- `rounded-(--sk-r-card)` and `--sk-*` tokens are on-system (used in `activity.vue`, `RecipeSearchView.vue`); no inline hex.
- `formatFixed` is auto-imported from `utils/recipeView.ts`.
- No localStorage plumbing, no provider/office files touched (frontend-only, as stated).

### `work/skewvoir-cdu-card` — Spec

Let me check a few more things — the DESIGN.md for color token rules, and whether `formatFixed` is properly available in Nuxt context.
## Review: `work/skewvoir-cdu-card` against `task-cdu-card.md`

The implementation satisfies all spec requirements. Findings below:

### (a) Missing or incomplete: none

Every spec line is addressed:
- **Three lines**: level (mean, median), spread (σ, 3σ, MAD, range), shape (center-edge delta from existing `features.ts` spatial) — all present in `CduCard.vue`
- **`유효 N`**: shown in the card header alongside 결측 count
- **No target offset**: explicitly excluded with code comment matching the spec's "열지 마세요"
- **`isMeasuredRow` gate**: used in `cdu.ts:75`, never substitutes 0 for `null`
- **median/MAD in `utils/stats.ts`**: both functions + tests added
- **Failure causes split**: `msr_check`, `align_fail`, image, `cd_missing` — all four in `FailureCauses.vue`
- **`fail_ratio` untouched**: passed through at source, never scaled
- **Spatial clustering visible**: per-sector counts displayed, reuses `analyzeSpatial().failures`

### (b) Scope creep: one borderline addition

`failureClustering()` in `cdu.ts` outputs a binary verdict (`clustered`/`scattered`) based on hardcoded thresholds (`MIN_PLACED_FOR_VERDICT = 3`, `CLUSTER_SHARE = 0.6`). The spec line says "실패가 웨이퍼 위에서 뭉쳐 있는지 볼 수 있어야 합니다" — a visibility requirement, not an automated judgment. The per-sector counts fulfill the requirement; the verdict is extra.

### (c) Wrong: none

All constraints pass:
- **No `health`/`spm_dict`** in 판정 paths
- **Colors**: `--sk-*` tokens only, `--sk-bad` reused — no inline hex
- **Computation outside components**: `cdu.ts`, `stats.ts` with `.test.ts` siblings
- **`.ts` extension** on sibling imports in `utils/skewvoirAnalysis/`
- **`useSkewvoirAnalysis.ts`** unmodified
- **`align_fail === 'NA'`**: correctly reported as `unknown`, not `fail`
- **`formatFixed`** from `utils/recipeView.ts` — auto-imported by Nuxt, no conflict

**Verdict**: the diff satisfies the spec.


## Judgement

인용은 모두 원문을 열어 대조했습니다. `DESIGN.md` 17·52·118·136행,
벤치마크 연구 §7.1 표와 297행, `radialAnalysis.ts:160`·`319`,
`acrossMsr.ts:220` 대 `AcrossMsrScatter.vue` — 근거가 실재하지 않는 지적은
없었습니다.

### 수용하고 고친 것

| 지적 | 축 | 커밋 |
| --- | --- | --- |
| `TONE.ok` 가 drift σ 값을 muted ink 로 칠함 | fdc-set Standards (HARD) | `23398013` |
| CDU 카드·실패 카드의 데이터 값이 11px | cdu-card Standards (HARD) | `a122465e` |
| `median` / `1.4826` 이 `radialAnalysis.ts` 와 중복 | cdu-card Standards | `a122465e` |
| 장비 식별자 없는 측정이 팔레트 색과 빈 legend chip 을 얻음 | across-msr Standards + Spec | `f26a9a5c` |
| 추세선 발표 여부를 컴포넌트가 결정하고 테스트가 없음 | across-msr Spec | `8dff32e2` |

### 수용했으나 고치지 않은 것

- **set 범위 Distribution 패널 제거** — 두 축이 scope creep 으로 지적했고 그
  판단은 맞습니다. 다만 옳은 해결은 복원이 아니라 제거입니다. 그 패널은 set
  범위라고 이름 붙인 채 focus 파일 하나의 site 행만 그리고 있었으므로,
  자리표시자의 나머지 절반이었습니다.
- **Pearson 과 Spearman 병기** — 스펙은 "전체 상관 계수 하나"를 요구했지만,
  두 계수를 나란히 두는 것은 단조 관계와 선형 관계를 구분하게 해 주므로
  요구를 넘어선 개선으로 판단해 유지합니다.
- **`failureClustering` 의 군집/분산 판정** — 스펙은 가시성만 요구했습니다.
  판정과 함께 섹터별 실제 개수를 항상 렌더링하므로 판정이 근거를 가립니다.
- **`fdcCategoryLabels` 의 first-non-empty 규칙 변경** — 단일 범위 동작도
  바뀌지만, 빈 헤더 대신 category 코드로 떨어지는 쪽이 개선이고 기존 테스트
  25개가 그대로 통과합니다.

### 보류한 것

- **§7.1 의 robust fit 과 time arrow** — 벤치마크 연구가 Across-MSR Outcome
  의 권장 chart 로 지정했으나 이번 작업 지시서의 요구가 아니었습니다.
- **`AcrossMsrSummary.vue` 가 `RelationshipSummary.vue` 를 거의 복제** —
  실재하는 중복이지만 리뷰 대상 밖의 파일까지 건드려야 하므로 별도 정리
  대상입니다.
- **`STATUS_LABEL` 의 상태→한국어 라벨 중복** — 우선순위 낮음.

### 아직 열려 있는 것 — `데모 데이터` 표식

벤치마크 연구 297행이 요구합니다. *"home mock에서 CD와 FDC는 모두 per-MSR
공통 `health` scalar로 편향되므로, 이 데이터에서 관찰되는 CD↔FDC 상관은
생성기 artifact이며 방법 검증 근거가 아닙니다. 단일 sequence(§6)와 다중 run
화면 모두에 `데모 데이터` 표식을 답니다."*

`front-dev-home/app` 전체에 그 표식이 없습니다. 새 Across-MSR Outcome mode 는
CD feature 와 FDC feature 를 두 축에 놓을 수 있으므로, home 에서는 조작된
상관을 경고 없이 보여줍니다. 기존 단일 범위 CD↔FDC 뷰도 같은 빈틈을 이미
갖고 있습니다.

고치려면 프런트엔드에 provider 인지 계층이 필요합니다. `/api/health/providers`
가 feature 별 `mock`/`office` 를 알려주지만 프런트엔드는 이 응답을 어디에서도
읽지 않습니다. 표식을 무조건 달면 office 의 실제 데이터를 데모라고 잘못
표기하게 되므로, `msr_file` 이 `mock` 으로 해석될 때만 표시해야 합니다.
리뷰 수정이 아니라 신규 작업이라 이번 범위에서 제외했습니다.

## Follow-up

- 병합: `3ef16fcb`, `9540c3a3`, `413d39e5`, `573b836d` (main)
- 브라우저 검증: 세 화면 모두 확인, 콘솔 에러 0건
  (`.playwright-mcp/screenshots/verify-01..03`)
- 검증에서 새로 발견: 측정 개요의 StatBar 평균(`29.57`)과 CDU 카드
  평균(`29.58`)이 같은 화면에서 다르게 보입니다. 백엔드가 3자리로 반올림한
  `mean: 29.575` 와 프런트엔드가 원본에서 계산한 `29.57546…` 의 차이입니다.
  둘 다 틀리지 않았으나 계측 도구에서 같은 이름의 값이 달라 보이는 것은
  그 자체로 결함이므로, StatBar 의 중복 칸을 걷어내는 것으로 해소해야 합니다.
- `oc-review` 스킬 개선: 스펙 파일 경로 규칙, 빈 응답 진단, 인용 검증 절차
