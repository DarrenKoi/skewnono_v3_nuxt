/**
 * The one switch for AFM Metrology's visibility. `true` shows the landing-page
 * card and lets `/afm/*` through; `false` hides the card and makes
 * `middleware/afm-hidden.global.ts` redirect `/afm/*` to `/`.
 */
export const AFM_ENABLED = true

export const useAfmEnabled = () => AFM_ENABLED
