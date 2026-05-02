<template>
  <div class="histogram-chart-wrapper">
    <!-- Controls Section -->
    <v-card elevation="0" class="mb-3">
      <v-card-text class="pa-2">
        <v-row dense align="center">
          <!-- Bin Count -->
          <v-col cols="12" md="3">
            <v-select
              v-model="binSelection"
              :items="binOptions"
              item-title="title"
              item-value="value"
              label="Bin Count Method"
              density="compact"
              variant="outlined"
              hide-details
            >
              <template v-slot:selection="{ item }">
                {{ item.title }} ({{ item.value === 'custom' ? customBinCount : item.bins }})
              </template>
              <template v-slot:item="{ props, item }">
                <v-list-item v-bind="props" :title="item.raw.title" :subtitle="item.raw.description">
                  <template v-slot:append>
                    <v-chip size="small">{{ item.raw.value === 'custom' ? customBinCount : item.raw.bins }}</v-chip>
                  </template>
                </v-list-item>
              </template>
            </v-select>
          </v-col>

          <!-- Custom Bin Count (when custom is selected) -->
          <v-col cols="12" md="2" v-if="binSelection === 'custom'">
            <v-text-field
              v-model.number="customBinCount"
              label="Custom Bins"
              type="number"
              min="5"
              max="200"
              :rules="[v => v >= 5 && v <= 200 || 'Must be between 5 and 200']"
              density="compact"
              variant="outlined"
              hide-details="auto"
            ></v-text-field>
          </v-col>

          <!-- Display Mode -->
          <v-col cols="12" md="3">
            <v-select
              v-model="displayMode"
              :items="displayModes"
              label="Display"
              density="compact"
              variant="outlined"
              hide-details
            ></v-select>
          </v-col>

          <!-- Show Normal Curve -->
          <v-col cols="12" md="3">
            <v-checkbox
              v-model="showNormalCurve"
              label="Normal Distribution Curve"
              density="compact"
              hide-details
            ></v-checkbox>
          </v-col>

          <!-- Show Percentiles -->
          <v-col cols="12" md="2">
            <v-checkbox
              v-model="showPercentiles"
              label="Percentiles"
              density="compact"
              hide-details
            ></v-checkbox>
          </v-col>

          <!-- Log Scale Y -->
          <v-col cols="12" md="2">
            <v-checkbox
              v-model="logScale"
              label="Log Scale Y"
              density="compact"
              hide-details
            ></v-checkbox>
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Enhanced Statistics Box -->
    <div v-if="statistics" class="statistics-box mb-3">
      <v-card variant="outlined" class="pa-4">
        <v-row dense>
          <!-- Basic Stats -->
          <v-col cols="12" md="8">
            <div class="d-flex align-center justify-space-around">
              <div class="text-center px-2">
                <div class="text-caption text-medium-emphasis mb-1">Count</div>
                <div class="text-subtitle-1 font-weight-medium">{{ statistics.count.toLocaleString() }}</div>
              </div>
              <v-divider vertical class="mx-2" />
              <div class="text-center px-2">
                <div class="text-caption text-medium-emphasis mb-1">Mean</div>
                <div class="text-subtitle-1 font-weight-medium" :title="`Exact: ${statistics.mean}`">{{ statistics.mean }} {{ units.Z }}</div>
              </div>
              <v-divider vertical class="mx-2" />
              <div class="text-center px-2">
                <div class="text-caption text-medium-emphasis mb-1">Std Dev</div>
                <div class="text-subtitle-1 font-weight-medium" :title="`Exact: ${statistics.std}`">{{ statistics.std }} {{ units.Z }}</div>
              </div>
              <v-divider vertical class="mx-2" />
              <div class="text-center px-2">
                <div class="text-caption text-medium-emphasis mb-1">Range</div>
                <div class="text-subtitle-1 font-weight-medium" :title="`Exact: ${statistics.range}`">{{ statistics.range }} {{ units.Z }}</div>
              </div>
            </div>
          </v-col>

          <!-- Percentiles -->
          <v-col cols="12" md="4" v-if="showPercentiles">
            <div class="d-flex align-center justify-space-around">
              <div class="text-center px-2">
                <div class="text-caption text-medium-emphasis mb-1">Q1 (25%)</div>
                <div class="text-subtitle-2">{{ statistics.q1 }} {{ units.Z }}</div>
              </div>
              <v-divider vertical class="mx-1" />
              <div class="text-center px-2">
                <div class="text-caption text-medium-emphasis mb-1">Q2 (50%)</div>
                <div class="text-subtitle-2">{{ statistics.median }} {{ units.Z }}</div>
              </div>
              <v-divider vertical class="mx-1" />
              <div class="text-center px-2">
                <div class="text-caption text-medium-emphasis mb-1">Q3 (75%)</div>
                <div class="text-subtitle-2">{{ statistics.q3 }} {{ units.Z }}</div>
              </div>
            </div>
          </v-col>
        </v-row>

        <!-- Additional Stats Row -->
        <v-row dense class="mt-2">
          <v-col cols="12" md="8">
            <div class="d-flex align-center justify-space-around">
              <v-chip
                size="small"
                class="mr-2"
                variant="outlined"
                :color="Math.abs(parseFloat(statistics.skewness)) > 1 ? 'warning' : 'default'"
                :title="'Skewness interpretation: ' + getSkewnessInterpretation(statistics.skewness)"
              >
                Skewness: {{ statistics.skewness }}
              </v-chip>
              <v-chip
                size="small"
                class="mr-2"
                variant="outlined"
                :color="Math.abs(parseFloat(statistics.kurtosis)) > 1 ? 'warning' : 'default'"
                :title="'Kurtosis interpretation: ' + getKurtosisInterpretation(statistics.kurtosis)"
              >
                Kurtosis: {{ statistics.kurtosis }}
              </v-chip>
              <v-chip size="small" class="mr-2" variant="outlined" :title="'Coefficient of Variation: ' + statistics.cv + '%'">
                CV: {{ statistics.cv }}%
              </v-chip>
              <v-chip
                size="small"
                variant="outlined"
                v-if="statistics.outliers > 0"
                color="error"
                :title="'Points beyond 3 standard deviations from mean'"
              >
                Outliers (3σ): {{ statistics.outliers }}
              </v-chip>
            </div>
          </v-col>
          <v-col cols="12" md="4" v-if="binSelection === 'custom'">
            <div class="text-caption text-medium-emphasis">
              <strong>Bin Count:</strong> {{ binCount }} bins
            </div>
          </v-col>
          <v-col cols="12" md="4" v-else>
            <div class="text-caption text-medium-emphasis">
              <strong>{{ getCurrentMethodName() }}:</strong> {{ getCurrentMethodDescription() }} ({{ binCount }} bins)
            </div>
          </v-col>
        </v-row>
      </v-card>
    </div>

    <!-- Chart Container -->
    <div ref="chartContainer" :style="{ width: '100%', height: `${adjustedChartHeight}px` }"></div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from 'vue'
import * as echarts from 'echarts'
import shineThemeData from '@/plugins/shine.json'

const props = defineProps({
  waferData: {
    type: Object,
    default: () => ({ data: [], available_points: 0 })
  },
  chartHeight: {
    type: Number,
    default: 500
  }
})

const chartContainer = ref(null)
let chartInstance = null

// Controls
const binSelection = ref('auto')
const customBinCount = ref(30)
const displayMode = ref('frequency')
const showNormalCurve = ref(true)
const showPercentiles = ref(true)
const logScale = ref(false)

// Options
const displayModes = [
  { title: 'Frequency', value: 'frequency' },
  { title: 'Density', value: 'density' },
  { title: 'Cumulative', value: 'cumulative' }
]

// Computed
const units = computed(() => {
  return {
    X: props.waferData?.info?.X || 'µm',
    Y: props.waferData?.info?.Y || 'µm',
    Z: props.waferData?.info?.Z || 'nm'
  }
})

// Optimized data statistics (computed once)
const dataStatistics = computed(() => {
  const data = zValues.value
  const n = data.length

  if (n === 0) return null

  // Single pass for min, max, mean, variance
  let min = Infinity
  let max = -Infinity
  let sum = 0
  let sumSq = 0

  for (const val of data) {
    if (val < min) min = val
    if (val > max) max = val
    sum += val
    sumSq += val * val
  }

  const mean = sum / n
  const variance = Math.max(0, (sumSq / n) - (mean * mean))
  const std = Math.sqrt(variance)
  const range = max - min

  // Calculate percentiles from sorted data
  const sorted = [...data].sort((a, b) => a - b)
  const q1 = sorted[Math.floor(n * 0.25)] || min
  const q3 = sorted[Math.floor(n * 0.75)] || max
  const median = sorted[Math.floor(n * 0.5)] || mean
  const iqr = q3 - q1

  return { n, min, max, mean, std, variance, range, q1, q3, median, iqr, sorted }
})

// Simplified bin count calculations
const statisticalBinCounts = computed(() => {
  const stats = dataStatistics.value
  if (!stats || stats.n === 0) return { auto: 30, fine: 60 }

  const { n, std, range, iqr } = stats

  // Auto: Smart choice between Sturges (normal data) and Freedman-Diaconis (outlier-heavy data)
  const sturges = Math.max(5, Math.min(100, Math.ceil(1 + Math.log2(n))))
  const freedmanDiaconis = iqr > 0 && range > 0 ?
    Math.max(5, Math.min(200, Math.ceil(range / (2 * iqr * Math.pow(n, -1/3))))) : sturges

  // Choose based on data characteristics
  const outlierRatio = stats.outliers / n
  const auto = outlierRatio > 0.05 ? freedmanDiaconis : sturges // Use F-D if >5% outliers

  // Fine: More detail for when users want to see distribution nuances
  const fine = Math.min(200, auto * 2)

  return { auto, fine }
})

const binOptions = computed(() => {
  const stats = statisticalBinCounts.value
  return [
    {
      title: "Auto",
      value: 'auto',
      bins: stats.auto,
      description: "Smart default (adapts to data)"
    },
    {
      title: "Fine Detail",
      value: 'fine',
      bins: stats.fine,
      description: "More bins for detailed view"
    },
    {
      title: "Custom",
      value: 'custom',
      bins: customBinCount.value,
      description: "Manual control"
    }
  ]
})

const binCount = computed(() => {
  if (binSelection.value === 'custom') {
    // Validate custom bin count
    const custom = Math.max(5, Math.min(200, Math.floor(customBinCount.value) || 30))
    if (custom !== customBinCount.value) {
      // Silently correct invalid values
      customBinCount.value = custom
    }
    return custom
  }
  return statisticalBinCounts.value[binSelection.value] || 30
})

const adjustedChartHeight = computed(() => {
  // Subtract space for controls (60px) and statistics box (120px)
  const controlsHeight = 60
  const statsBoxHeight = statistics.value ? (showPercentiles.value ? 120 : 80) : 0
  return props.chartHeight - controlsHeight - statsBoxHeight
})

const zValues = computed(() => {
  if (!props.waferData?.data || props.waferData.available_points === 0) return []

  return props.waferData.data
    .map(point => point.Z || point.z || 0)
    .filter(z => typeof z === 'number' && !isNaN(z) && isFinite(z))
})

const histogramData = computed(() => {
  const data = zValues.value
  const stats = dataStatistics.value

  if (data.length === 0 || !stats) {
    return { bins: [], values: [], binCenters: [], rawCounts: [] }
  }

  const { min, max } = stats
  const bins_count = binCount.value

  // Handle edge case where all values are identical
  if (max === min) {
    return {
      bins: [`${min.toFixed(3)}`],
      values: [data.length],
      binCenters: [min],
      rawCounts: [data.length]
    }
  }

  const binSize = (max - min) / bins_count
  const bins = []
  const values = Array.from({ length: bins_count }, () => 0)
  const binCenters = []

  // Pre-calculate bin boundaries and centers
  for (let i = 0; i < bins_count; i++) {
    const binStart = min + i * binSize
    const binEnd = i === bins_count - 1 ? max : binStart + binSize // Include max in last bin
    const binCenter = binStart + binSize / 2

    bins.push(`${binStart.toFixed(3)}-${binEnd.toFixed(3)}`)
    binCenters.push(binCenter)
  }

  // Efficient binning - single pass through data
  for (const value of data) {
    let binIndex = Math.floor((value - min) / binSize)
    // Handle edge cases
    if (binIndex >= bins_count) binIndex = bins_count - 1
    if (binIndex < 0) binIndex = 0
    values[binIndex]++
  }

  // Calculate display values based on mode
  let displayValues = [...values] // Copy to avoid mutation

  if (displayMode.value === 'density') {
    const totalArea = data.length * binSize
    if (totalArea > 0) {
      displayValues = displayValues.map(count => count / totalArea)
    }
  } else if (displayMode.value === 'cumulative') {
    let cumSum = 0
    displayValues = displayValues.map(count => {
      cumSum += count
      return data.length > 0 ? (cumSum / data.length * 100) : 0
    })
  }

  return { bins, values: displayValues, binCenters, rawCounts: values }
})

const normalCurveData = computed(() => {
  const stats = dataStatistics.value
  if (!stats || !showNormalCurve.value || stats.std === 0) return []

  const { mean, std, n: totalCount } = stats
  const { binCenters } = histogramData.value

  if (binCenters.length === 0) return []

  const binSize = binCenters.length > 1 ? binCenters[1] - binCenters[0] : 1
  const sqrt2Pi = Math.sqrt(2 * Math.PI)

  return binCenters.map(x => {
    try {
      const z = (x - mean) / std

      if (displayMode.value === 'density') {
        const probability = (1 / (std * sqrt2Pi)) * Math.exp(-0.5 * z * z)
        return isFinite(probability) ? probability : 0
      } else if (displayMode.value === 'cumulative') {
        const cdf = 50 * (1 + erf(z / Math.sqrt(2)))
        return isFinite(cdf) ? Math.max(0, Math.min(100, cdf)) : 0
      } else {
        const probability = (1 / (std * sqrt2Pi)) * Math.exp(-0.5 * z * z)
        const frequency = probability * totalCount * binSize
        return isFinite(frequency) ? frequency : 0
      }
    } catch (error) {
      console.warn('Normal curve calculation error:', error)
      return 0
    }
  })
})

const statistics = computed(() => {
  const stats = dataStatistics.value
  if (!stats) return null

  const { n, min, max, mean, std, q1, median, q3, sorted } = stats
  const range = max - min

  // Robust skewness and kurtosis calculations
  let skewness = 0
  let kurtosis = 0
  let outliers = 0

  if (std > 0 && n > 2) {
    let sumSkew = 0
    let sumKurt = 0

    for (const val of sorted) {
      const z = (val - mean) / std
      sumSkew += z * z * z
      sumKurt += z * z * z * z

      // Count outliers (3 sigma rule)
      if (Math.abs(z) > 3) outliers++
    }

    skewness = sumSkew / n
    kurtosis = (sumKurt / n) - 3 // Excess kurtosis
  }

  // Coefficient of variation (handle division by zero)
  const cv = mean !== 0 ? Math.abs(std / mean) * 100 : 0

  return {
    count: n,
    mean: mean.toFixed(3),
    std: std.toFixed(3),
    min: min.toFixed(3),
    max: max.toFixed(3),
    range: range.toFixed(3),
    q1: q1.toFixed(3),
    median: median.toFixed(3),
    q3: q3.toFixed(3),
    skewness: isFinite(skewness) ? skewness.toFixed(3) : '0.000',
    kurtosis: isFinite(kurtosis) ? kurtosis.toFixed(3) : '0.000',
    cv: cv.toFixed(1),
    outliers
  }
})

// Error function approximation for normal CDF
function erf(x) {
  const a1 =  0.254829592
  const a2 = -0.284496736
  const a3 =  1.421413741
  const a4 = -1.453152027
  const a5 =  1.061405429
  const p  =  0.3275911

  const sign = x < 0 ? -1 : 1
  x = Math.abs(x)

  const t = 1.0 / (1.0 + p * x)
  const y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * Math.exp(-x * x)

  return sign * y
}

function initChart() {
  if (!chartContainer.value || props.waferData?.available_points === 0) return

  // Validate data before proceeding
  const { bins, values } = histogramData.value
  if (bins.length === 0 || values.length === 0) {
    console.warn('HistogramChart: No valid data to display')
    return
  }

  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }

  try {
    // Register the shine theme
    echarts.registerTheme('shine', shineThemeData)
    chartInstance = echarts.init(chartContainer.value, 'shine')

    const normalCurve = normalCurveData.value

  const series = [{
    name: displayMode.value === 'cumulative' ? 'Cumulative %' :
          displayMode.value === 'density' ? 'Density' : 'Frequency',
    type: 'bar',
    data: values,
    itemStyle: {
      color: '#3b82f6',
      opacity: 0.7
    }
  }]

  // Add normal curve if enabled
  if (showNormalCurve.value && normalCurve.length > 0) {
    series.push({
      name: 'Normal Distribution',
      type: 'line',
      data: normalCurve,
      smooth: true,
      symbol: 'none',
      lineStyle: {
        color: '#ef4444',
        width: 2
      },
      yAxisIndex: displayMode.value === 'cumulative' ? 1 : 0
    })
  }

  const yAxes = [{
    type: logScale.value ? 'log' : 'value',
    name: displayMode.value === 'cumulative' ? 'Cumulative %' :
          displayMode.value === 'density' ? 'Density' : 'Frequency',
    nameLocation: 'middle',
    nameGap: 50
  }]

  // Add secondary y-axis for cumulative mode with normal curve
  if (showNormalCurve.value && displayMode.value === 'cumulative') {
    yAxes.push({
      type: 'value',
      name: 'Normal CDF %',
      nameLocation: 'middle',
      nameGap: 50,
      position: 'right'
    })
  }

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: {
        type: 'shadow'
      },
      formatter: function (params) {
        try {
          if (!params || !params[0]) return 'No data'

          let result = `Range: ${params[0].name} ${units.value.Z}<br/>`
          params.forEach(param => {
            if (!param || typeof param.value !== 'number') return

            const value = displayMode.value === 'cumulative' ? `${param.value.toFixed(2)}%` :
                         displayMode.value === 'density' ? param.value.toFixed(6) :
                         param.value.toString()
            result += `${param.seriesName}: ${value}<br/>`
          })
          return result
        } catch (error) {
          console.warn('Tooltip formatter error:', error)
          return 'Error displaying tooltip'
        }
      }
    },
    legend: {
      data: series.map(s => s.name).filter(Boolean),
      top: 10
    },
    grid: {
      left: '15%',
      right: showNormalCurve.value && displayMode.value === 'cumulative' ? '15%' : '10%',
      bottom: '20%',
      top: '15%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: bins,
      name: `Z Value (${units.value.Z})`,
      nameLocation: 'middle',
      nameGap: 35,
      axisLabel: {
        rotate: 45,
        interval: Math.max(0, Math.floor(bins.length / 10)),
        fontSize: 10
      }
    },
    yAxis: yAxes,
    series: series,
    animation: false // Better performance for large datasets
  }

  // Add percentile lines if enabled
  if (showPercentiles.value && statistics.value) {
    const markLines = [
      { name: 'Q1', xAxis: findBinIndex(parseFloat(statistics.value.q1)), lineStyle: { color: '#10b981', type: 'dashed' } },
      { name: 'Median', xAxis: findBinIndex(parseFloat(statistics.value.median)), lineStyle: { color: '#f59e0b', type: 'solid' } },
      { name: 'Q3', xAxis: findBinIndex(parseFloat(statistics.value.q3)), lineStyle: { color: '#10b981', type: 'dashed' } }
    ]

    try {
      option.series[0].markLine = {
        data: markLines.filter(line => isFinite(line.xAxis)),
        label: {
          show: true,
          position: 'middle'
        }
      }
    } catch (error) {
      console.warn('HistogramChart: Failed to add percentile lines:', error)
    }
  }

    chartInstance.setOption(option, true) // true = not merge, replace completely
  } catch (error) {
    console.error('HistogramChart: Chart initialization failed:', error)
    if (chartInstance) {
      chartInstance.dispose()
      chartInstance = null
    }
  }
}

function findBinIndex(value) {
  const { binCenters } = histogramData.value
  if (binCenters.length === 0) return 0

  let closestIndex = 0
  let minDiff = Math.abs(binCenters[0] - value)

  for (let i = 1; i < binCenters.length; i++) {
    const diff = Math.abs(binCenters[i] - value)
    if (diff < minDiff) {
      minDiff = diff
      closestIndex = i
    }
  }

  return closestIndex
}

function getCurrentMethodName() {
  const method = binOptions.value.find(opt => opt.value === binSelection.value)
  return method ? method.title : 'Unknown'
}

function getCurrentMethodDescription() {
  const method = binOptions.value.find(opt => opt.value === binSelection.value)
  return method ? method.description : 'No description available'
}

function getSkewnessInterpretation(skewness) {
  const value = parseFloat(skewness)
  if (isNaN(value)) return 'Invalid'
  if (Math.abs(value) < 0.5) return 'Approximately symmetric'
  if (value > 0.5) return 'Right-skewed (positive)'
  if (value < -0.5) return 'Left-skewed (negative)'
  return 'Unknown'
}

function getKurtosisInterpretation(kurtosis) {
  const value = parseFloat(kurtosis)
  if (isNaN(value)) return 'Invalid'
  if (Math.abs(value) < 0.5) return 'Similar to normal distribution'
  if (value > 0.5) return 'Heavy tails (leptokurtic)'
  if (value < -0.5) return 'Light tails (platykurtic)'
  return 'Unknown'
}

function handleResize() {
  if (chartInstance) {
    chartInstance.resize()
  }
}

// Watchers with debouncing for performance
let chartUpdateTimeout = null

function scheduleChartUpdate() {
  if (chartUpdateTimeout) {
    clearTimeout(chartUpdateTimeout)
  }
  chartUpdateTimeout = setTimeout(() => {
    initChart()
    chartUpdateTimeout = null
  }, 100) // 100ms debounce
}

watch([binSelection, customBinCount, displayMode, showNormalCurve, showPercentiles, logScale], () => {
  scheduleChartUpdate()
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
  if (chartUpdateTimeout) {
    clearTimeout(chartUpdateTimeout)
    chartUpdateTimeout = null
  }

  if (chartInstance) {
    try {
      chartInstance.dispose()
    } catch (error) {
      console.warn('Error disposing chart:', error)
    }
    chartInstance = null
  }

  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.histogram-chart-wrapper {
  width: 100%;
}

.statistics-box {
  background: transparent;
}

.statistics-box .v-card {
  background: rgba(248, 250, 252, 0.8);
  border: 1px solid #e2e8f0;
}
</style>
