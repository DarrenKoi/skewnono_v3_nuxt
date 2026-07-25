---
type: Documentation Plan
title: July 25 OpenWiki Maintenance Plan
description: Temporary evidence and impact plan for documenting the Mag/Pixel guide, Skewvoir interaction changes, SCE revision history, chart theming, and their regression tests.
tags: [openwiki, maintenance, planning]
---

# Documentation impact plan

## Source change -> documentation impact

| Source change | Documentation affected | Surgical edit | Why |
| --- | --- | --- | --- |
| New `/mag-pixel` route, components, and pure calculation model | `quickstart.md`, `domain/concepts.md`, `workflows/key-workflows.md`, `source-map.md`, `testing/guidance.md` | Add the product surface, metrology constraints, user/calculation flow, source entrypoints, and focused tests | This is a new user-facing workflow with explicit domain invariants and a shared scale utility. |
| Skewvoir keyboard navigation, composite multiselect, identity colors, calibrated gallery scale, and FDC matrix model/rendering | `domain/concepts.md`, `workflows/key-workflows.md`, `testing/guidance.md` | Describe focus versus selection, cross-view identity, scale calculation, matrix ranking/layout, and tests | These changes alter analysis interaction and evidence interpretation. The worktree-only matrix mounting/drill behavior must be labeled as uncommitted. |
| Full color-mode-aware ECharts themes and MATLAB light default | `workflows/key-workflows.md`, `testing/guidance.md` | Add one cross-cutting chart behavior note and its tests | Theme-driven presentation now changes across all ECharts surfaces while semantic colors remain fixed. |
| SCE coefficient collections collapsed into settings revisions with a revision picker | `workflows/key-workflows.md`, `testing/guidance.md` | Replace the generic SCE sentence and identify revision-collapse coverage | This changes how operators interpret and select coefficient history. |
| Correct full-backend pytest command | No edit | Preserve existing command | `quickstart.md` and `testing/guidance.md` already use `pytest tests back_dev_home -q`. |
| `useMsrFileApi` lint-driven retry refactor and dependency lock update | No edit | None | Runtime behavior and documented retry/batch contract are unchanged. |
| Uncommitted provider-safe ratio test split | No edit | None until committed | Runtime semantics are unchanged and the current workflow statement remains accurate. |

## Evidence-backed concept relationships

- Mag/Pixel setup guide -> shares FOV and nm/px calculations with -> Skewvoir gallery calibration (`app/utils/magPixel.ts`, `app/utils/skewvoirAnalysis/gallery.ts`).
- Skewvoir measurement-point selection -> surfaces identity consistently across -> measurement table, wafer map, radius plot, and distribution (`useSkewvoirAnalysis.ts`, `siteColors.ts`, chart components).
- Skewvoir FDC matrix model -> ranks and groups -> dynamic FDC parameters relative to `cd_value` (`skewvoirAnalysis/paramMatrix.ts`).
- Skewvoir matrix component -> is intended to dispatch to -> shared sequence cursor and detailed FDC panes (`ParamMatrix.vue`; worktree `SequenceWorkbench.vue`).
- ECharts theme selection -> configures presentation colors for -> Skewvoir and other chart workflows (`useEchartsTheme.ts`, `useChartPalette.ts`, `useEchart.ts`).
- SCE history documents -> collapse into -> coefficient revisions (`sceHistory.ts`, `ScePanel.vue`).
- Workflow behavior -> is guarded by -> focused frontend pure-utility and backend contract tests (`*.test.ts`, `hardware/tests/test_sce.py`).

## Remaining questions and boundaries

- The matrix component/model are committed, but mounting and click-to-detail drill-down exist only in the current worktree. Document this distinction rather than presenting worktree behavior as released.
- The minimum px/CD threshold is explicitly provisional; do not present the default value as an approved metrology standard.
- Browser-level interaction coverage is still absent for the new keyboard, linked selection, matrix drill-down, and Mag/Pixel rendering flows.
