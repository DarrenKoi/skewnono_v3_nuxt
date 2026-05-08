import * as echarts from 'echarts'
import type { ComputedRef, Ref } from 'vue'
import type { ECharts, EChartsOption } from 'echarts'

interface UseEchartOptions {
  // Fired when a series element (e.g. a bar) is clicked. Receives the
  // x-axis category for category-bucketed series — for our charts that's
  // the lot_cd, since xAxis.data is built from lot labels.
  onClick?: (name: string) => void
}

export const useEchart = (
  elRef: Ref<HTMLDivElement | null>,
  optionRef: ComputedRef<EChartsOption>,
  options: UseEchartOptions = {}
) => {
  const colorMode = useColorMode()
  const themeName = computed(() => colorMode.value === 'dark' ? 'dark' : 'vintage')

  let chart: ECharts | null = null
  let resizeHandler: (() => void) | null = null

  const bindClick = () => {
    const callback = options.onClick
    if (!chart || !callback) return
    chart.on('click', (params) => {
      if (params.componentType !== 'series') return
      const name = (params as { name?: string }).name
      if (typeof name === 'string' && name.length > 0) callback(name)
    })
  }

  const ensureChart = () => {
    if (chart || !elRef.value) return
    chart = echarts.init(elRef.value, themeName.value)
    chart.setOption(optionRef.value)
    bindClick()
    if (!resizeHandler) {
      resizeHandler = () => chart?.resize()
      window.addEventListener('resize', resizeHandler)
    }
  }

  onMounted(() => {
    ensureChart()
  })

  // Containers may be inside a v-if and toggle on/off. When the previous
  // element unmounts, dispose the instance bound to it; when a fresh element
  // mounts, init against the new node. ensureChart() short-circuits when
  // chart is already truthy, so without this dispose the new container would
  // never receive an echarts instance after the first remount.
  watch(elRef, (next, prev) => {
    if (prev && prev !== next) {
      chart?.dispose()
      chart = null
    }
    if (next) ensureChart()
  })

  watch(optionRef, (next) => {
    chart?.setOption(next, true)
  })

  // ECharts binds a theme at init time; swapping themes requires
  // dispose + re-init on the same DOM node. Click handler is bound to the
  // instance, so it must be re-attached after re-init.
  watch(themeName, () => {
    if (!elRef.value) return
    chart?.dispose()
    chart = echarts.init(elRef.value, themeName.value)
    chart.setOption(optionRef.value)
    bindClick()
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
