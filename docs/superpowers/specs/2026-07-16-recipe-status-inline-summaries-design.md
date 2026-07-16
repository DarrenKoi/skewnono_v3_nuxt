# Recipe Status Inline Summaries

## Goal

Move the high-level summary values for Recipe TAT, Align Fail, and Meas Fail into their ranking table headers. Remove the standalone KPI strips so the summaries stay close to the ranked data they describe.

## Scope

The change applies only to the Nuxt frontend components used by the `recipe-status` page. Existing backend endpoints, response shapes, filters, charts, tables, downloads, and row actions remain unchanged.

## Layout

Use one small reusable inline-summary component to render compact label-value items. It must wrap on narrow screens and preserve the existing table title, row-count badge, capped indicator, and table controls.

The headers show these values:

- `Align fails by recipe`: Align fails, Total measurements, Fail ratio.
- `Meas fails by recipe`: Meas fails, Total measurements, Fail ratio.
- `Ranked recipes`: Total TAT, Distinct recipes, Total executions, Avg meastime.

Remove the two standalone fail KPI strips and the standalone TAT KPI strip.

## Data Behavior

All values come from the existing server summary response for the active tool type, fab, device selection, and date range. Table search, sorting, and pagination do not recalculate or alter the summary values.

Use the existing number, percentage, and duration formatters. When a value is temporarily unavailable, render an em dash instead of deriving a value from table rows.

## Component Changes

- Add a reusable E-beam inline-summary presentation component with typed label-value items.
- Allow `FailIssueRankingTable` to receive optional summary items and render them beside its title.
- Pass the aspect-specific Align and Meas summary items from `FailIssueView`.
- Render the same inline-summary component beside `Ranked recipes` in `RecipeTatView`.
- Delete KPI-only computed values and template markup that become unused.

## Verification

- Run frontend lint and type checking.
- Confirm the three standalone KPI strips are absent.
- Confirm each ranking header shows the agreed values for both overall and device-specific views.
- Confirm changing the date range or selected device refreshes the summary.
- Confirm searching, sorting, paginating, copying, and downloading still behave as before.
