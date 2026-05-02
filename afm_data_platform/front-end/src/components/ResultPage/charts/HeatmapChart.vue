<template>
  <div class="heatmap-chart-container">
    <!-- Controls Section -->
    <v-card elevation="0" class="mb-3">
      <v-card-text class="pa-2">
        <v-row dense align="center">
          <!-- Outlier Removal -->
          <v-col cols="12" md="3">
            <v-select
              v-model="outlierMethod"
              :items="outlierMethods"
              label="Outlier Removal"
              density="compact"
              variant="outlined"
              hide-details
            ></v-select>
          </v-col>
          
          <!-- Outlier Threshold -->
          <v-col cols="12" md="2" v-if="outlierMethod !== 'none' && outlierMethod !== 'auto'">
            <v-text-field
              v-model.number="outlierThreshold"
              :label="getThresholdLabel()"
              type="number"
              :step="getThresholdStep()"
              :min="getThresholdMin()"
              :max="getThresholdMax()"
              density="compact"
              variant="outlined"
              hide-details
              :hint="getThresholdHint()"
            ></v-text-field>
          </v-col>
          
          <!-- Color Scheme -->
          <v-col cols="12" md="3">
            <v-select
              v-model="colorScheme"
              :items="colorSchemes"
              label="Color Scheme"
              density="compact"
              variant="outlined"
              hide-details
            ></v-select>
          </v-col>
          
          <!-- Sampling Rate for Large Data -->
          <v-col cols="12" md="2" v-if="dataPointCount > 50000">
            <v-select
              v-model="samplingRate"
              :items="samplingRates"
              label="Sampling"
              density="compact"
              variant="outlined"
              hide-details
            ></v-select>
          </v-col>
          
          <!-- Download Button -->
          <v-col cols="12" md="2" class="text-right">
            <v-btn
              color="primary"
              variant="outlined"
              density="compact"
              @click="downloadRawData"
              :loading="downloading"
            >
              <v-icon left>mdi-download</v-icon>
              Download Data
            </v-btn>
          </v-col>
        </v-row>
        
        <!-- Data Info -->
        <v-row dense class="mt-2" v-if="dataStats">
          <v-col cols="12">
            <v-chip size="small" class="mr-2" variant="outlined">
              Points: {{ dataStats.totalPoints.toLocaleString() }}
            </v-chip>
            <v-chip size="small" class="mr-2" variant="outlined" v-if="dataStats.filtered">
              Filtered: {{ dataStats.filteredPoints.toLocaleString() }}
            </v-chip>
            <v-chip size="small" class="mr-2" variant="outlined">
              Min Z: {{ dataStats.minZ.toFixed(3) }} {{ units.Z }}
            </v-chip>
            <v-chip size="small" class="mr-2" variant="outlined">
              Max Z: {{ dataStats.maxZ.toFixed(3) }} {{ units.Z }}
            </v-chip>
            <v-chip size="small" class="mr-2" variant="outlined">
              Mean Z: {{ dataStats.meanZ.toFixed(3) }} {{ units.Z }}
            </v-chip>
            <v-chip size="small" variant="outlined" v-if="dataStats.outliers">
              Outliers: {{ dataStats.outliers }}
            </v-chip>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>
    
    <!-- Chart Container -->
    <div ref="chartContainer" :style="{ width: '100%', height: `${chartHeight}px` }"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import * as echarts from 'echarts'
import shineThemeData from '@/plugins/shine.json'
import api from '@/services/api'

const props = defineProps({
  waferData: {
    type: Object,
    default: () => ({ data: [], available_points: 0 })
  },
  chartHeight: {
    type: Number,
    default: 700
  },
  filename: {
    type: String,
    default: ''
  },
  tool: {
    type: String,
    default: 'MAP608'
  }
})

const emit = defineEmits(['point-selected'])

// Chart refs
const chartContainer = ref(null)
let chartInstance = null

// Controls
const outlierMethod = ref('auto')
const outlierThreshold = ref(1.5)
const colorScheme = ref('spectral')
const samplingRate = ref(1)
const downloading = ref(false)

// Options
const outlierMethods = [
  { title: 'None', value: 'none' },
  { title: 'Auto (Smart)', value: 'auto' },
  { title: 'IQR Method', value: 'iqr' },
  { title: 'Percentile Trim', value: 'percentile' },
  { title: 'Z-Score', value: 'zscore' }
]

const colorSchemes = [
  { title: 'Spectral', value: 'spectral' },
  { title: 'Viridis', value: 'viridis' },
  { title: 'Plasma', value: 'plasma' },
  { title: 'Cool Warm', value: 'coolwarm' },
  { title: 'Rainbow', value: 'rainbow' },
  { title: 'Jet', value: 'jet' },
  { title: 'Thermal', value: 'thermal' },
  { title: 'Grayscale', value: 'grayscale' }
]

const samplingRates = [
  { title: '100%', value: 1 },
  { title: '50%', value: 2 },
  { title: '25%', value: 4 },
  { title: '10%', value: 10 },
  { title: '5%', value: 20 }
]

// Color maps
const colorMaps = {
  spectral: ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8', '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027', '#a50026'],
  viridis: ['#440154', '#482777', '#3f4a8a', '#31678e', '#26838f', '#1f9d8a', '#6cce5a', '#b6de2b', '#fee825'],
  plasma: ['#0d0887', '#46039f', '#7201a8', '#9c179e', '#bd3786', '#d8576b', '#ed7953', '#fb9f3a', '#fdca26', '#f0f921'],
  coolwarm: ['#3b4cc0', '#6788ee', '#9abbff', '#c9ddff', '#f7f7f7', '#ffddaa', '#ffaa77', '#ee6644', '#b40426'],
  rainbow: ['#ff0000', '#ff7f00', '#ffff00', '#00ff00', '#0000ff', '#4b0082', '#9400d3'],
  jet: ['#000083', '#003caa', '#0055d4', '#0071ff', '#008cff', '#00a6ff', '#00c1ff', '#00dbff', '#00f6ff', '#1fffea', '#42ffca', '#65ffa9', '#88ff88', '#abff66', '#ceff44', '#f1ff22', '#ffee00', '#ffcc00', '#ffaa00', '#ff8800', '#ff6600', '#ff4400', '#ff2200', '#ff0000', '#dd0000', '#bb0000', '#990000', '#770000'],
  thermal: ['#000000', '#200080', '#4000c0', '#6000ff', '#8040ff', '#a080ff', '#c0c0ff', '#ffffff', '#ffc0c0', '#ff8080', '#ff4040', '#ff0000', '#c00000', '#800000', '#400000'],
  grayscale: ['#000000', '#1a1a1a', '#333333', '#4d4d4d', '#666666', '#808080', '#999999', '#b3b3b3', '#cccccc', '#e6e6e6', '#ffffff']
}

// Computed
const units = computed(() => {
  return {
    X: props.waferData?.info?.X || 'µm',
    Y: props.waferData?.info?.Y || 'µm',
    Z: props.waferData?.info?.Z || 'nm'
  }
})

const dataPointCount = computed(() => {
  return props.waferData?.available_points || 0
})

const dataStats = computed(() => {
  const data = processedData.value.originalData
  if (!data || data.length === 0) return null
  
  const zValues = data.map(d => d.z).filter(z => !isNaN(z))
  const stats = {
    totalPoints: props.waferData?.available_points || 0,
    filteredPoints: processedData.value.data.length,
    filtered: processedData.value.data.length < data.length,
    minZ: Math.min(...zValues),
    maxZ: Math.max(...zValues),
    meanZ: zValues.reduce((a, b) => a + b, 0) / zValues.length,
    outliers: data.length - processedData.value.data.length
  }
  
  return stats
})

const processedData = computed(() => {
  if (!props.waferData?.data || props.waferData?.available_points === 0) {
    return { data: [], xAxis: [], yAxis: [], originalData: [] }
  }

  // Normalize data format
  let normalizedData = props.waferData.data.map(point => ({
    x: point.X || point.x || 0,
    y: point.Y || point.y || 0,
    z: point.Z || point.z || 0
  }))

  // Apply sampling for large datasets (use available_points for checking)
  if (samplingRate.value > 1 && props.waferData.available_points > 50000) {
    normalizedData = normalizedData.filter((_, index) => index % samplingRate.value === 0)
  }

  // Remove outliers
  const filteredData = removeOutliers(normalizedData)

  // Create grid data for heatmap
  return createHeatmapGrid(filteredData, normalizedData)
})

function removeOutliers(data) {
  if (outlierMethod.value === 'none') return data
  
  const zValues = data.map(d => d.z).filter(z => !isNaN(z) && isFinite(z))
  if (zValues.length === 0) return data
  
  let lowerBound = -Infinity
  let upperBound = Infinity
  
  switch (outlierMethod.value) {
    case 'auto': {
      // Smart auto-detection: Use IQR for AFM data (robust to measurement errors)
      const sorted = [...zValues].sort((a, b) => a - b)
      const q1 = sorted[Math.floor(sorted.length * 0.25)]
      const q3 = sorted[Math.floor(sorted.length * 0.75)]
      const iqr = q3 - q1
      const median = sorted[Math.floor(sorted.length * 0.5)]
      
      // Adaptive threshold based on data characteristics
      const range = Math.max(...zValues) - Math.min(...zValues)
      const isHighVariability = iqr / range > 0.3
      const adaptiveMultiplier = isHighVariability ? 1.5 : 2.0 // More aggressive for high variability
      
      lowerBound = q1 - adaptiveMultiplier * iqr
      upperBound = q3 + adaptiveMultiplier * iqr
      
      // Safety bounds - never remove more than 20% of data
      const maxRemoval = Math.floor(zValues.length * 0.2)
      const wouldRemove = zValues.filter(z => z < lowerBound || z > upperBound).length
      if (wouldRemove > maxRemoval) {
        // Fall back to percentile method
        lowerBound = sorted[Math.floor(sorted.length * 0.05)]
        upperBound = sorted[Math.floor(sorted.length * 0.95)]
      }
      break
    }
    case 'zscore': {
      const mean = zValues.reduce((a, b) => a + b, 0) / zValues.length
      const stdDev = Math.sqrt(zValues.reduce((sq, n) => sq + Math.pow(n - mean, 2), 0) / zValues.length)
      if (stdDev > 0) {
        lowerBound = mean - outlierThreshold.value * stdDev
        upperBound = mean + outlierThreshold.value * stdDev
      }
      break
    }
    case 'iqr': {
      const sorted = [...zValues].sort((a, b) => a - b)
      const q1 = sorted[Math.floor(sorted.length * 0.25)]
      const q3 = sorted[Math.floor(sorted.length * 0.75)]
      const iqr = q3 - q1
      if (iqr > 0) {
        lowerBound = q1 - outlierThreshold.value * iqr
        upperBound = q3 + outlierThreshold.value * iqr
      }
      break
    }
    case 'percentile': {
      const sorted = [...zValues].sort((a, b) => a - b)
      const lowerPercentile = outlierThreshold.value
      const upperPercentile = 100 - outlierThreshold.value
      lowerBound = sorted[Math.floor(sorted.length * lowerPercentile / 100)] || sorted[0]
      upperBound = sorted[Math.floor(sorted.length * upperPercentile / 100)] || sorted[sorted.length - 1]
      break
    }
  }
  
  return data.filter(d => d.z >= lowerBound && d.z <= upperBound)
}

function createHeatmapGrid(data, originalData) {
  if (data.length === 0) return { data: [], xAxis: [], yAxis: [], originalData }
  
  // For large datasets, use binning to create a manageable grid
  const maxGridSize = 200
  
  // Get data ranges
  const xValues = data.map(p => p.x)
  const yValues = data.map(p => p.y)
  const xMin = Math.min(...xValues)
  const xMax = Math.max(...xValues)
  const yMin = Math.min(...yValues)
  const yMax = Math.max(...yValues)
  
  // Calculate grid resolution based on data size
  const dataPoints = data.length
  let gridSizeX = Math.min(maxGridSize, Math.ceil(Math.sqrt(dataPoints)))
  let gridSizeY = Math.min(maxGridSize, Math.ceil(Math.sqrt(dataPoints)))
  
  // Create bins
  const xBinSize = (xMax - xMin) / gridSizeX
  const yBinSize = (yMax - yMin) / gridSizeY
  
  // Create grid labels
  const xAxis = Array.from({ length: gridSizeX }, (_, i) => 
    (xMin + (i + 0.5) * xBinSize).toFixed(2)
  )
  const yAxis = Array.from({ length: gridSizeY }, (_, i) => 
    (yMin + (i + 0.5) * yBinSize).toFixed(2)
  )
  
  // Bin the data
  const bins = new Map()
  
  data.forEach(point => {
    const xBin = Math.min(Math.floor((point.x - xMin) / xBinSize), gridSizeX - 1)
    const yBin = Math.min(Math.floor((point.y - yMin) / yBinSize), gridSizeY - 1)
    const key = `${xBin},${yBin}`
    
    if (!bins.has(key)) {
      bins.set(key, [])
    }
    bins.get(key).push(point.z)
  })
  
  // Create heatmap data with averaged values
  const heatmapData = []
  bins.forEach((zValues, key) => {
    const [xBin, yBin] = key.split(',').map(Number)
    const avgZ = zValues.reduce((a, b) => a + b, 0) / zValues.length
    heatmapData.push([xBin, yBin, avgZ])
  })
  
  return {
    data: heatmapData,
    xAxis,
    yAxis,
    originalData
  }
}

function initChart() {
  if (!chartContainer.value || !props.waferData?.data || props.waferData?.available_points === 0) return

  if (chartInstance) {
    chartInstance.dispose()
  }

  // Register the shine theme
  echarts.registerTheme('shine', shineThemeData)

  // Initialize chart with shine theme
  chartInstance = echarts.init(chartContainer.value, 'shine')

  const { data, xAxis, yAxis } = processedData.value

  if (data.length === 0) {
    console.warn('HeatmapChart: No data to display after processing')
    return
  }

  // Calculate min/max for color scale
  const zValues = data.map(d => d[2])
  const minZ = Math.min(...zValues)
  const maxZ = Math.max(...zValues)

  const option = {
    tooltip: {
      position: 'top',
      formatter: function (params) {
        const [xIndex, yIndex, value] = params.data
        return `X: ${xAxis[xIndex]} ${units.value.X}<br/>Y: ${yAxis[yIndex]} ${units.value.Y}<br/>Z: ${value.toFixed(3)} ${units.value.Z}`
      }
    },
    grid: {
      left: '10%',
      right: '15%',
      top: '10%',
      bottom: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: xAxis,
      name: `X (${units.value.X})`,
      nameLocation: 'middle',
      nameGap: 25,
      splitArea: {
        show: true
      },
      axisLabel: {
        rotate: 45,
        interval: Math.max(0, Math.floor(xAxis.length / 20))
      }
    },
    yAxis: {
      type: 'category',
      data: yAxis,
      name: `Y (${units.value.Y})`,
      nameLocation: 'middle',
      nameGap: 45,
      splitArea: {
        show: true
      },
      axisLabel: {
        interval: Math.max(0, Math.floor(yAxis.length / 20))
      }
    },
    visualMap: {
      min: minZ,
      max: maxZ,
      calculable: true,
      orient: 'vertical',
      right: '5%',
      top: 'center',
      text: [`High (${units.value.Z})`, `Low (${units.value.Z})`],
      inRange: {
        color: colorMaps[colorScheme.value] || colorMaps.spectral
      },
      textStyle: {
        fontSize: 12
      },
      precision: 3
    },
    series: [{
      type: 'heatmap',
      data: data,
      label: {
        show: false
      },
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      },
      progressive: 1000,
      progressiveThreshold: 10000,
      animation: false // Disable animation for better performance with large data
    }]
  }

  chartInstance.setOption(option)

  // Add click event listener
  chartInstance.on('click', function (params) {
    if (params.componentType === 'series') {
      const [xIndex, yIndex, value] = params.data
      emit('point-selected', {
        x: parseFloat(xAxis[xIndex]),
        y: parseFloat(yAxis[yIndex]),
        z: value,
        point: xIndex * yAxis.length + yIndex + 1
      })
    }
  })
}

async function downloadRawData() {
  if (!props.filename) {
    console.error('Filename is required for download')
    return
  }
  
  downloading.value = true
  
  try {
    // Extract point ID from filename if it contains it
    // Filename format: #date#recipe#lot#slot_pointid#
    const filenameMatch = props.filename.match(/#[^#]+#[^#]+#[^#]+#(\d+)_(\d+)#/)
    const pointId = filenameMatch ? filenameMatch[2] : '1'
    
    // Get profile data from Flask API
    const response = await api.getProfileData(props.filename, pointId, props.tool)
    
    if (response && response.data) {
      // Convert data to CSV format
      const csvContent = convertToCSV(response.data)
      
      // Create blob and download
      const blob = new Blob([csvContent], { type: 'text/csv' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${props.filename}_point${pointId}_profile.csv`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      window.URL.revokeObjectURL(url)
    }
  } catch (error) {
    console.error('Error downloading data:', error)
  } finally {
    downloading.value = false
  }
}

function convertToCSV(data) {
  if (!data || data.length === 0) return ''
  
  // Headers
  const headers = [`X (${units.value.X})`, `Y (${units.value.Y})`, `Z (${units.value.Z})`]
  
  // Rows
  const rows = data.map(point => [
    point.X || point.x || 0,
    point.Y || point.y || 0,
    point.Z || point.z || 0
  ])
  
  // Combine headers and rows
  const csvContent = [
    headers.join(','),
    ...rows.map(row => row.join(','))
  ].join('\n')
  
  return csvContent
}

function getThresholdLabel() {
  switch (outlierMethod.value) {
    case 'iqr': return 'IQR Multiplier'
    case 'zscore': return 'Sigma Level'
    case 'percentile': return 'Percentile %'
    default: return 'Threshold'
  }
}

function getThresholdStep() {
  switch (outlierMethod.value) {
    case 'iqr': return 0.1
    case 'zscore': return 0.1
    case 'percentile': return 0.5
    default: return 0.1
  }
}

function getThresholdMin() {
  switch (outlierMethod.value) {
    case 'iqr': return 0.1
    case 'zscore': return 0.5
    case 'percentile': return 0.1
    default: return 0.1
  }
}

function getThresholdMax() {
  switch (outlierMethod.value) {
    case 'iqr': return 3.0
    case 'zscore': return 5.0
    case 'percentile': return 25.0
    default: return 10.0
  }
}

function getThresholdHint() {
  switch (outlierMethod.value) {
    case 'iqr': return '1.5 = standard, 2.0 = moderate, 3.0 = conservative'
    case 'zscore': return '2.0 = 95%, 2.5 = 99%, 3.0 = 99.7%'
    case 'percentile': return '1% = aggressive, 5% = moderate, 10% = conservative'
    default: return ''
  }
}

function handleResize() {
  if (chartInstance) {
    chartInstance.resize()
  }
}

// Watchers
watch([outlierMethod, outlierThreshold, colorScheme, samplingRate], () => {
  initChart()
})

watch(() => props.waferData, () => {
  initChart()
})

watch(() => props.chartHeight, () => {
  if (chartInstance) {
    chartInstance.resize()
  }
})

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
.heatmap-chart-container {
  width: 100%;
}
</style>