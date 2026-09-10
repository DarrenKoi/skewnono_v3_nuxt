import { computed, type ComputedRef } from 'vue'
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'

export interface FocusImageCtx {
  eqp_ip: string
  class_name: string
  msr: string
}

// The (eqp_ip, class_name, msr) an msr_image request needs. Empty strings when
// the focus MSR's address is unknown, so callers can gate on `eqp_ip` before
// building an image URL. Shared by the skewvoir gallery/dashboard/drawer
// components instead of re-derived in each.
//
// Read from the msr_file response FIRST, and only then from the meas_hist row.
// The row is whatever the cached landing list happens to hold, so a measurement
// opened from a search hit or a shared deep link has no row — that used to leave
// eqp_ip empty and render 이미지 없음 on every image in the page while the
// numbers loaded fine. The msr_file response is keyed on the focus msr itself
// and resolves the tool address server-side, so it answers for any MSR.
export function useFocusImageCtx(analysis: SkewvoirAnalysis): ComputedRef<FocusImageCtx> {
  return computed(() => {
    const msr = analysis.focusMsr.value ?? ''
    // Guarded on the echoed msr: focusFile keeps the PREVIOUS response until the
    // next one resolves, and an unguarded read would address the newly-focused
    // measurement's images at the previously-focused tool.
    const file = analysis.focusFile.value
    const fresh = file && file.msr === msr ? file : null
    const row = analysis.focusRow.value
    return {
      eqp_ip: fresh?.eqp_ip || row?.eqp_ip || '',
      class_name: fresh?.class_name || row?.class_name || '',
      msr
    }
  })
}
