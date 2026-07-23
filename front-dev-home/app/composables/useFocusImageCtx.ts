import { computed, type ComputedRef } from 'vue'
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

export interface FocusImageCtx {
  eqp_ip: string
  class_name: string
  msr: string
}

// The (eqp_ip, class_name, msr) an msr_image request needs, derived once from
// the focus MSR's meas_hist row. Empty strings when no focus row is loaded, so
// callers can gate on `eqp_ip` before building an image URL. Shared by the
// skewvoir gallery/dashboard/drawer components instead of re-derived in each.
export function useFocusImageCtx(analysis: SkewvoirAnalysis): ComputedRef<FocusImageCtx> {
  return computed(() => {
    const row = analysis.focusRow.value
    return {
      eqp_ip: row?.eqp_ip ?? '',
      class_name: row?.class_name ?? '',
      msr: analysis.focusMsr.value ?? ''
    }
  })
}
