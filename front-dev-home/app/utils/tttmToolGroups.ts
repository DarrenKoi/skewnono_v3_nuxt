// Grouping the TTTM fleet picker's tools by model code.
//
// A fab holds up to ~18 CD-SEMs, which is more chips than anyone reads as a
// flat row, and the selection a user actually wants is almost always "the
// CG6300s" or "everything except the drifted one" — matching tools by series
// is how a skew comparison gets scoped. So the picker groups by
// `eqp_model_cd` and lets a whole series be toggled at once.
//
// Selection stays a flat list of eqp_ids (that is what the payload subsetting
// in tttmFleetSubset.ts takes, and what usePersistedState stores); the groups
// are purely a way to reach into it.

export interface GroupableTool {
  eqp_id: string
  eqp_model_cd: string
}

export interface ToolGroup<T extends GroupableTool> {
  model: string
  tools: T[]
}

/**
 * Tools bucketed by model code, groups in model-code order.
 *
 * Within a group the fleet's own order is preserved, so a chip never moves
 * because a sibling was selected. A tool whose model code is missing or blank
 * is filed under '기타' rather than dropped — the picker is the only way to
 * reach a tool, and a tool that cannot be reached cannot be compared.
 */
export const groupToolsByModel = <T extends GroupableTool>(tools: readonly T[]): ToolGroup<T>[] => {
  const buckets = new Map<string, T[]>()
  for (const tool of tools) {
    const model = tool.eqp_model_cd?.trim() || '기타'
    const bucket = buckets.get(model)
    if (bucket) bucket.push(tool)
    else buckets.set(model, [tool])
  }
  return [...buckets.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([model, groupTools]) => ({ model, tools: groupTools }))
}

/**
 * `wanted` re-expressed in fleet order.
 *
 * Every selection change goes through this, so the stored list never depends
 * on the order the user happened to click in — two users who selected the same
 * tools have byte-identical settings, and a diff of the stored value means a
 * different selection rather than a different click order.
 */
export const orderSelection = (
  fleet: readonly string[],
  wanted: ReadonlySet<string>
): string[] => fleet.filter(eqp => wanted.has(eqp))
