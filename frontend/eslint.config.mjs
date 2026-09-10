// @ts-check
import withNuxt from './.nuxt/eslint.config.mjs'

export default withNuxt(
  {
    // Vendor ECharts theme files (UMD bundles from echarts.apache.org).
    // Kept verbatim for reference — the values are mirrored in
    // app/utils/echartsThemes.ts for ESM consumption.
    ignores: ['app/assets/echarts-theme/**']
  }
)
