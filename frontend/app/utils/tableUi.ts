/**
 * The UTable slot classes the ebeam analytics tables share.
 *
 * Four tables bind this — recipe-tat's fleet table and equipment compare, and
 * fail-issue's twins of both — and it was byte-identical in all four until
 * 2026-08-09. The cost was already proven once: the d48d592b DESIGN.md sweep
 * (drop the header background, take `.sk-label`) had to make the same edit in
 * every copy, and DESIGN.md sweeps are a recurring event here. The next one
 * touches this file.
 *
 * The zinc in `tr` is deliberate and sanctioned: DESIGN.md keeps zinc for
 * table hovers and the empty-state message, and nowhere else.
 *
 * NOT the same preset as `recipeTableUi` (utils/recipeView.ts), which the
 * recipe-search tables use. That one still carries the pre-sweep header
 * (a zinc header band and an ad-hoc 11px size) rather than `.sk-label`. Do not
 * merge them without deciding which header the recipe-search tables should
 * have — that is a design decision, not a refactor.
 *
 * OPEN, for the next sweep: `td` still spells out `text-[12px] … text-(--sk-ink)`
 * where DESIGN.md now prefers the semantic `.sk-value`. `FailIssueRankingTable`
 * already uses it and could share this preset afterwards. Left as-is here
 * because `.sk-value` also sets weight 500 — a real visual change, and this
 * extraction was meant to render identically.
 */
export const analyticsTableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
  th: 'py-2 px-3 sk-label'
} as const
