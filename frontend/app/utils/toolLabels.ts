// One place to turn an `eqp_id` into something a person reads.
//
// Four tttm components each hand-rolled `tools.find(t => t.eqp_id === eqp)`,
// which cost an O(n) scan per label per redraw (the chart formatters call it
// once per point) and meant a change to the label convention had to be found in
// four files — one of which, PairMatrix's `shortLabel`, had already drifted.

interface ToolRefLike {
  eqp_id: string
  label: string
}

export interface ToolLabels {
  /** Full label, e.g. "CD-SEM 01". Falls back to the raw id when unknown. */
  labelFor: (eqp: string) => string
  /** Label minus the prefix every tool shares, e.g. "01". For dense axes. */
  shortLabel: (eqp: string) => string
}

/**
 * The prefix shared by every label, trimmed back to a word boundary.
 *
 * The trim is the whole trick. A raw common prefix of
 * ["CD-SEM 01" … "CD-SEM 05"] is "CD-SEM 0" — the digits agree too — which
 * would shorten them to "1".."5" and quietly renumber the fleet. Cutting at the
 * last space yields "CD-SEM " and the intended "01".."05".
 *
 * Derived rather than hardcoded because `.replace('CD-SEM ', '')` (what
 * PairMatrix used to do) silently stops shortening the moment an HV-SEM fleet
 * is rendered, and the contract's ToolSlug already admits `hvsem`.
 */
const sharedPrefix = (labels: string[]): string => {
  if (labels.length < 2) return ''
  let prefix = labels[0] ?? ''
  for (const label of labels.slice(1)) {
    let i = 0
    while (i < prefix.length && i < label.length && prefix[i] === label[i]) i++
    prefix = prefix.slice(0, i)
    if (!prefix) return ''
  }
  const cut = prefix.lastIndexOf(' ')
  return cut < 0 ? '' : prefix.slice(0, cut + 1)
}

/** Build the labellers once per tool list — the lookup is a Map, not a scan. */
export const toolLabels = (tools: readonly ToolRefLike[]): ToolLabels => {
  const byId = new Map(tools.map(t => [t.eqp_id, t.label]))
  const prefix = sharedPrefix(tools.map(t => t.label))

  const labelFor = (eqp: string) => byId.get(eqp) ?? eqp

  return {
    labelFor,
    shortLabel: (eqp: string) => {
      const label = byId.get(eqp)
      if (label === undefined) return eqp
      // Never return an empty string: a label identical to the shared prefix
      // would otherwise vanish from the axis entirely.
      const short = prefix && label.startsWith(prefix) ? label.slice(prefix.length) : label
      return short || label
    }
  }
}
