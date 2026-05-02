<template>
  <div class="scatter-chart-container">
    <div ref="chartContainer" class="echarts-instance"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import * as echarts from 'echarts'
import shineThemeData from '@/plugins/shine.json'

const props = defineProps({
  summaryData: {
    type: Array,
    default: () => []
  },
  selectedStatistic: {
    type: String,
    default: 'MEAN'
  },
  selectedMeasurements: {
    type: Array,
    default: () => []
  }
})

const chartContainer = ref(null)
let chartInstance = null

const chartData = computed(() => {
  if (!props.summaryData || props.summaryData.length === 0) return { series: [], xAxisData: [] }

  console.log('🔍 [StatisticalScatterChart] Processing summary data:', props.summaryData)

  // Get unique sites (measurement points) for X-axis
  const uniqueSites = [...new Set(props.summaryData.map(row => row.Site).filter(site => site !== null && site !== undefined))]
  console.log('🔍 [StatisticalScatterChart] Unique sites:', uniqueSites)

  // Find all columns containing "(nm)" for Y-axis data
  const firstRecord = props.summaryData[0]
  const nmColumns = Object.keys(firstRecord).filter(key =>
    key.includes('(nm)') && key !== 'ITEM' && key !== 'Site'
  )
  console.log('🔍 [StatisticalScatterChart] Columns with (nm):', nmColumns)

  // Create series for each selected measurement type and statistic combination
  const series = props.selectedMeasurements.map((measurement, index) => {
    const data = uniqueSites.map((site, siteIndex) => {
      // Find the record for this site and the selected statistic
      const record = props.summaryData.find(r =>
        r.Site === site && r.ITEM === props.selectedStatistic
      )

      if (record) {
        // Look for the measurement value in the record
        let value = null

        // Try to find the exact column name that matches the measurement
        const matchingColumn = nmColumns.find(col =>
          col.toLowerCase().includes(measurement.toLowerCase()) ||
          measurement.toLowerCase().includes(col.toLowerCase().replace('(nm)', '').trim())
        )

        if (matchingColumn) {
          value = record[matchingColumn]
        } else {
          // Fallback: use any available nm column
          for (const col of nmColumns) {
            if (record[col] !== undefined && record[col] !== null) {
              value = record[col]
              break
            }
          }
        }

        return [siteIndex, value || 0]
      }

      return [siteIndex, 0]
    })

    return {
      name: measurement,
      type: 'line',
      symbol: 'circle',
      symbolSize: 14,
      data: data,
      lineStyle: {
        width: 1
      },
      emphasis: {
        focus: 'series'
      }
    }
  })

  console.log('🔍 [StatisticalScatterChart] Generated series:', series)
  return { series, xAxisData: uniqueSites }
})

function initChart() {
  if (!chartContainer.value) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  // Register the shine theme
  echarts.registerTheme('shine', shineThemeData)

  // Initialize chart with shine theme
  chartInstance = echarts.init(chartContainer.value, 'shine')

  const { series, xAxisData } = chartData.value

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: function (params) {
        const xIndex = params.data[0]
        const pointName = xAxisData[xIndex]
        return `${params.seriesName}<br/>${pointName}: ${params.data[1].toFixed(3)}`
      },
      textStyle: {
        fontSize: 18,
        fontWeight: 'bold'
      }
    },
    legend: {
      data: props.selectedMeasurements,
      bottom: 0,
      textStyle: {
        fontSize: 14,
        fontWeight: 'bold'
      },
      selectedMode: false
    },
    grid: {
      left: '10%',
      right: '5%',
      bottom: '15%',
      top: '5%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: xAxisData,
      name: 'Site (Measurement Points)',
      nameLocation: 'middle',
      nameGap: 45,
      nameTextStyle: {
        fontSize: 14,
        fontWeight: 'bold'
      },
      axisLabel: {
        rotate: 45,
        interval: 0,
        fontSize: 12,
        fontWeight: 'bold'
      }
    },
    yAxis: {
      type: 'value',
      name: `${props.selectedStatistic} Value (nm)`,
      nameLocation: 'middle',
      nameGap: 50,
      nameTextStyle: {
        fontSize: 14,
        fontWeight: 'bold'
      },
      axisLabel: {
        formatter: '{value}',
        fontSize: 12,
        fontWeight: 'bold'
      }
    },
    series: series
  }

  chartInstance.setOption(option)
}

function handleResize() {
  if (chartInstance) {
    chartInstance.resize()
  }
}

watch([
  () => props.summaryData,
  () => props.selectedStatistic,
  () => props.selectedMeasurements
], () => {
  initChart()
}, { deep: true })

onMounted(() => {
  initChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (chartInstance) {
    chartInstance.dispose()
  }
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.scatter-chart-container {
  width: 100%;
  height: 100%;
  min-height: 550px;
  position: relative;
  display: flex;
  flex-direction: column;
}

.echarts-instance {
  width: 100%;
  height: 100%;
  min-height: 550px;
}
</style>
