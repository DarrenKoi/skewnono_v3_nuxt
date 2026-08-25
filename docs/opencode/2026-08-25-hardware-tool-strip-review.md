# H/W 관리 장비 선택 스트립 — opencode oc-review 기록

- 실행일: 2026-08-25
- 스킬: oc-review (2축 — Standards / Spec)
- 모델: opencode-go/glm-5.3 variant=high (tier=heavy)
- 대상: `git diff 5ef644fd~1...HEAD` — H/W 관리의 320px 장비 목록 레일을
  메타바 아래 가로 "장비 선택" 스트립으로 옮긴 커밋 1개 (2개 파일,
  +381/−338)
- 소요: standards 140s (`ses_fc8254a11ffeqMQsDm4dLlVE21`) · spec 131s
  (`ses_fc8254a0cffeqwv1eE4dISvHPu`), 두 축 모두 exit 0
- 표준 출처로 지정한 문서: `CLAUDE.md`, `DESIGN.md`,
  `front-dev-home/app/components/sk/Chip.vue`
- 스펙 출처: `.scratch/` 에 스펙이 없어 사용자의 요청문을 그대로
  `.scratch/hw-tool-strip/spec.md` 에 옮겨 저장소 상대 경로로 넘겼습니다.
  그 파일의 "Requirements as read" 다섯 항목은 Claude 가 요청문에서 읽어
  낸 것이며, 스펙 축은 그 다섯 항목을 기준으로 채점했습니다.

## 모델이 말한 것 — Standards 축

**Commit 5ef644fd** — rail → strip move. The design intent is self-consistent: the diff updates DESIGN.md §Layout in the same commit, uses `rounded-[var(--sk-r-card)]` on the new strip, and the chip-role litmus test (terracotta = filter, `tone="ink"` = one-of, matching `ParamCoverageList.vue:53`) is applied and documented correctly.

**Findings**

1. **HARD (minor)** — `HardwareView.vue`, selected-tool summary line: `{{ rows.length }}대 중 <strong ...>{{ searchedRows.length }}대</strong> 표시` inside `sk-field-label` (`--sk-ink-subtle`). DESIGN.md §Colors: "data values always get full ink; muted ink is for labels only." Both numbers are counts — data values — yet only `searchedRows.length` gets full ink; the total renders in subtle ink. (The repo treats counts as data values elsewhere — see the 12px-floor comment in `Chip.vue:101`.) Wrap the total in the same full-ink treatment.

2. **JUDGEMENT** — Scope-bar gating rule (DESIGN.md:177): the diff enrolls this page in "the scope-bar layout" (DESIGN.md:174) but not its gate — "the results area carries an explicit `AppEmptyState` naming the missing choice." The empty-scope state is still a plain `<span>…정보는 선택한 장비를 기준으로 열립니다</span>`, and the empty-search state a `sk-body` `<p>`. Mitigating: `selectedTool` auto-falls-back to the first row (`HardwareView.vue:142-147`) and the watch at :169-179 re-seeds it, so an unscoped results pane is nearly unreachable in practice — the rule's substance (no zeroed card masquerading as a verdict) holds. Worth either an `AppEmptyState` for the zero-rows case or a one-line doc note that H/W gates by auto-selection.

3. **JUDGEMENT** — DESIGN.md internal tension: §Layout:176 still says the scope bar *is* `EbeamScopeBar` titled **비교 대상**; this change adds H/W to the scope-bar family with a bespoke `장비 선택` section, sanctioned only by the changelog entry, not by the rule text. The rule body wasn't amended to permit a per-page strip, so the next reader applying :176 literally will flag this page.

4. **JUDGEMENT** — Pre-existing raw Tailwind colours carried through re-indentation (`text-emerald-700`, `text-amber-700`, `text-rose-700`, `bg-zinc-50`, `bg-zinc-900/60`, `border-zinc-200/70`, `rounded-2xl` on the service-tabs section) where `--sk-ok/warn/bad` families and `--sk-r-card` exist (DESIGN.md:221 bans `rounded-2xl` in hand-written markup). Not newly authored; noting because the diff touched every one of these lines — an opportune moment to tokenize.

No Fowler-baseline smells beyond a faint **Duplicated Code** (the `modelGroups` counting loop mirrors the `availabilityCounts` loop) — both are small and commented; not worth extraction.

## 모델이 말한 것 — Spec 축

(회신이 도중에 끊긴 뒤 모델이 스스로 검증 문단을 이어 붙였습니다. 두 부분
모두 그대로 둡니다.)

**(a) Missing / partly done**

- Nothing material is missing. All five requirements land: strip sits directly under `EbeamMetaBar` (HardwareView.vue:290→311), it is horizontal (chip rows, lines 312–424), models are shown and narrow the tool list (`modelGroups`/`matchesModel`, lines 106–139), the 데일리/분기 tabs and detail now span full width (lines 452–490), and search, On/Off filter, deep-link `eqp_id`, and selection-driving-detail survive.
- Partly done, req 5 — "Existing behaviour of the page … is preserved": the rail showed vendor/model/fab/IP/version on *every* row; now that metadata is hover-only (`:title`, line 410) except for the selected tool (lines 434–449). Keyboard/touch users lose it for non-selected tools.

**(b) Scope creep**

- Cross-filtered chip counts: "Each chip row's counts respect the OTHER two controls" (lines 112–115) and zero-count model retention ("A model chip is never dropped for counting zero"). The spec only asked "we may well see the tool lists" — counts weren't requested. Defensible polish, but unrequested.
- The "N대 중 M대 표시" counter (line 447) — nobody asked for a display-count readout.
- The scroll cap: "The tool row caps at about four rows and scrolls" (`max-h-[9.5rem]`, line 402). Reasonable, but invented, and it partially undercuts req 4 — with 60+ tools the strip itself consumes vertical space the request wanted given to the data.
- DESIGN.md reclassification of H/W 관리 from "rail member" to scope-bar member — repo convention says to do this, but it's beyond the quoted request.

**(c) Implemented but looks wrong**

- Duplicate eqp_id handling: the comment (lines 390–394) says sem_list repeats ids and keys are position-based, but `:active="row.eqp_id === selectedToolId"` (line 409) lights up *both* duplicate chips and `selectTool` can't distinguish them — the fab/IP context that separated them is now invisible on the chip face. Pre-existing in the rail (where the row body disambiguated), but the chip form makes it worse; with the strip the user picks between two visually identical chips.
- `matchesAvailability` respects model+search but the model row's counts respect availability — asymmetric by design, yet the "All Models" chip count (`modelCountAll`, line 125) is the only chip whose count can disagree with the tool row it would reveal when a model filter is active. Cosmetic, not incorrect.

Net: faithful to the spec; the creep is polish, the
I verified this report against my own read of the spec, the diff, and the post-change file. Verdict on each finding:

**Confirmed**

- (a) All five requirements land as stated; the hover-only metadata regression on non-selected tools (req 5: "Existing behaviour of the page … is preserved unless the request implies otherwise") is a fair partial finding.
- (b) Cross-filtered counts, zero-count retention, the "N대 중 M대 표시" readout, and the `max-h-[9.5rem]` scroll cap are all genuinely unrequested — accurately characterized as defensible polish, with the scroll cap genuinely trading against req 4 ("the data display below gain the freed width").
- (c) The duplicate-eqp_id finding is correct and the sharpest one: the key comment (lines 390–394) acknowledges ids repeat, yet `:active="row.eqp_id === selectedToolId"` (line 409) and `selectTool`/`selectedTool` (lines 142–147, 153) match on bare `eqp_id`, so two identical chips both highlight and are indistinguishable — worse in chip form than in the rail, where the row body carried the disambiguating fab/IP.

**Corrections**

- (b) DESIGN.md: not creep. This repo's convention is that DESIGN.md is the living design record and the dense-exception list explicitly says "Agreed pattern — do not revert" — reclassifying H/W 관리 from rail member to scope-bar member after moving it is required maintenance, not scope.
- (c) The `modelCountAll` claim is wrong. `modelCountAll` (line 125) is the sum of counts each respecting search + availability — exactly the set clicking "All Models" reveals. It agrees with the tool row it would show; there is no disagreement, cosmetic or otherwise.

**Completing the cut-off conclusion:** Net: faithful to the spec; the creep is polish, the regression is minor (tooltip-dependent metadata), and the one real defect — duplicate eqp_id chips being indistinguishable and double-highlighting — is pre-existing logic carried into a UI that no longer shows the disambiguating context, so it's worth fixing but wasn't introduced by this change's intent.

## 판정

인용된 규칙은 모두 열어 확인했습니다. "data values always get full ink; muted
ink is for labels only" 는 `DESIGN.md:17` 과 `:52` 에, `rounded-2xl` 금지는
`:221` 에 (그리고 `:384` 가 이미 "call-site drift to sweep" 으로 적어 둔
항목), 게이트 조건은 `:177` 에 실제로 있습니다.

### Standards 축

| # | 판정 | 이유 |
| --- | --- | --- |
| 1 (HARD, 카운트 잉크) | 수용 | 두 숫자 모두 데이터 값인데 전체 대수만 `--sk-ink-subtle` 에 남겨 두었습니다. 둘 다 full ink 로 올렸습니다. |
| 2 (JUDGEMENT, 게이트 없음) | 수용 — 문서로 해결 | H/W 관리는 선택이 자동으로 채워지므로 결과가 비는 상태가 사실상 없고, `AppEmptyState` 를 넣으면 "없는 선택" 을 지어내는 셈이 됩니다. 대신 `DESIGN.md` 규칙 본문에 *auto-selected variant* 항목을 추가해, 게이트를 생략할 수 있는 조건(기본값이 결과를 정직하게 계산할 수 있는 답일 때)을 적었습니다. |
| 3 (JUDGEMENT, 규칙 본문 미수정) | 수용 | 2번과 같은 수정으로 해결됩니다. 변경 로그만으로 새 변형을 허가한 것은 지적대로 부족했습니다. |
| 4 (JUDGEMENT, 기존 raw Tailwind) | 부분 수용 | 이 diff 가 실제로 건드린 두 `<section>` 의 `rounded-2xl` 은 `--sk-r-card` 로 올렸습니다. `emerald/amber/rose` 는 이 파일 밖까지 이어지는 `sk-bad-sweep` 에픽(`.scratch/sk-bad-sweep/`)의 범위라 여기서 손대지 않습니다. |
| Duplicated Code (modelGroups ↔ availabilityCounts) | 기각 | 모델 스스로 "not worth extraction" 이라 했고 동의합니다. 두 루프는 반대 방향으로 교차 필터링하므로 하나로 접으면 오히려 읽기 어려워집니다. |

### Spec 축

| # | 판정 | 이유 |
| --- | --- | --- |
| (a) 비선택 장비의 메타데이터가 hover 전용 | 보류 | 사실입니다. 다만 모델 chip 행이 이미 모델을 드러내고, fab 은 사이드바가, IP·버전은 선택 후 캡션이 보여 줍니다. chip 마다 다섯 필드를 얹으면 스트립이 다시 레일만큼 커지므로 이번에는 두지 않습니다. |
| (b) 카운트·표시 대수·스크롤 캡·DESIGN.md 는 요청 밖 | 부분 기각 | 카운트와 표시 대수는 요청 밖의 다듬기가 맞고, 값이 싸서 유지합니다. 스크롤 캡은 요청 4("데이터 표시에 폭을 더 준다")를 *깎는* 것이 아니라 *지키는* 장치입니다 — 60대 합집합에서 캡이 없으면 스트립이 6행으로 늘어나 데이터를 아래로 밀어냅니다. DESIGN.md 갱신은 모델의 자체 검증 문단이 이미 정정한 대로 이 저장소의 의무입니다. |
| (c) 중복 eqp_id chip 이 동시에 켜짐 | 수용 | 가장 날카로운 지적입니다. 레일은 행 본문(IP·버전)이 둘을 구분했지만 chip 은 id 만 보여 주고, 상세는 어차피 id 로 조회하므로 두 번째 chip 은 같은 데이터를 다시 열 뿐입니다. `toolChips` 로 id 당 한 개만 그리고 key 도 id 로 돌렸습니다(위치 key 는 중복 행을 살려 두던 레일의 결정이었습니다). 전체 대수 기준도 고유 id 수(`toolCount`)로 맞췄습니다 — 메타바의 "전체" 는 여전히 행 수라 mock 에서만 1 차이가 납니다(사내 sem_list 는 id 가 고유합니다). |
| (c) `modelCountAll` 불일치 | 기각 | 모델의 자체 검증 문단이 이미 철회했습니다. 검색·On/Off 를 반영한 합이므로 "All Models" 를 눌렀을 때 드러나는 수와 정확히 같습니다. |

### 두 축이 모두 놓친 것

- 요청문의 "we can show the models and based on the model selections, we may
  well see the tool lists" 를 스펙 축은 "모델 선택 → 장비 목록 좁힘" 으로 읽었고
  구현도 그렇습니다. 그러나 "All Models" 일 때도 장비 목록 전체를 보여 주는
  선택은 Claude 의 해석입니다 — 요청을 "모델을 고르기 전에는 장비를 숨긴다"
  로 읽을 여지도 있습니다. 두 축 모두 이 분기를 지적하지 않았습니다.

## 후속

- 수용 항목은 같은 날 후속 커밋으로 반영했습니다 (HardwareView.vue,
  DESIGN.md). 커밋 해시는 git log 를 참조합니다.
