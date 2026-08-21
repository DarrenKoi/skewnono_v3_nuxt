# 측정 개요 판정 블록 — opencode oc-review 기록

- 실행일: 2026-08-22
- 스킬: oc-review (2축 — Standards / Spec)
- 모델: opencode-go/glm-5.3 variant=high (tier=heavy)
- 대상: `git diff 78e781a3...HEAD` — skewvoir 측정 개요 상단 4카드를 판정 블록
  하나로 교체한 커밋 2개 (10개 파일, +925/−399)
- 소요: standards 93s (`ses_fd980dc2effeIc1q31B6tMtd4o`) · spec 86s
  (`ses_fd980dc11ffeSL3Qe8sJN0kNYZ`), 두 축 모두 exit 0
- 표준 출처로 지정한 문서: `CLAUDE.md`, `DESIGN.md`,
  `front-dev-home/app/assets/css/main.css`
- 스펙 출처: claude.ai/design 프로젝트가 저장소 밖이라 opencode 샌드박스가 읽지
  못하므로, 시안 원본(`proposed.dc.html`)과 시안 주석에서 옮긴 스펙을
  `.playwright-mcp/design-spec/` (gitignore) 아래에 넣고 저장소 상대 경로로
  넘겼습니다.

## 모델이 말한 것 — Standards 축

## Standards axis (documented breaches)

**VerdictBlock.vue:221 — HARD.** The "웨이퍼에서 보기 →" button renders `text-(--sk-accent)`:

```html
class="ml-auto shrink-0 text-xs font-semibold text-(--sk-accent) transition-colors duration-200 hover:text-(--sk-brand-ink)"

```

DESIGN.md §Colors: crimson is "trim only — sanctioned uses are exactly three (`.sk-nav-accent`, `.sk-fab-active`, `.dashboard-bg-layer`)"; §Don'ts: "no crimson buttons, no crimson body text." The 2026-08-05 changelog entry explicitly swept crimson *text* out of CapCell for this reason. Existing `text-(--sk-accent)` drift elsewhere doesn't authorize a new instance. (It also arguably fails the litmus test — it changes the view, so ink, not a hue.)

**VerdictBlock.vue:83 — HARD (borderline).** `<span class="text-sm text-(--sk-ink-muted)">/{{ cov.total }}</span>` puts the denominator in muted ink. DESIGN.md: "data values always get full ink; muted ink is for labels only" and the litmus "Value → ink." `cov.total` is a value the reader uses, not a label. Same question applies to `align.methods` rendered as `.sk-label` (line 95).

**VerdictBlock.vue:289 — JUDGEMENT.** `font-mono text-[11px] text-(--sk-ink-muted)` hand-rolls an 11px label tier where DESIGN.md's "going forward, prefer the semantic type classes over re-introducing ad-hoc `text-[…]` sizes" points at `.sk-label` (a mono variant is the missing piece, which is the honest fix).

## Baseline smells

**Duplicated Code — JUDGEMENT.** VerdictBlock.vue: the "자세히" toggle button (lines 72–79, 125–131, 165–171) is the same 8-line markup three times, differing only in the key; the `·`-separator list pattern (lines 102–117 and 202–213) and the `평가 불가 — …` `text-xs font-semibold text-(--sk-ink-subtle)` span (lines 149, 182, 295) are each repeated. → extract one `DetailToggle`-shaped local component / one separator loop.

**`rounded-full` dot — JUDGEMENT, suppressed.** Line 10 (`h-1.5 w-1.5 rounded-full`) nominally hits the "no rounded-full on new components" rule, but tiny status dots are an established repo-wide pattern (HardwareView, LotTable, ScePanel) — treating a 6px dot as outside the ban matches existing practice.

## Clean

- Conditions.vue: unit split keeps values at `sk-value-num` (12px ink), units at `.sk-label` — explicitly satisfies the sub-12px rule; comments cite DESIGN.md.
- verdict.ts / cdu.ts: reuse over re-derivation is documented and real; `VerdictInput` is a proper type where a data clump wanted to be born; `sectorClustering` rename + widened `SectorSited` avoids primitive obsession; tests cover the refusal paths (null σ, no sites) — no value-domain narrowing.
- No inline hex, no hand-rolled localStorage, deleted components leave no dangling references; `missing: cov.failed` matches `overview.ts`'s `failed = total − measured` semantics.

## 모델이 말한 것 — Spec 축

## Spec review: skewvoir/analysis 측정 개요 verdict block

**(a) Missing / partly done**

1. **판정 규칙 tooltip is paraphrased, not verbatim.** Spec: "## 판정 규칙 — verbatim from the design, to be exposed as a tooltip". `VerdictBlock.vue` rewrites the four rules into prose (`'실패·결측이 있거나 이상 site 가 있으면 확인 필요, 그 외에는 정상입니다.'` etc.), dropping the design's exact threshold phrasing ("실패·결측 > 0 또는 이상 site > 0 → **확인 필요**"). Content is equivalent, but the spec explicitly asked for verbatim.
2. Nothing else is missing: badge, sentence, conditions-on-one-line, three columns with 자세히, 웨이퍼에서 보기, and all five "유지" values are present; 자세히 carries median, σ(이상치 제외)/range, 4-cause detail, sector counts, 유효 N/결측 as specified.

**(b) Scope creep**

1. **`show-on-wafer` machinery.** Spec table lists only "웨이퍼에서 보기 →" as a caption line item. The diff adds `setFocusedSequence`, an emitted event, `useTemplateRef`, and `scrollIntoView` wiring in `Dashboard.vue` — behavior nobody asked for, though defensible since the design renders it as a link.
2. **`AlignImages` thumbnails inside the 커버리지 column.** Spec: "실패 n · Align n + methods" — images are not in the column spec. Mitigating: they are carried over from the deleted `StatBar.vue`, so it's preservation, not invention.
3. `sectorClustering`'s rename + widened `SectorSited` type is a shared-util API change, but it's required by the design's rule ("좌표 있는 **실패·이상** 3개 이상") — not creep.

**(c) Implemented but looks wrong**

1. **Sentence/σ-share clause can contradict its own guard.** Spec: "σ(이상치 제외)/σ ≤ 0.8 → 'σ 의 n% 가 이상 site 에서'". `verdict.ts` implements this as `share >= 1 − 0.8`, which is correct, but `outlierShare` returns `1 − madSigma/std` which can be **negative** (MAD-sigma exceeds std on flat-topped distributions), printing "σ 의 -8% 가 …" — a nonsensical sentence the spec's rule never licenses. No clamp to 0.
2. **산포 caption prints the 축소 clause even with zero outliers** whenever `outlierShare !== null`, including clean wafers where "이상치 제외 시 n% 축소" describes outliers that don't exist. Spec ties the clause to the outlier story ("σ 의 n% 가 이상 site 에서").
3. **`missing` input semantics.** `VerdictBlock.vue` passes `missing: cov.value.failed` while `verdict.ts` documents it as "Sites … with no measurement" — harmless today only because `cdMissingReason` makes 결측 a failed cause anyway, so the tone rule ("실패·결측 > 0 … 확인 필요") holds indirectly rather than by construction.

## 판단

### 수용 — 근거를 확인하고 고친 것

| 지적 | 확인한 근거 | 처리 |
| --- | --- | --- |
| crimson 링크 (HARD) | `DESIGN.md:38` "Trim only — sanctioned uses are exactly three", `:309` "no crimson body text", 그리고 모델이 든 전례가 실재합니다 — `:405` 2026-08-05 계측 룰 sweep 이 CapCell 에서 같은 `text-(--sk-accent)` 를 걷어냈습니다 | ink + 밑줄로 교체 |
| 분모·Align 방식이 muted (HARD) | `DESIGN.md:52` "Ink Muted … *never data values*", `:302` 리트머스 | 색 대신 크기로 강등 |
| σ 몫이 음수가 될 수 있음 | 재현했습니다 — 균등에 가까운 10점에서 `std 3.0277 / madSigma 3.7065 → share −0.224`, 캡션이 "이상치 제외 시 -22% 축소" 를 찍습니다 | `Math.max(0, …)` + 회귀 테스트 |
| 이상치 0 인데 축소 절이 나옴 | 위와 같은 뿌리 | 축소가 실제로 있을 때만 렌더 |
| 자세히 버튼 3중복 | 8줄 × 3 | `DetailToggle.vue` 로 추출 |
| `missing: cov.failed` | 두 값은 정의상 같지만 이름이 그렇게 말하지 않습니다 | `metrics.missing` 으로 교체 |

### 반려 — 근거를 확인하고 고치지 않은 것

- **문장이 "σ 의 -8%" 를 찍는다 (Spec c-1)** — 문장은 안전합니다. σ 몫 절은
  `share >= 0.2` 가드 뒤에 있어 음수는 통과하지 못합니다. 실제로 깨진 것은
  캡션 쪽이고, 그 절반은 위에서 고쳤습니다.
- **`missing` 의미가 간접적이다 (Spec c-3)** — "harmless indirectly" 는
  틀렸습니다. `overview.ts` 의 `failed = total − measured` 와 `cduMetrics` 의
  `missing = forParam.length − n` 은 같은 식이라 정의상 동일합니다. 그래도
  이름이 사실을 말하도록 바꿨습니다.
- **판정 규칙이 verbatim 이 아니다 (Spec a-1)** — 시안의 원문은
  `실패·결측 > 0 또는 이상 site > 0 → 확인 필요` 같은 주석용 축약형입니다.
  `DESIGN.md` 는 도움말 문장에 `~입니다/합니다.` 종결을 요구하므로, 화면에
  그대로 옮기는 쪽이 오히려 표준 위반입니다. 임계값(0.8 · 3개 · 60%)은 모두
  살아 있습니다.
- **`show-on-wafer` 배선이 scope creep (Spec b-1)** — 시안에서 이 자리는
  `<a href="#2a">` 이고, 아무 일도 하지 않는 링크는 출시할 수 없습니다. 최소
  동작(최악 이상 site 로 포커스 + 웨이퍼 열로 스크롤)만 넣었습니다.
- **`AlignImages` 가 커버리지 열에 있는 것 (Spec b-2)** — 시안 주석이 "유지:
  유지 요청한 5개 값 전부(… Align …)" 라고 못박고 있고, 지워진
  `StatBar.vue` 에서 그대로 옮겨온 것입니다.
- **`text-[11px]` 몬탄 라벨 (Standards, JUDGEMENT)** — 지워진 `CduCard.vue`
  에서 그대로 옮겨온 셀 라벨이고, 값이 아니라 라벨이라 11px 마이크로 라벨
  계층에 맞습니다. mono 변형 클래스가 없다는 점은 맞지만, 새 타입 클래스를
  만드는 것은 이 작업의 범위 밖입니다.
- **`rounded-full` 6px 점** — 모델이 스스로 억제했고, 확인 결과 맞습니다:
  `sk/AnomalyLegend.vue`, `sk/AnomalyBadge.vue` 가 같은 점을 씁니다.
- **`·` 구분 목록 2중복** — 두 곳뿐이고 데이터 모양이 달라, 지금 공용
  컴포넌트를 만들면 얻는 것보다 간접층이 큽니다.

## 두 축이 놓친 것

- 브라우저 확인에서만 잡힌 두 가지가 이미 앞 커밋(`802f216e`)에 들어가
  있습니다. diff 만 읽어서는 나오지 않는 것들입니다.
  - 이상 site 열의 큰 숫자(이상 site)와 섹터 목록(이상 ∪ 실패)의 분모가
    달라 한 숫자가 자기 자신과 어긋나 보였습니다.
  - 헤드라인이 `flex-1`(basis 0)이라 1024px 에서 4줄 조각으로 찌그러졌습니다.
- `cduMetrics` 가 identical site 에서 `std ≈ 3e-15` 를 내는 부동소수 문제는
  구현 중 테스트가 먼저 잡았고, 두 축 모두 언급하지 않았습니다. 음수 몫과
  같은 뿌리입니다.

## 후속

없습니다. 수용한 지적은 `e160aad0` 에 모두 반영했고, 프런트 1660 테스트 통과 ·
lint · typecheck clean 입니다.
