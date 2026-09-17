# TTTM page renovation — brief for Codex

You are working in a git worktree: `/Users/daeyoung/Codes/skewnono-tttm-renovate`
(branch `work/tttm-renovate`). Do ALL work here. Read `CLAUDE.md` and `DESIGN.md`
at the root first — they are binding (colors from `--sk-*` tokens only, no Pinia,
explicit-path git staging only, never `git add -A`).

The page: `frontend/app/pages/ebeam/cd-sem/[fab]/tttm.vue` → one component,
`frontend/app/components/ebeam/LabView.vue`, plus `components/ebeam/tttm/*`,
`components/ebeam/{RequestBar,AnalysisBar,ScopeParameter,ToleranceKnob,LabPanelPicker,ToolGroupBar}.vue`,
`components/ebeam/pmPlanning/*`, `utils/labView.ts`, `utils/pmTuningTarget.ts`.

This is the product owner's feedback, verbatim in spirit. Seven changes.

## 1. Remove the "PM 튜닝" option; make tuning reactive to a map click

- Delete the `pm` panel from `utils/labView.ts` (`LabPanel`, `LAB_PANELS`). A
  stored `pm` value must be dropped silently by `normalizePanels` (it already
  filters unknown names — keep a test for it).
- Delete the 튜닝할 장비 picker bar (`pmPlanning/ToolPicker.vue`) from the page.
- In 장비 그룹 배치도 (`tttm/FleetMap.vue`), clicking a tool's dot selects it
  (emit `update:pickedTool`; clicking it again or empty space deselects). The
  selected dot gets the existing ring (`pickedTool` prop already draws it).
  Mind the memory note: chart OPTIONS must never depend on hover/cursor state
  (`useEchart` rebuilds with notMerge) — a click-selected tool is fine, hover is not.
- Beside the map, a reactive card shows how much each parameter of the selected
  tool must change to reach the group centre. That computation EXISTS:
  `utils/pmTuningTarget.ts` + `pmPlanning/Targets.vue`. Reuse them; do not write
  a second calculation. With no tool selected the card says, in one short
  sentence, to click a tool on the map.
- No default pick any more: remove the `pickDefaultTool` watcher. Clear the pick
  when the tool leaves the basis.
- The pm_planning gate (`GateCard.vue`, the `usePmPlanningApi` fetch in LabView,
  the Hold stat in `metaStats`, the "이 장비는" summary sentence) leaves this
  page. Delete frontend files that become unreferenced (grep first —
  `pages/ebeam/cd-sem/[fab]/pm-planning.vue` is a redirect stub and STAYS, and
  `utils/pmAdmission.ts` stays if anything still imports it). Do NOT touch
  `backend/` pm_planning, `pageIdentity.ts` aliases, or `_logging/feature_map.py`.
- Layout: row = [배치도 | 튜닝 목표 card]. The consensus 잔차 card
  (`FleetStatus`) moves to its own place below (pair it sensibly; check at
  1440px and ~1100px).

## 2. Relocate 데이터 요청

In `RequestBar.vue` the button sits far right, away from 수집 기간; users cannot
tell what to click. Put the button directly BELOW the 수집 기간 control, same
left edge, status line beside/under it. One visual unit: period → button.

## 3. Rewrite the explanatory copy

All hints/captions on this page are unclear and verbose. Rewrite them: short,
kind, plain, formal Korean (`~합니다/~입니다`). One sentence where possible.
- Do NOT use the "자세히" fold. Remove every `<EbeamTttmCaptionMore>` that uses
  the default label; say the one thing the reader needs inline, drop the rest.
  (`RecommendationCard`'s `label="목록"` use is a list, not an explanation — keep
  it, and then `CaptionMore`'s default label can go.)
- Never the word 함대; say 장비 그룹.
- Code COMMENTS are not the target — only user-visible text. Don't churn comments
  except where the code they describe changes.

## 4. "오늘 consensus 잔차" → the selected 수집 기간

"오늘" is ambiguous. The residual card, and the deviation badges in
`ToolGroupBar`, should describe the selected window instead.
- First check what the payload already carries: `trend` (per tool per day) and
  `parameter_profile` are window-scoped. If a per-tool window residual can be
  derived on the client from `trend` (median of that tool's daily residuals
  over the window, then re-based on the visible basis like `rebaseDeviations`
  does), do that as a pure function in `utils/` with a `node --test` test — no
  backend change.
- Only if `trend` cannot honestly carry it, change the backend — and then BOTH
  `backend/ebeam/tttm/providers/mock.py` AND `office_example.py` (never
  `office.py`, never `data.py`), plus `contracts.py`, fixtures, and
  `frontend/app/composables/useTttmApi.ts`. Say which route you took and why.
- Title becomes e.g. `consensus 잔차 · 최근 N주` — name the window, not "오늘".
- Reword every other user-visible "오늘" on this page likewise.

## 5. skew 트렌드 chart

- Scatter, not line: with many tools selected the lines are untraceable. Make
  the dots noticeable (size ~9–10, solid fill, thin white/surface border,
  emphasis on hover; keep legend toggle + dataZoom; tooltip per item is fine).
- No dashed lines anywhere — the fab never uses them. BM/PM marker lines become
  solid; distinguish hard vs soft by colour (`SK_STATE.bad` / `SK_STATE.warn`)
  and width + the label text. Update the caption accordingly (short).
- Also remove the dashed blocked-pair connector style in `FleetMap.vue` (`type: [5, 4]`) → solid.

## 6. 분석 조건: parameters as buttons

Replace the `USelectMenu` dropdown in `ScopeParameter.vue` with toggle chips
(multi-select; an explicit `전체` chip = empty selection = all parameters).
Reuse the chip styling `LabPanelPicker.vue` already uses — do not invent a new
chip. Keep the `lock` disabled/loading behaviour and the emitted contract
(`update:parameters`, string[]). Long lists wrap.

## 7. 장비 그룹 배치도 legend + tolerance

- "가장 가까운 장비마저 허용오차 밖" reads weird. Reword both fill legends
  plainly, e.g. `허용 오차 안에 맞는 장비 있음` / `허용 오차 안에 맞는 장비 없음`.
- Move the tolerance control (`ToleranceKnob.vue`) out of 분석 조건 and place it
  next to the map (in or directly above the map card) so dragging it and seeing
  dots recolour happen in one place. Keep its drag/commit split
  (`v-model` per frame, `@commit` persists) exactly — see the comment at
  `LabView.vue` `tolerance` ref. It must still render when the `map` panel is
  off? No: if the map is off, keep the knob reachable in 분석 조건 as a fallback,
  OR decide the simpler honest option and state it. Prefer the smallest code.

## Process — required

1. Implement. Prefer deletion and reuse; no new dependency, no new abstraction
   with one user. Pure logic goes in `utils/*.ts` with a `*.test.ts`.
2. SIMPLIFY pass: re-read your whole diff for duplicated logic, dead
   props/computeds/imports left by the pm removal, comments describing deleted
   code, and anything reimplementing an existing util. Fix what you find.
3. Gates, all from `frontend/`: `npm test`, `npm run typecheck`, `npm run lint`.
   If backend changed: from the root
   `/Users/daeyoung/Codes/skewnono_v3_nuxt/.venv/bin/python -m pytest backend/ebeam/tttm tests -q`
   and `.venv/bin/python -m ruff check .`. Markdown edits: `npm run lint:md` at root.
4. THOROUGH self-review of the final diff (`git diff main`), as a hostile
   reviewer: correctness (null/empty payload, <2 tools, stale payload, tool
   detached from PCA, deselect), DESIGN.md compliance, Nuxt auto-import name
   traps (a component under `components/ebeam/tttm/X.vue` is `<EbeamTttmX>`;
   repeated path words collapse), frontend types drifting from `contracts.py`.
   Fix findings, re-run gates.
5. Commit on this branch with explicit pathspecs, `type(scope): summary` + body.
   Do NOT merge, push, or remove the worktree.
6. Finish with a report: what changed per item, which route for item 4, files
   deleted, gate output tails, review findings fixed, anything left open.
