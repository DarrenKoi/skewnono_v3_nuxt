// front-dev-home/app/utils/chartExport.ts
// Pure helpers for exporting a chart as a downloadable PNG. Kept free of DOM /
// Nuxt / ECharts imports so the filename logic is unit-testable in isolation;
// the DOM wiring that consumes these lives in composables/useEchart.ts.

// Lowercase, replace any run of non-alphanumerics with a single hyphen, and
// trim leading/trailing hyphens. Empty result falls back to 'chart'.
export const slugifyChartName = (raw: string): string => {
  const slug = raw
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  return slug || 'chart'
}

// Local calendar date as YYYY-MM-DD (month is 0-indexed on Date).
export const formatDateStamp = (date: Date): string => {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

// Preferred filename base is the caller-supplied exportName, else the chart's
// own title text, else the literal 'chart'. Blank/whitespace inputs are ignored.
export const chartExportFilename = (
  exportName: string | undefined,
  titleText: string | undefined,
  date: Date
): string => {
  const base = exportName?.trim() || titleText?.trim() || 'chart'
  return `${slugifyChartName(base)}-${formatDateStamp(date)}.png`
}
