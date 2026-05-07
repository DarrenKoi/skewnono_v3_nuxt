import * as echarts from 'echarts'
import type { ComputedRef, Ref } from 'vue'
import type { ECharts, EChartsOption } from 'echarts'

export const useEchart = (
  elRef: Ref<HTMLDivElement | null>,
  optionRef: ComputedRef<EChartsOption>
) => {
  const colorMode = useColorMode()
  const themeName = computed(() => colorMode.value === 'dark' ? 'dark' : 'vintage')

  let chart: ECharts | null = null
  let resizeHandler: (() => void) | null = null

  const ensureChart = () => {
    if (chart || !elRef.value) return
    chart = echarts.init(elRef.value, themeName.value)
    chart.setOption(optionRef.value)
    if (!resizeHandler) {
      resizeHandler = () => chart?.resize()
      window.addEventListener('resize', resizeHandler)
    }
  }

  onMounted(() => {
    ensureChart()
  })

  // Containers may be inside a v-if, so the element ref appears later.
  watch(elRef, (next) => {
    if (next) ensureChart()
  })

  watch(optionRef, (next) => {
    chart?.setOption(next, true)
  })

  // ECharts binds a theme at init time; swapping themes requires
  // dispose + re-init on the same DOM node.
  watch(themeName, () => {
    if (!elRef.value) return
    chart?.dispose()
    chart = echarts.init(elRef.value, themeName.value)
    chart.setOption(optionRef.value)
  })

  onBeforeUnmount(() => {
    if (resizeHandler) {
      window.removeEventListener('resize', resizeHandler)
      resizeHandler = null
    }
    chart?.dispose()
    chart = null
  })
}
