<template>
  <div>

    <!-- Display statistics when summary data is available -->
    <div v-if="summaryData && summaryData.length > 0">
      <!-- Scatter Chart -->
      <v-card elevation="2">
        <v-card-title class="bg-primary text-white py-2 text-subtitle-1">
          <v-icon start size="small">mdi-chart-scatter-plot</v-icon>
          Summary Scatter Chart
        </v-card-title>

        <v-card-text class="pa-3">
          <!-- Chart Controls -->
          <v-row class="mb-3">
            <v-col cols="12" sm="6">
              <v-select v-model="selectedStatistic" :items="availableStatistics" label="Statistic Type"
                density="compact" variant="outlined" hide-details />
            </v-col>
            <v-col cols="12" sm="6">
              <v-select v-model="selectedMeasurements" :items="availableMeasurements" label="Measurements" multiple
                chips density="compact" variant="outlined" hide-details />
            </v-col>
          </v-row>

          <!-- Chart Container -->
          <div class="chart-wrapper">
            <StatisticalScatterChart 
              :summary-data="summaryData"
              :selected-statistic="selectedStatistic"
              :selected-measurements="selectedMeasurements"
            />
          </div>
        </v-card-text>
      </v-card>
    </div>

    <!-- No data message -->
    <div v-else class="text-center pa-6 text-medium-emphasis">
      <v-card elevation="2">
        <v-card-text class="pa-6">
          <v-icon size="64" class="mb-3">mdi-chart-line-variant</v-icon>
          <div class="text-h6 mb-2">No Statistical Data Available</div>
          <div class="text-body-2">Load measurement data to view point-by-point statistics</div>
        </v-card-text>
      </v-card>
    </div>
  </div>
</template>

<script setup>
import { computed, watch, ref, onMounted } from 'vue'
import StatisticalScatterChart from './charts/StatisticalScatterChart.vue'

const props = defineProps({
  summaryData: {
    type: Array,
    default: () => []
  },
  compact: {
    type: Boolean,
    default: false
  }
})

// Emits for row click events
const emit = defineEmits(['row-click', 'statistic-selected'])

// Chart controls
const selectedStatistic = ref('MEAN')
const selectedMeasurements = ref(['Left_H (nm)', 'Right_H (nm)', 'Ref_H (nm)'])

// Available options for controls
const availableStatistics = ref(['MEAN', 'STDEV', 'MIN', 'MAX', 'RANGE'])
const availableMeasurements = computed(() => {
  if (!props.summaryData || props.summaryData.length === 0) return []

  const firstRecord = props.summaryData[0]
  const allKeys = Object.keys(firstRecord)

  return allKeys.filter(key =>
    key !== 'ITEM' && key !== 'Site' &&
    (key.includes('(') || key.includes('nm') || key.includes('_H') || key.includes('Left') || key.includes('Right') || key.includes('Ref'))
  )
})

// Watch for data changes
watch(() => props.summaryData, (newData) => {
  console.log(`🏁 [StatisticalInfoByPoints] Received summary data:`)
  console.log(`🏁 [StatisticalInfoByPoints] Type:`, typeof newData)
  console.log(`🏁 [StatisticalInfoByPoints] Is Array:`, Array.isArray(newData))
  console.log(`🏁 [StatisticalInfoByPoints] Length:`, newData?.length || 0)
  console.log(`🏁 [StatisticalInfoByPoints] Full data:`, newData)

  if (newData && Array.isArray(newData) && newData.length > 0) {
    console.log(`🏁 [StatisticalInfoByPoints] First record:`, newData[0])
    console.log(`🏁 [StatisticalInfoByPoints] First record keys:`, Object.keys(newData[0]))
    console.log(`🏁 [StatisticalInfoByPoints] Has ITEM field:`, 'ITEM' in newData[0])
    console.log(`🏁 [StatisticalInfoByPoints] Has Site field:`, 'Site' in newData[0])

    // Check for data quality issues
    const hasValidStructure = newData.every(record =>
      record && typeof record === 'object' && Object.keys(record).length > 0
    )
    console.log(`🏁 [StatisticalInfoByPoints] All records have valid structure:`, hasValidStructure)

    if (!hasValidStructure) {
      console.error(`❌ [StatisticalInfoByPoints] Invalid data structure detected`)
    }
  } else {
    console.warn(`⚠️ [StatisticalInfoByPoints] No valid summary data received. Data:`, newData)
  }
}, { immediate: true })


// Lifecycle
onMounted(() => {
  console.log(`🚀 [StatisticalInfoByPoints] Component mounted`)
  console.log(`📊 [StatisticalInfoByPoints] Props at mount:`, {
    summaryDataLength: props.summaryData?.length,
    summaryDataSample: props.summaryData?.[0],
    compact: props.compact
  })

  // Initialize available measurements
  if (availableMeasurements.value.length > 0) {
    selectedMeasurements.value = availableMeasurements.value.slice(0, 3)
    console.log(`✅ [StatisticalInfoByPoints] Initialized selected measurements:`, selectedMeasurements.value)
  }
})

// Watch for changes in available measurements to update selected measurements
watch(availableMeasurements, (newMeasurements) => {
  console.log(`🔄 [StatisticalInfoByPoints] Available measurements changed:`, newMeasurements)

  if (newMeasurements.length > 0 && selectedMeasurements.value.length === 0) {
    selectedMeasurements.value = newMeasurements.slice(0, 3)
    console.log(`✅ [StatisticalInfoByPoints] Auto-selected measurements:`, selectedMeasurements.value)
  }
}, { immediate: true })

</script>

<style scoped>
/* Chart container styling */
.v-card {
  height: 100%;
  min-height: 750px;
  display: flex;
  flex-direction: column;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.v-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.v-card-text {
  flex: 1;
  display: flex;
  flex-direction: column;
}

/* Chart wrapper to ensure proper height management */
.chart-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 550px;
  height: calc(100% - 80px); /* Subtract the height of controls */
  position: relative;
}

.chart-wrapper > div {
  flex: 1;
  width: 100%;
  height: 100%;
}
</style>
