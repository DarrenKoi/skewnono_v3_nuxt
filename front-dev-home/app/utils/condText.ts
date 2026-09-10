// Relative (not `~/`) so `npm test` can load this module under plain node.
import type { SettingBlock, SettingRow } from '../composables/useRecipeParamDetail'

/**
 * A `.{image}/cond.txt` body as the SettingBlock the recipe-open tables render.
 *
 * The tool writes one `key<TAB>value` per line under a `# Observation condition`
 * header (office 확인 2026-06-08, auto_recipe_creator workflow_2 cond_sample.txt).
 * Values stay verbatim strings — the unit lives inside them ("500 V"), so
 * nothing downstream may parse them as numbers. Twin of `cond_lines()` in
 * back_dev_home/_core/cond_cursor.py; the msr-image route ships the raw body
 * in the `X-Msr-Cond` header rather than parsing it, so the split lives here.
 */
export function parseCondText(text: string, source = 'cond.txt'): SettingBlock {
  const rows: SettingRow[] = []
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim()
    if (!line || line.startsWith('#')) continue
    const [, key = '', value = ''] = /^(\S+)\s*(.*)$/.exec(line) ?? []
    if (key) rows.push({ key, value: value.trim() })
  }
  return { source, rows }
}
