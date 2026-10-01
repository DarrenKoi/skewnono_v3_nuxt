// Pure helpers for the AFM summary table ({ Site, ITEM, <measurement columns…> }
// rows). No DOM/Nuxt imports so they run under `node --test`.
import { collectColumns } from './afmExport.ts'

// Measurement columns: every key any row carries, except the two id columns.
export const summaryColumns = (summary: Record<string, unknown>[]): string[] =>
  collectColumns(summary, []).filter(k => k !== 'Site' && k !== 'ITEM')

// A summary cell as a number. The payload is an untyped dataframe dict, so a
// numeric cell may arrive as a string; anything unparseable is null, never 0.
export const summaryNumber = (raw: unknown): number | null => {
  const n = typeof raw === 'string' && raw.trim() ? Number(raw) : raw
  return typeof n === 'number' && Number.isFinite(n) ? n : null
}
