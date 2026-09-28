import type { FdcFleet, FdcFleetTool } from '~/composables/useHardwareApi'

const finite = (value: number | null): value is number => value !== null && Number.isFinite(value)

export const fdcFleetHeatmap = (tools: FdcFleetTool[]) => {
  const ordered = tools.filter(tool => finite(tool.temp_c) && tool.temp_days.some(day => Number.isFinite(day.temp_c)))
    .sort((a, b) => b.temp_c! - a.temp_c! || a.eqp_id.localeCompare(b.eqp_id))
  const days = [...new Set(ordered.flatMap(tool => tool.temp_days.map(day => day.day)))].sort()
  const dayIndex = new Map(days.map((day, index) => [day, index]))
  const points: [number, number, number][] = ordered.flatMap((tool, toolIndex) =>
    tool.temp_days.filter(day => Number.isFinite(day.temp_c)).map(day => [dayIndex.get(day.day)!, toolIndex, day.temp_c] as [number, number, number])
  )
  const values = points.map(point => point[2])
  return { tools: ordered.map(tool => tool.eqp_id), days, points, min: Math.min(...values), max: Math.max(...values) }
}

export const fdcFleetLaserRows = (tools: FdcFleetTool[]) =>
  tools.filter(tool => finite(tool.laser_x1))
    .map(tool => ({ eqpId: tool.eqp_id, x1: tool.laser_x1!, y1: finite(tool.laser_y1) ? tool.laser_y1 : null }))
    .sort((a, b) => b.x1 - a.x1 || a.eqpId.localeCompare(b.eqpId))

export const fdcFleetPinRows = (tools: FdcFleetTool[]) =>
  tools.map((tool) => {
    const counts = tool.pin_counts
    const ok = counts.Conduction ?? 0
    const warn = counts.UnstableConduction ?? 0
    const bad = counts.NonConduction ?? 0
    const total = ok + warn + bad
    return {
      eqpId: tool.eqp_id, ok, warn, bad, total,
      greenRate: total ? ok / total : 0,
      percent: { ok: total ? ok / total * 100 : 0, warn: total ? warn / total * 100 : 0, bad: total ? bad / total * 100 : 0 }
    }
  }).filter(row => row.total > 0)
    .sort((a, b) => a.greenRate - b.greenRate || a.eqpId.localeCompare(b.eqpId))

export const fdcFleetHistogram = (fleet: FdcFleet) => {
  const bins = [...new Set(fleet.spread_bins.map(bin => bin.lo))].sort((a, b) => a - b)
  const judgements = ['Conduction', 'UnstableConduction', 'NonConduction'] as const
  const series = judgements.map(judgement => ({
    judgement,
    counts: bins.map(lo => fleet.spread_bins
      .filter(bin => bin.judgement === judgement && bin.lo === lo)
      .reduce((sum, bin) => sum + bin.count, 0))
  }))
  return {
    bins, labels: bins.map(lo => `${lo}–${lo + fleet.spread_bin_width}`),
    // Bars sit at bin CENTRES on a value axis, so a threshold band drawn in
    // spread units (15-20) lines up with the bins it covers.
    series: series.map(row => ({
      ...row,
      points: bins.map((lo, i) => [lo + fleet.spread_bin_width / 2, row.counts[i] ?? 0] as [number, number])
    }))
  }
}

export const fdcFleetCounterRows = (tools: FdcFleetTool[]) =>
  tools.flatMap(tool => tool.counter_rates.map(rate => ({ eqpId: tool.eqp_id, ...rate })))
    .sort((a, b) => (b.per_day ?? -Infinity) - (a.per_day ?? -Infinity)
      || a.eqpId.localeCompare(b.eqpId) || a.channel.localeCompare(b.channel))
