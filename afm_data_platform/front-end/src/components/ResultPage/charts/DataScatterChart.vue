<template>
  <div class="scatter-chart-container">
    <div v-if="!chartConfig" class="no-data-container">
      <div class="text-center pa-6 text-medium-emphasis">
        <v-icon size="64" color="grey" class="mb-3">mdi-chart-scatter-plot</v-icon>
        <div class="text-h6 mb-2">No Chart Configuration</div>
        <div class="text-body-2">Select X and Y axis columns above to generate scatter chart</div>
      </div>
    </div>
    
    <div v-else-if="!chartConfig.data || chartConfig.data.length === 0" class="no-data-container">
      <div class="text-center pa-6 text-medium-emphasis">
        <v-icon size="64" color="warning" class="mb-3">mdi-alert-circle</v-icon>
        <div class="text-h6 mb-2">No Valid Data</div>
        <div class="text-body-2">No data points available for the selected columns</div>
      </div>
    </div>
    
    <div v-else>
      <!-- Chart Header -->
      <div class="chart-header mb-3">
        <div class="d-flex align-center justify-space-between">
          <div>
            <div class="text-subtitle-1 font-weight-medium">
              {{ chartConfig.yTitle }} vs {{ chartConfig.xTitle }}
            </div>
            <div class="text-caption text-medium-emphasis">
              {{ chartConfig.data.length }} data points
              <span v-if="chartConfig.colorTitle"> • Colored by {{ chartConfig.colorTitle }}</span>
            </div>
          </div>
          <v-btn-group variant="outlined" density="compact">
            <v-btn @click="resetZoom" size="small" title="Reset Zoom">
              <v-icon size="small">mdi-magnify-scan</v-icon>
            </v-btn>
            <v-btn @click="downloadChart" size="small" title="Download Chart">
              <v-icon size="small">mdi-download</v-icon>
            </v-btn>
          </v-btn-group>
        </div>
      </div>

      <!-- ECharts Container -->
      <div 
        ref="chartContainer" 
        :style="{ width: '100%', height: chartHeight + 'px' }"
        class="echarts-container"
      />
      
      <!-- Legend for Color Grouping -->
      <div v-if="chartConfig.colorTitle && colorCategories.length > 1" class="legend-container mt-3">
        <div class="text-caption text-medium-emphasis mb-2">{{ chartConfig.colorTitle }}:</div>
        <div class="d-flex flex-wrap ga-2">
          <v-chip
            v-for="(category, index) in colorCategories"
            :key="category"
            :color="getColorByIndex(index)"
            size="small"
            variant="tonal"
          >
            {{ category }} ({{ getCategoryCount(category) }})
          </v-chip>
        </div>
      </div>
      
      <!-- Chart Statistics -->
      <div class="chart-stats mt-3">
        <v-row dense>
          <v-col cols="6" md="3">
            <v-card variant="outlined" class="pa-2">
              <div class="text-caption text-medium-emphasis">X Range</div>
              <div class="text-body-2 font-weight-medium">{{ xRange }}</div>
            </v-card>
          </v-col>
          <v-col cols="6" md="3">
            <v-card variant="outlined" class="pa-2">
              <div class="text-caption text-medium-emphasis">Y Range</div>
              <div class="text-body-2 font-weight-medium">{{ yRange }}</div>
            </v-card>
          </v-col>
          <v-col cols="6" md="3">
            <v-card variant="outlined" class="pa-2">
              <div class="text-caption text-medium-emphasis">Correlation</div>
              <div class="text-body-2 font-weight-medium">{{ correlation }}</div>
            </v-card>
          </v-col>
          <v-col cols="6" md="3">
            <v-card variant="outlined" class="pa-2">
              <div class="text-caption text-medium-emphasis">Data Points</div>
              <div class="text-body-2 font-weight-medium">{{ chartConfig.data.length }}</div>
            </v-card>
          </v-col>
        </v-row>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'

const props = defineProps({
  chartConfig: {
    type: Object,
    default: null
  },
  chartHeight: {
    type: Number,
    default: 400
  }
})

const chartContainer = ref(null)
const chartInstance = ref(null)

// Computed properties
const colorCategories = computed(() => {
  if (!props.chartConfig || !props.chartConfig.colorTitle) return []
  
  const categories = new Set()
  props.chartConfig.data.forEach(item => {
    categories.add(item.color)
  })
  
  return Array.from(categories).sort()
})

const xRange = computed(() => {
  if (!props.chartConfig || !props.chartConfig.data.length) return 'N/A'
  
  const xValues = props.chartConfig.data.map(item => item.x).filter(v => typeof v === 'number')
  if (xValues.length === 0) return 'N/A'
  
  const min = Math.min(...xValues)
  const max = Math.max(...xValues)
  return `${min.toFixed(2)} - ${max.toFixed(2)}`
})

const yRange = computed(() => {
  if (!props.chartConfig || !props.chartConfig.data.length) return 'N/A'
  
  const yValues = props.chartConfig.data.map(item => item.y).filter(v => typeof v === 'number')
  if (yValues.length === 0) return 'N/A'
  
  const min = Math.min(...yValues)
  const max = Math.max(...yValues)
  return `${min.toFixed(2)} - ${max.toFixed(2)}`
})

const correlation = computed(() => {
  if (!props.chartConfig || !props.chartConfig.data.length) return 'N/A'
  
  const xValues = props.chartConfig.data.map(item => item.x).filter(v => typeof v === 'number')
  const yValues = props.chartConfig.data.map(item => item.y).filter(v => typeof v === 'number')
  
  if (xValues.length !== yValues.length || xValues.length < 2) return 'N/A'
  
  const xMean = xValues.reduce((a, b) => a + b, 0) / xValues.length
  const yMean = yValues.reduce((a, b) => a + b, 0) / yValues.length
  
  let numerator = 0
  let xSumSquares = 0
  let ySumSquares = 0
  
  for (let i = 0; i < xValues.length; i++) {
    const xDiff = xValues[i] - xMean
    const yDiff = yValues[i] - yMean
    numerator += xDiff * yDiff
    xSumSquares += xDiff * xDiff
    ySumSquares += yDiff * yDiff
  }
  
  const denominator = Math.sqrt(xSumSquares * ySumSquares)
  if (denominator === 0) return 'N/A'
  
  const corr = numerator / denominator
  return corr.toFixed(3)
})

// Methods
function getColorByIndex(index) {
  const colors = [
    '#1976d2', '#388e3c', '#f57c00', '#d32f2f', '#7b1fa2',
    '#0288d1', '#1976d2', '#7cb342', '#ffa000', '#e53935'
  ]
  return colors[index % colors.length]
}

function getCategoryCount(category) {
  if (!props.chartConfig) return 0
  return props.chartConfig.data.filter(item => item.color === category).length
}

function initChart() {
  if (!chartContainer.value || !props.chartConfig || !props.chartConfig.data.length) return
  
  if (chartInstance.value) {
    chartInstance.value.dispose()
  }
  
  chartInstance.value = echarts.init(chartContainer.value)
  updateChart()
}

function updateChart() {
  if (!chartInstance.value || !props.chartConfig) return
  
  const seriesData = {}
  
  // Group data by color category
  props.chartConfig.data.forEach((item, index) => {
    const category = item.color
    if (!seriesData[category]) {
      seriesData[category] = []
    }
    seriesData[category].push([item.x, item.y, item.raw])
  })
  
  // Create series for each category
  const series = Object.keys(seriesData).map((category, index) => ({
    name: category,
    type: 'scatter',
    data: seriesData[category],
    itemStyle: {
      color: getColorByIndex(index),
      opacity: 0.7
    },
    emphasis: {
      itemStyle: {
        opacity: 1,
        borderColor: '#333',
        borderWidth: 2
      }
    },
    symbolSize: 8,
    animationDuration: 800,
    animationEasing: 'cubicOut'
  }))
  
  const option = {
    animation: true,
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      borderColor: '#777',
      borderWidth: 1,
      textStyle: {
        color: '#fff',
        fontSize: 12
      },
      formatter: (params) => {
        const [x, y, rawData] = params.data
        const colorBy = props.chartConfig.colorTitle
        
        let tooltip = `
          <div style="font-weight: bold; margin-bottom: 4px;">${params.seriesName}</div>
          <div><strong>${props.chartConfig.xTitle}:</strong> ${formatValue(x)}</div>
          <div><strong>${props.chartConfig.yTitle}:</strong> ${formatValue(y)}</div>
        `
        
        if (colorBy && rawData[props.chartConfig.colorColumn]) {
          tooltip += `<div><strong>${colorBy}:</strong> ${rawData[props.chartConfig.colorColumn]}</div>`
        }
        
        // Add additional info
        if (rawData['Site ID'] || rawData.Site_ID) {
          tooltip += `<div><strong>Site ID:</strong> ${rawData['Site ID'] || rawData.Site_ID}</div>`
        }
        if (rawData['Point No'] || rawData.Point_No) {
          tooltip += `<div><strong>Point:</strong> ${rawData['Point No'] || rawData.Point_No}</div>`
        }
        
        return tooltip
      }
    },
    legend: {
      show: colorCategories.value.length > 1 && colorCategories.value.length <= 10,
      top: 10,
      right: 10,
      orient: 'vertical',
      textStyle: {
        fontSize: 11
      }
    },
    grid: {
      left: '12%',
      right: colorCategories.value.length > 1 && colorCategories.value.length <= 10 ? '20%' : '8%',
      top: colorCategories.value.length > 1 && colorCategories.value.length <= 10 ? '15%' : '8%',
      bottom: '15%',
      containLabel: false
    },
    xAxis: {
      type: 'value',
      name: props.chartConfig.xTitle,
      nameLocation: 'middle',
      nameGap: 30,
      nameTextStyle: {
        fontSize: 12,
        fontWeight: 'bold'
      },
      axisLabel: {
        fontSize: 11,
        formatter: (value) => formatAxisValue(value)
      },
      splitLine: {
        show: true,
        lineStyle: {
          type: 'dashed',
          opacity: 0.3
        }
      }
    },
    yAxis: {
      type: 'value',
      name: props.chartConfig.yTitle,
      nameLocation: 'middle',
      nameGap: 50,
      nameTextStyle: {
        fontSize: 12,
        fontWeight: 'bold'
      },
      axisLabel: {
        fontSize: 11,
        formatter: (value) => formatAxisValue(value)
      },
      splitLine: {
        show: true,
        lineStyle: {
          type: 'dashed',
          opacity: 0.3
        }
      }
    },
    series: series,
    dataZoom: [
      {
        type: 'inside',
        xAxisIndex: 0,
        yAxisIndex: 0,
        zoomLock: false
      },
      {
        type: 'slider',
        xAxisIndex: 0,
        height: 20,
        bottom: 5,
        handleSize: 15
      }
    ],
    toolbox: {
      show: false
    }
  }
  
  chartInstance.value.setOption(option, true)
}

function formatValue(value) {
  if (typeof value === 'number') {
    if (Math.abs(value) >= 1000) {
      return value.toFixed(1)
    } else if (Math.abs(value) >= 1) {
      return value.toFixed(2)
    } else {
      return value.toFixed(4)
    }
  }
  return value.toString()
}

function formatAxisValue(value) {
  if (Math.abs(value) >= 1000000) {
    return (value / 1000000).toFixed(1) + 'M'
  } else if (Math.abs(value) >= 1000) {
    return (value / 1000).toFixed(1) + 'K'
  } else if (Math.abs(value) >= 1) {
    return value.toFixed(1)
  } else {
    return value.toFixed(2)
  }
}

function resetZoom() {
  if (chartInstance.value) {
    chartInstance.value.dispatchAction({
      type: 'dataZoom',
      start: 0,
      end: 100
    })
  }
}

function downloadChart() {
  if (!chartInstance.value) return
  
  const url = chartInstance.value.getDataURL({
    type: 'png',
    pixelRatio: 2,
    backgroundColor: '#fff'
  })
  
  const link = document.createElement('a')
  link.href = url
  link.download = `scatter_chart_${props.chartConfig.xTitle}_vs_${props.chartConfig.yTitle}_${new Date().toISOString().split('T')[0]}.png`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

function handleResize() {
  if (chartInstance.value) {
    chartInstance.value.resize()
  }
}

// Watchers
watch(() => props.chartConfig, (newConfig) => {
  if (newConfig && newConfig.data && newConfig.data.length > 0) {
    nextTick(() => {
      initChart()
    })
  }
}, { deep: true })

// Lifecycle
onMounted(() => {
  window.addEventListener('resize', handleResize)
  if (props.chartConfig && props.chartConfig.data && props.chartConfig.data.length > 0) {
    nextTick(() => {
      initChart()
    })
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance.value) {
    chartInstance.value.dispose()
  }
})
</script>

<style scoped>
.scatter-chart-container {
  width: 100%;
  height: 100%;
}

.no-data-container {
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.chart-header {
  padding: 8px 0;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.12);
}

.echarts-container {
  border-radius: 4px;
  background: #fafafa;
  border: 1px solid rgba(var(--v-theme-outline), 0.12);
}

.legend-container {
  padding: 12px;
  background-color: rgba(var(--v-theme-surface), 0.5);
  border-radius: 6px;
  border: 1px solid rgba(var(--v-theme-outline), 0.12);
}

.chart-stats .v-card {
  text-align: center;
  min-height: 60px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.v-chip {
  margin: 2px;
}

@media (max-width: 960px) {
  .chart-header {
    flex-direction: column;
    align-items: flex-start !important;
  }
  
  .chart-header .v-btn-group {
    margin-top: 8px;
  }
  
  .legend-container .d-flex {
    justify-content: center;
  }
}
</style>