// Builds the wafer-map hover tooltip HTML. Kept pure (no ECharts types) so it
// can be unit-tested; the leaf component feeds it per-point identity + value.
export interface WaferTooltipInput {
  seq: string
  field: string | null // chip_number (die index) — the "field info"
  mp: number | null // representative mp_number for the die
  n: number // measurements aggregated into this point
  param: string
  value: number | null // null → measurement failure
  unit: string
}

export const formatWaferTooltip = (i: WaferTooltipInput): string => {
  const lines: string[] = [`seq ${i.seq}`]
  if (i.field != null) lines.push(`Field ${i.field}`)
  if (i.mp != null) lines.push(i.n > 1 ? `MP ${i.mp} · avg of ${i.n} pts` : `MP ${i.mp}`)
  lines.push(i.value != null ? `${i.param}: <b>${i.value}</b> ${i.unit}` : '측정 실패')
  return lines.join('<br/>')
}
