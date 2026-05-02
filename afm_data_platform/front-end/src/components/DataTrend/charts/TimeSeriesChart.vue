<template>
  <div ref="chartContainer" :style="{ height: chartHeight + 'px' }"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import * as echarts from 'echarts'
import shineThemeData from '@/plugins/shine.json'

const props = defineProps({
  timeSeriesData: {
    type: Array,  // Array of series objects: [{name: 'site', data: [...]}, ...]
    default: () => []
  },
  selectedColumn: {
    type: String,
    default: ''
  },
  chartHeight: {
    type: Number,
    default: 600
  },
  loading: {
    type: Boolean,
    default: false
  }
})

const chartContainer = ref(null)
let chartInstance = null

// Helper function to combine date and time strings into a Date object
const parseDateTime = (dateStr, timeStr) => {
  if (!dateStr || !timeStr) return null

  // Parse date string (YYMMDD format)
  const year = 2000 + parseInt(dateStr.substring(0, 2), 10)
  const month = parseInt(dateStr.substring(2, 4), 10) - 1 // Month is 0-indexed
  const day = parseInt(dateStr.substring(4, 6), 10)

  // Parse time string (HHMMSS format)
  const hours = parseInt(timeStr.substring(0, 2), 10)
  const minutes = parseInt(timeStr.substring(2, 4), 10)
  const seconds = parseInt(timeStr.substring(4, 6), 10)

  return new Date(year, month, day, hours, minutes, seconds)
}

// Computed property to format the chart data
const chartData = computed(() => {
  if (!props.timeSeriesData || props.timeSeriesData.length === 0) {
    return { allTimestamps: [], series: [] }
  }

  // Collect all unique timestamps and sort them
  const allTimestampsSet = new Set()
  props.timeSeriesData.forEach(series => {
    if (series && series.data && Array.isArray(series.data)) {
      series.data.forEach(item => {
        if (item && item.date && item.time) {
          const combinedDateTime = parseDateTime(item.date, item.time)
          if (combinedDateTime) {
            allTimestampsSet.add(combinedDateTime.getTime())
          }
        }
      })
    }
  })

  const allTimestamps = Array.from(allTimestampsSet).sort((a, b) => a - b)

  // Format timestamps for display (Korean-friendly format: yy/mm/dd hh:mm:ss)
  const formattedTimestamps = allTimestamps.map(timestamp => {
    const date = new Date(timestamp)
    const year = String(date.getFullYear()).slice(-2)
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')

    return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`
  })

  // Process each series
  const processedSeries = props.timeSeriesData.map((series, seriesIndex) => {
    if (!series || !series.data || !Array.isArray(series.data)) {
      return { name: series?.name || `Series ${seriesIndex}`, data: [], rawData: [] }
    }

    // Sort series data by combined timestamp
    const sortedData = [...series.data]
      .map(item => {
        const combinedDateTime = parseDateTime(item.date, item.time)
        return {
          ...item,
          combinedTimestamp: combinedDateTime
        }
      })
      .filter(item => item.combinedTimestamp !== null)
      .sort((a, b) => a.combinedTimestamp - b.combinedTimestamp)

    // Convert to scatter plot format
    const scatterData = sortedData.map(item => {
      const timestampIndex = allTimestamps.indexOf(item.combinedTimestamp.getTime())
      return {
        value: [timestampIndex, item.value],
        timestamp: item.combinedTimestamp,
        lotId: item.lotId,
        recipe: item.recipe,
        site: item.site,
        date: item.date,
        time: item.time
      }
    })

    return {
      name: series.name,
      data: scatterData,
      rawData: sortedData
    }
  })

  return {
    allTimestamps: formattedTimestamps,
    series: processedSeries
  }
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

  const { allTimestamps, series } = chartData.value

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: function (params) {
        const dataItem = params.data
        // Format timestamp to Korean-friendly format
        const date = dataItem.timestamp
        const year = String(date.getFullYear()).slice(-2)
        const month = String(date.getMonth() + 1).padStart(2, '0')
        const day = String(date.getDate()).padStart(2, '0')
        const hours = String(date.getHours()).padStart(2, '0')
        const minutes = String(date.getMinutes()).padStart(2, '0')
        const seconds = String(date.getSeconds()).padStart(2, '0')
        const formattedTime = `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`

        return `
          <div style="padding: 8px;">
            <div style="font-weight: bold; margin-bottom: 4px;">${params.seriesName}</div>
            <div>Time: ${formattedTime}</div>
            <div>Value: ${dataItem.value[1].toFixed(3)} nm</div>
            <div style="color: #666; font-size: 12px; margin-top: 4px;">
              Date: ${dataItem.date || 'N/A'} | Time: ${dataItem.time || 'N/A'}<br/>
              Lot: ${dataItem.lotId || 'N/A'}<br/>
              Recipe: ${dataItem.recipe || 'N/A'}
            </div>
          </div>
        `
      }
    },
    legend: {
      data: series.map(s => s.name),  // Only show original site names
      top: 10,
      textStyle: {
        fontSize: 14,
        fontWeight: 'bold'
      },
      selectedMode: false,
      orient: 'horizontal'
    },
    grid: {
      left: '8%',
      right: '8%',
      bottom: '10%',
      top: '10%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: allTimestamps,
      name: 'Time',
      nameLocation: 'end',
      nameGap: 20,
      nameTextStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      },
      axisLabel: {
        rotate: 45,
        fontSize: 13,
        margin: 10,
        interval: 0,
        fontWeight: '500'
      },
      axisTick: {
        alignWithLabel: true,
        length: 8
      }
    },
    yAxis: {
      type: 'value',
      name: `${props.selectedColumn}`,
      nameLocation: 'end',
      nameGap: 20,
      nameTextStyle: {
        fontSize: 16,
        fontWeight: 'bold'
      },
      axisLabel: {
        formatter: '{value}',
        fontSize: 13,
        fontWeight: '500'
      }
    },
    series: series.flatMap((seriesData, index) => {
      // Get theme colors
      const themeColors = shineThemeData.color
      const seriesColor = themeColors[index % themeColors.length]

      return [
        // Line series for connections
        {
          name: `${seriesData.name}_line`,  // Different name to avoid legend conflict
          type: 'line',
          data: seriesData.data.map(item => item.value),
          lineStyle: {
            width: 2,
            color: seriesColor
          },
          itemStyle: {
            color: seriesColor
          },
          symbol: 'none', // Hide symbols on line
          showSymbol: false,
          smooth: false,
          silent: true, // Make line non-interactive
          legendHoverLink: false
        },
        // Scatter series for points with lot ID labels
        {
          name: seriesData.name,
          type: 'scatter',
          data: seriesData.data,
          symbolSize: 14,
          itemStyle: {
            color: seriesColor
          },
          label: {
            show: true,
            position: 'top',
            formatter: function (params) {
              return params.data.lotId || ''
            },
            fontSize: 10,
            fontWeight: 'bold',
            color: '#333',
            backgroundColor: 'rgba(255, 255, 255, 0.8)',
            padding: [2, 4],
            borderRadius: 3
          },
          emphasis: {
            focus: 'series',
            itemStyle: {
              shadowBlur: 10,
              shadowColor: 'rgba(0, 0, 0, 0.5)',
              color: seriesColor
            },
            label: {
              show: true
            }
          }
        }
      ]
    }),
    dataZoom: [
      {
        type: 'inside',
        start: 0,
        end: 100
      },
      {
        type: 'slider',
        start: 0,
        end: 100,
        height: 30,
        bottom: 20
      }
    ]
  }

  // Show loading animation if data is being loaded
  if (props.loading) {
    chartInstance.showLoading({
      text: 'Loading time series data...',
      color: '#1976d2',
      textColor: '#000',
      maskColor: 'rgba(255, 255, 255, 0.8)',
      zlevel: 0
    })
  } else {
    chartInstance.hideLoading()
  }

  chartInstance.setOption(option)
}

function handleResize() {
  if (chartInstance) {
    chartInstance.resize()
  }
}

// Watch for data changes
watch([
  () => props.timeSeriesData,
  () => props.selectedColumn,
  () => props.loading
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
/* Chart container will be sized by parent */
</style>
