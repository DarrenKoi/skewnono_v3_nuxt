// The `ui` preset shared by the scope pickers (RECIPE, PARAMETER).
//
// NuxtUI pins a menu to its trigger (`w-(--reka-select-trigger-width)` in
// .nuxt/ui/select-menu.ts), and each trigger is one cell of a scope bar — about
// half of the bar's free width, and narrower still once the bar wraps. A
// class/recipe full name such as CD_MONITOR/CD_MONITORING_HR_800V_X_FULL_NEW5
// does not fit in that, and two recipes differing only in their suffix become
// indistinguishable in the list you pick from. So the POPPER widens instead of
// the cell: it floats over the results below, where the space already exists.
// Bounded by the viewport so a narrow window cannot push it off-screen.
//
// One constant rather than a copy per picker, for the reason utils/tableUi.ts
// exists: a DESIGN.md sweep otherwise has to find every copy.
export const scopeMenuUi = {
  content: 'w-auto min-w-full max-w-[min(48rem,calc(100vw-2rem))]',
  item: 'font-mono text-[13px]'
}
