import type { ToolType } from '~/stores/navigation'

/**
 * Tool type from an equipment model code, or null for a model we do not know.
 *
 * Lives in utils rather than beside `useSemListApi` because it is a pure
 * function that `pendingToolMatrix.ts` needs at runtime, and `npm test` runs
 * `node --test` with no bundler — a runtime `~/composables/…` import would not
 * resolve. Callers are unaffected: nothing imports this explicitly, they all
 * reach it through Nuxt auto-import, which covers utils and composables alike.
 *
 * Note this DISAGREES with the backend's `_tool_specs.model_to_tool_type()`,
 * which returns None for the two AMAT families. Reconciling the two is real
 * work, tracked separately.
 */
export const classifyToolType = (eqpModelCd: string): ToolType | null => {
  if (eqpModelCd.startsWith('CG') || eqpModelCd.startsWith('GT')) return 'cd-sem'
  if (eqpModelCd.startsWith('TP')) return 'hv-sem'
  if (eqpModelCd.startsWith('VERITYSEM')) return 'verity-sem'
  if (eqpModelCd.startsWith('PROVISION')) return 'provision'
  return null
}
