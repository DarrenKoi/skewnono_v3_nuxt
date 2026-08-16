# oc-review — TTTM 3a 개선안 적용 (main...work/tttm-3a)

- 일자: 2026-08-16
- 스킬: `oc-review` (2축 — Standards / Spec)
- 티어: `heavy` (glm-5.3). 근거: 18개 파일입니다. escalation surface 는
  건드리지 않지만 rubric 의 ~10개 파일 선을 넘었고, 새 순수 모듈이 계측
  파생값 산술을 담고 있습니다.
- 대상: `git diff main...HEAD` — 커밋 `1612abf5`
  (`feat(tttm): rebuild 장비간 스큐 관리 on the 3a control-rail layout`)
- Standards 근거 문서: `CLAUDE.md`, `DESIGN.md`,
  `front-dev-home/app/assets/css/main.css`
- Spec: claude.ai/design 프로젝트 `cad32336` 의 `TTTM 개선안.dc.html` 중
  "Turn 3" 절입니다. opencode 는 워킹 트리 밖을 읽지 못하므로 해당 절만
  `.scratch/tttm-3a/design-3a.html` 로 복사한 뒤 그 저장소 상대 경로를
  넘겼습니다. 구현에서 역산한 스펙이 아닙니다.
- 경과: standards 159s · spec 215s. 두 축 모두 exit 0 으로 정상 종료했습니다.
- 세션: standards `ses_ff5658f26ffeYD31yP587rhmjA` ·
  spec `ses_ff5658f1fffeAjGaPZyNJugu73`

## Standards (glm-5.3, 원문)

> **Review: `1612abf5` tttm rebuild (18 files, +1444/−615)**
>
> The 3a rail layout itself is compliant: DESIGN.md was amended in the same change (Iteration Guide §7), the 392px rail + `gap-3` matches the new documented exception, colors route through `--sk-*` tokens, `<details>` folds replace hand-rolled toggles, and `useId()` pairs the knob label.
>
> **HARD findings**
>
> 1. **FleetMap.vue:6-8** — `class="font-mono text-[11px] tabular-nums"` on `stress {{ map.stress.toFixed(3) }} · {{ stress.text }}`. DESIGN.md §Typography: "a data value never renders below 12px." stress is a value the user reads.
> 2. **ToleranceKnob.vue** — slider endpoints `font-mono text-[11px] tabular-nums` (`range.min/max`). Same sub-12px rule; these are numeric values (borderline labels, but numbers).
> 3. **CaptionMore.vue** — summary is `text-(--sk-accent)`. DESIGN.md: crimson's sanctioned uses are "exactly three" (nav underline, fab edge, page wash); "no crimson body text". A crimson clickable text link is a fourth use.
> 4. **Ad-hoc type sizes vs §Semantic type classes** — "prefer the semantic type classes … over re-introducing ad-hoc `text-[…]` sizes" (Known Gaps): ExcludedTools lead `text-[22px] font-bold` (role exists: `.sk-card-id`), PairMatrix cells `text-[13px]` (role: `.sk-value-num`), ScopePanel count `text-[13px]`, CellSeverityList row label `text-[13px]`, RecommendationCard `text-4xl` KPI.
>
> **JUDGEMENT findings**
>
> 5. **Rail rule vs cell tabs** — the diff's own new DESIGN.md rule says "the results column holds no control at all", yet PairMatrix puts an `SkNavPill` tab strip (a control) in the results column. It's a within-card view toggle, not a filter, but the rule as written is now contradicted by its own introducing commit.
> 6. **Card-title tier inconsistency** — ExcludedTools and RecommendationCard title via `.sk-eyebrow` (10px mono uppercase — Korean text in a mono-caps kicker tier); sibling cards in the same rows use `.sk-title`. Pick one.
> 7. **Duplicated Code** — `signed()` defined identically in ScopePanel.vue:236 and ExcludedTools.vue:117; FleetStatus inlines a third variant (`'+' : '−'` + toFixed(3)).
> 8. **Duplicated Code** — `rankCells` runs `worstFractionOfLimit` and `worstPairOf`, two upper-triangle max-walks over the same matrix; at fixed CD they're monotonic transforms of each other, so `severity === worstPair.index` — one walk could carry both.
> 9. **Motion vocabulary** — `transition-transform duration-150` (MdcTimeline/ProductionChip chevrons); DESIGN.md: `transition-colors duration-200` + two spinners "are the entire motion vocabulary".
> 10. **Carried over, not introduced**: ProductionChip overlap bars still fill `var(--sk-accent)` (crimson as fill) — pre-existing; sweep opportunity only.
>
> No mock/office smells apply — diff is frontend-only.

## Spec (glm-5.3, 원문)

> Now the diff. It's large, so I'll read it in chunks.
> Two spots need the post-change file state (not just the diff) to judge the meta bar:
> One quick check on the grouping engine, to judge whether ExcludedTools' unconditional "초과" claim can be false:
> ## Spec review: 3a → TTTM page
>
> The five-row argument order, the 392px control rail / control-free results split, tabs-to-one-matrix, folded MDC/양산 panels, and the roll-up card all match the mock's structure. Findings:
>
> ### (a) Missing / partly done
>
> 1. **App shell untouched.** Spec lines 23–41 (header nav with active TTM pill, 실험실/계정 chips) and 44–60 (64px CD/HV/VS/PR + fab rail) appear nowhere in the diff. Presumably deliberate — that chrome is app-level, not "the tttm page" — but the spec is "the design of record" including the shell, so flagging it.
> 2. Nothing else material is missing; stats, 데이터 기준 chip ("2026-05-31 14:30 · 1주 윈도우", line 87), tolerance knob, and every card's caption text are present.
>
> ### (b) Scope creep
>
> 1. **Sticky rail.** `xl:sticky xl:top-2` (TttmView.vue:29). Spec line 267 explicitly defers this: `다음에 해볼 것: "레일을 스크롤에 고정해줘" …` — it is a listed *future* experiment, implemented anyway.
> 2. **Dropdown row deviations.** ScopePanel's group menus show each tool's consensus residual and a 측정 없음 badge, plus 전체/해제 footer buttons. Spec lines 101–103 spec only `CG6300 2/7` triggers with chevrons.
> 3. **"함께 빠짐" chips** for extra excluded tools (ExcludedTools.vue) and the "(셀 합계)" qualifier — the mock shows exactly one excluded tool and line 132 reads `점유 셀 4개 · 불합격 장비쌍 4쌍 · 최악 0.240 nm (BC1·Y)` with no qualifier. Defensible generalizations, but unasked.
>
> ### (c) Implemented but looks wrong
>
> 1. **"tolerance … nm 초과" can be false.** ExcludedTools prints `초과` whenever a blocker pair exists, but exclusion also happens when a tool never overlapped *some* group member: adjacency is `isMeasured(v) && v <= tolerance` (tttmGrouping.ts:74), so a tool measured against one member only, inside tolerance, is still left out of the larger clique — and the card then claims a tolerance violation it doesn't have. The mock state (line 160: `BC1·Y 셀에서 ECDX204 와 0.240 nm — tolerance 0.105 nm 초과`) never exercises this.
> 2. **최약 장비쌍 order.** Spec line 152: `0.048 nm · CD 대비 0.32×` (nm first). RecommendationCard renders index first (`CD 대비 0.32× · 0.048 nm`) — a deliberate old comment, but it contradicts the spec's content order.
> 3. **Trend span.** Spec line 239: `최근 5주`; the diff replaces the fixed label with the computed date range. Data-driven and arguably safer, but it is a deviation from the specified content.

## Claude 의 판단

### 받아들인 것

인용된 `DESIGN.md` 규칙 세 건은 모두 문서를 직접 열어 확인했습니다. 세 건 다
실재하는 규칙이었습니다.

| 지적 | 축 | 조치 |
| --- | --- | --- |
| "tolerance 초과" 가 거짓일 수 있음 | Spec (c)1 | **진짜 버그입니다.** N배화는 모든 그룹 구성원과 "측정되고 tolerance 안인" 쌍을 요구하므로(`buildAdjacency` 의 `isMeasured`), 쌍 하나가 미측정이면 나머지 쌍이 전부 통과해도 제외됩니다. 카드는 데이터에 없는 위반을 단언하고 있었습니다. 비교를 `ExcludedTool.exceeds` / `RankedCell.worstExceeds` 로 옮기고 반대 경우의 문장을 따로 뒀습니다 |
| 12px 미만 데이터 값 | Standards 1·2 | stress 값과 슬라이더 양 끝값을 12px 로 올렸습니다 |
| crimson 링크 | Standards 3 | `자세히` 를 밑줄 + ink-muted 로 바꿨습니다. 목업은 accent 를 쓰지만 `DESIGN.md` 가 표준 문서이고 목업은 제안입니다 |
| `duration-150` | Standards 9 | 문서화된 `duration-200` 으로 맞췄습니다 |
| rail rule 자기모순 | Standards 5 | 이 커밋이 새로 쓴 규칙을 같은 커밋이 어겼습니다. "데이터를 다시 거르는 컨트롤" 과 "같은 답의 다른 보기로 바꾸는 컨트롤" 을 구분하도록 문장을 고쳤습니다 |
| `signed()` 3중복 | Standards 7 | `formatSignedNm` 으로 통합했습니다. 세 번째 사본은 이미 음수 부호 글리프를 잃은 상태였습니다 |
| 행렬 2중 순회 | Standards 8 | `severity` 를 `worstPair.index` 에서 가져옵니다 |
| 뱃지·타입 role 재작성 | Reuse 2·3·4 | `.sk-signal-badge` / `.sk-card-id` 로 옮겼습니다 |
| `<details>` 카드 복붙 | Reuse 5 / Altitude 1 | `FoldPanel.vue` 로 뽑았습니다 |
| `cd_band` 미사용 미러링 | Altitude 2 | 제거했습니다 |
| tolerance 통과 prop | Altitude 4 / Efficiency 1 | 슬롯으로 바꿨습니다. 드래그 프레임마다 모델 그룹 드롭다운 7개가 다시 그려지고 있었습니다 |
| `rankCells` 가 tolerance 무관 작업을 매 프레임 반복 | Efficiency 3 | `scoreCells` + `applyTolerance` 로 쪼갰습니다 |

### 받아들이지 않은 것

- **Standards 4 (ad-hoc `text-[…]`)** — 절반만 반영했습니다. `.sk-card-id`
  로 옮길 수 있는 것은 옮겼지만, 목업이 지정한 22px 와 36px KPI 숫자에는
  대응 role 클래스가 없습니다. `DESIGN.md` 자신도 이것을 "open follow-up"
  으로 적고 있어 HARD 가 아니라 JUDGEMENT 입니다.
- **Standards 6 (eyebrow vs title 불일치)** — 의도된 위계입니다. 목업에서
  윗줄 두 카드(답)는 eyebrow, 아랫줄 패널(근거)은 title 을 씁니다.
- **Spec (c)2 (nm 우선 순서)** — 지적이 맞지만 유지합니다. 기존 코드에 "지수가
  순위를 정한 값이므로 먼저 온다" 는 근거 주석이 이미 있었고, 목업의 배열
  순서보다 그 판단이 더 구체적입니다. 주석을 남겨 뒀습니다.
- **Spec (b)1 (sticky rail)** — 목업의 "다음에 해볼 것" 목록에 있는 항목을
  미리 구현한 것이 맞습니다. `mag-pixel.vue` 의 기존 레일이 sticky 이고
  되돌리기가 한 줄이라 유지했으며, 사용자에게 그대로 보고했습니다.
- **Spec (b)2·(b)3, (c)3** — 목업은 장비 5대·제외 1대·고정 문구 "최근 5주"
  를 가정하지만 실제 R3 는 17대이고 제외가 4대이며 트렌드 구간은 payload 가
  정합니다. 실데이터에서 성립하게 만든 일반화입니다.
- **Spec (a)1 (앱 셸)** — 셸은 이 페이지의 것이 아닙니다. 이미 존재합니다.
- **Altitude Q1 (레일 컴포넌트화)** — 모델도 현재 altitude 가 맞다고
  판정했고 동의합니다. 세 페이지가 서로 다른 폭·간격·sticky 여부를 씁니다.
- **PairMatrix/FleetMap 의 임계 비교 (Altitude 3 일부)** — `worstExceeds`
  로 대체할 수 없습니다. 전자는 셀 값마다의 비교이고 후자는 다른 행렬
  (`fleet_today`) 에 대한 비교라 같은 문장이 아닙니다.

### 두 축이 놓친 것

- 목업의 `epoch 리셋` 이 카드에 두 번 찍혔습니다 — `EpochMarker.label` 이
  이미 그 괄호를 포함합니다. 브라우저 확인에서 잡았고, 두 축 모두 정적
  diff 만 읽었으므로 찾을 수 없는 종류입니다.
- 브랜드 채움 위의 chevron 이 NuxtUI 기본 dim 색을 물려받아 dark mode 에서
  거의 보이지 않았습니다. 역시 렌더링해야 보이는 문제입니다.

## Follow-up

- 적용 커밋: `b5123df0`
- 남긴 것: `maximalCliques` 에 pivot 이 없어 18대·포화 그래프에서 호출당
  약 155 ms 가 측정되었습니다(efficiency 축 실측). 기존 동작이고 정확성의
  근간이라 별도 변경으로 다룹니다.
