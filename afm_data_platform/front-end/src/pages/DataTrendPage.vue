<template>
  <v-container class="pa-6">
    <!-- Breadcrumb Navigation -->
    <BreadcrumbNav :items="breadcrumbItems" />
    
    <v-row>
      <v-col cols="12">
        <!-- Header with back button -->
        <div class="d-flex align-center mb-4">
          <v-btn 
            variant="elevated" 
            color="primary"
            @click="goBack" 
            class="mr-4 back-button">
            <v-icon start>mdi-arrow-left</v-icon>
            Back to Search
          </v-btn>

          <div>
            <h1 class="text-h4 font-weight-bold">AFM Data Trend Analysis</h1>
            <div class="d-flex align-center ga-3 mt-1">
              <v-chip color="primary" variant="tonal" size="small">
                <v-icon start size="small">mdi-file-document-multiple</v-icon>
                {{ dataStore.groupedCount }} measurements
              </v-chip>
              <v-chip v-if="uniqueSites && uniqueSites.length > 0" color="secondary" variant="tonal" size="small">
                <v-icon start size="small">mdi-target</v-icon>
                {{ uniqueSites.length }} sites
              </v-chip>
            </div>
          </div>
        </div>

        <!-- Selected Measurements Cards -->
        <v-card class="mb-4" elevation="3">
          <v-card-title class="bg-primary text-white py-3">
            <v-icon start>mdi-group</v-icon>
            Selected Measurements
          </v-card-title>

          <v-card-text class="pa-4">
            <!-- Loading State -->
            <div v-if="isLoading" class="text-center pa-8">
              <v-progress-circular indeterminate color="primary" size="64" />
              <p class="mt-4 text-body-1">Loading measurement details...</p>
            </div>

            <!-- Empty State -->
            <div v-else-if="dataStore.groupedCount === 0" class="text-center pa-8">
              <v-icon size="64" color="grey">mdi-group-off</v-icon>
              <h3 class="text-h6 mt-4">No Measurements Selected</h3>
              <p class="text-body-2 text-medium-emphasis mt-2">
                Go back to the search page and select measurements to compare
              </p>
              <v-btn color="primary" variant="elevated" @click="goBack" class="mt-4">
                <v-icon start>mdi-arrow-left</v-icon>
                Back to Search
              </v-btn>
            </div>

            <!-- Measurement Cards Grid -->
            <v-row v-else dense>
              <v-col v-for="(measurement, index) in enrichedMeasurements" :key="index" cols="12" sm="6" md="4" lg="3">
                <SimplifiedMeasurementCard :measurement="measurement" :order-number="index + 1" :loading="isLoading" />
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- Trend Analysis Tabs -->
        <v-card elevation="3">
          <v-tabs v-model="activeTab" bg-color="primary">
            <v-tab value="time-series">
              <v-icon left>mdi-chart-timeline</v-icon>
              Time Series
            </v-tab>
            <v-tab value="comparison">
              <v-icon left>mdi-chart-bar</v-icon>
              Parameter Comparison
            </v-tab>
            <v-tab value="correlation">
              <v-icon left>mdi-scatter-plot</v-icon>
              Correlation Analysis
            </v-tab>
          </v-tabs>

          <v-window v-model="activeTab">
            <!-- Time Series Tab -->
            <v-window-item value="time-series">
              <v-card-text>
                <!-- Loading State -->
                <div v-if="isLoadingGroupData" class="text-center pa-8">
                  <v-progress-circular indeterminate color="primary" size="64" />
                  <p class="mt-4 text-body-1">Loading measurement data from server...</p>
                </div>

                <!-- No Data State -->
                <div v-else-if="!groupSummaryData || Object.keys(groupSummaryData).length === 0"
                  class="text-center pa-8">
                  <v-icon size="64" color="grey">mdi-chart-timeline</v-icon>
                  <h3 class="text-h6 mt-4">Loading Measurement Data</h3>
                  <p class="text-body-2 text-medium-emphasis mt-2">
                    Please wait while measurement data is being loaded automatically...
                  </p>
                  <v-progress-circular indeterminate color="primary" class="mt-4" />
                </div>

                <!-- Data Display -->
                <div v-else>
                  <!-- Data Summary -->
                  <div class="mb-4">
                    <v-alert density="compact" variant="tonal" color="info">
                      <v-icon start size="small">mdi-information</v-icon>
                      <span class="text-body-2">
                        Loaded {{ groupDetailedData?.length || 0 }} measurements with
                        {{ uniqueSites?.length || 0 }} unique sites
                      </span>
                    </v-alert>
                  </div>

                  <!-- Time Series Controls -->
                  <v-card variant="outlined" class="mt-4">
                    <v-card-title class="text-subtitle-1">
                      <v-icon start size="small">mdi-tune</v-icon>
                      Time Series Configuration
                    </v-card-title>
                    <v-card-text>
                      <!-- Site Selection with Chips -->
                      <div class="mb-4">
                        <div class="text-subtitle-2 mb-2 d-flex align-center">
                          <v-icon start size="small" class="mr-1">mdi-target</v-icon>
                          Select Site
                        </div>
                        <v-chip-group v-model="selectedSites" selected-class="text-primary" multiple>
                          <v-chip v-for="site in uniqueSites" :key="site" :value="site" variant="outlined" filter
                            size="small">
                            {{ site }}
                          </v-chip>
                        </v-chip-group>
                        <div v-if="selectedSites && selectedSites.length > 0" class="text-caption text-medium-emphasis mt-1">
                          Selected ({{ selectedSites.length }}): {{ selectedSites.join(', ') }}
                        </div>
                      </div>

                      <!-- Other Controls -->
                      <v-row dense>
                        <v-col cols="12" md="6">
                          <v-select v-model="selectedItem" :items="availableItems" label="Select Item (Statistic)"
                            variant="outlined" density="compact" prepend-inner-icon="mdi-sigma" clearable />
                        </v-col>
                        <v-col cols="12" md="6">
                          <v-select v-model="selectedColumn" :items="nmColumns" label="Select Measurement (nm)"
                            variant="outlined" density="compact" prepend-inner-icon="mdi-ruler" clearable />
                        </v-col>
                      </v-row>
                    </v-card-text>
                  </v-card>

                  <!-- Time Series Chart -->
                  <v-card variant="outlined" class="mt-4" v-if="selectedSites.length > 0 && selectedItem && selectedColumn">
                    <v-card-title class="text-subtitle-1">
                      <v-icon start size="small">mdi-chart-line</v-icon>
                      Time Series: {{ selectedColumn }} - {{ selectedItem }} for {{ selectedSites.length === 1 ? 'Site ' + selectedSites[0] : selectedSites.length + ' Sites' }}
                    </v-card-title>
                    <v-card-text class="pa-4">
                      <TimeSeriesChart :time-series-data="timeSeriesData" :selected-column="selectedColumn"
                        :chart-height="700" :loading="isProcessingTimeSeries" />
                    </v-card-text>
                  </v-card>

                  <!-- No Selection Message -->
                  <v-card variant="outlined" class="mt-4" v-else>
                    <v-card-text class="text-center pa-8 text-medium-emphasis">
                      <v-icon size="48">mdi-chart-timeline-variant</v-icon>
                      <p class="mt-3">Select Sites, Item, and Measurement to view time series</p>
                      <p class="text-caption">Data is loaded and ready for visualization</p>
                    </v-card-text>
                  </v-card>
                </div>
              </v-card-text>
            </v-window-item>

            <!-- Parameter Comparison Tab -->
            <v-window-item value="comparison">
              <v-card-text>
                <div class="text-center pa-8">
                  <v-icon size="64" color="success">mdi-chart-bar</v-icon>
                  <h3 class="text-h6 mt-4">Parameter Comparison</h3>
                  <p class="text-body-2 text-medium-emphasis mt-2">
                    Compare roughness parameters (RQ, RA, RMAX) across selected measurements
                  </p>
                  <v-divider class="my-4" />
                  <div class="text-left">
                    <h4 class="text-subtitle-1 mb-2">Features to be implemented:</h4>
                    <ul class="text-body-2 text-medium-emphasis">
                      <li>Side-by-side bar charts for each parameter</li>
                      <li>Statistical summary (mean, std, min, max)</li>
                      <li>Outlier detection and highlighting</li>
                      <li>Fab/Recipe grouping options</li>
                    </ul>
                  </div>
                </div>
              </v-card-text>
            </v-window-item>

            <!-- Correlation Analysis Tab -->
            <v-window-item value="correlation">
              <v-card-text>
                <div class="text-center pa-8">
                  <v-icon size="64" color="warning">mdi-scatter-plot</v-icon>
                  <h3 class="text-h6 mt-4">Correlation Analysis</h3>
                  <p class="text-body-2 text-medium-emphasis mt-2">
                    Analyze relationships between different measurement parameters
                  </p>
                  <v-divider class="my-4" />
                  <div class="text-left">
                    <h4 class="text-subtitle-1 mb-2">Features to be implemented:</h4>
                    <ul class="text-body-2 text-medium-emphasis">
                      <li>Scatter plots with correlation coefficients</li>
                      <li>Heatmap of parameter correlations</li>
                      <li>Regression line fitting</li>
                      <li>Statistical significance testing</li>
                    </ul>
                  </div>
                </div>
              </v-card-text>
            </v-window-item>
          </v-window>
        </v-card>

      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDataStore } from '@/stores/dataStore.js'
import { apiService } from '@/services/api'
import SimplifiedMeasurementCard from '@/components/DataTrend/SimplifiedMeasurementCard.vue'
import TimeSeriesChart from '@/components/DataTrend/charts/TimeSeriesChart.vue'
import BreadcrumbNav from '@/components/common/BreadcrumbNav.vue'

const router = useRouter()
const dataStore = useDataStore()
const activeTab = ref('time-series')
const isLoading = ref(false)
const isLoadingGroupData = ref(false)
const groupDetailedData = ref([])
const groupSummaryData = ref({})

// Time series controls
const selectedSites = ref([])  // Multiple site selection
const selectedItem = ref('MEAN')
const selectedColumn = ref('')
const isProcessingTimeSeries = ref(false)

// Breadcrumb items
const breadcrumbItems = [
  {
    title: 'Data Trend Analysis',
    icon: 'mdi-chart-timeline',
    disabled: true
  }
]

// Computed property to enrich measurement data with additional information
const enrichedMeasurements = computed(() => {
  if (!dataStore.groupedData || dataStore.groupedData.length === 0) {
    return []
  }

  return dataStore.groupedData.map((measurement, index) => {
    // Extract core information for display
    const enriched = {
      ...measurement,
      // Ensure all required fields have default values
      fab: measurement.fab || 'SK_Hynix_ITC',
      lot_id: measurement.lot_id || extractLotIdFromFilename(measurement.filename),
      wf_id: measurement.wf_id || 'W01',
      rcp_id: measurement.rcp_id || measurement.recipe_name || 'Unknown Recipe',
      tool: measurement.tool || dataStore.selectedTool || 'MAP608',
      sample_id: measurement.sample_id || measurement.filename,
      carrier_id: measurement.carrier_id || generateCarrierId(measurement),
      // Generate missing timestamps if needed
      event_time: measurement.event_time || measurement.formatted_date || new Date().toISOString(),
      // Add computed properties
      measurementIndex: index + 1,
      isValid: validateMeasurementData(measurement)
    }

    console.log(`🔍 [DataTrendPage] Enriched measurement ${index + 1}:`, enriched)
    return enriched
  })
})

// Computed properties for unique sites and points
const uniqueSites = computed(() => {
  if (!groupSummaryData.value || Object.keys(groupSummaryData.value).length === 0) return []

  const sites = new Set()

  // Look through summary data from all files to find unique sites
  Object.values(groupSummaryData.value).forEach(fileData => {
    if (fileData.summary && Array.isArray(fileData.summary)) {
      fileData.summary.forEach(record => {
        // Check various possible field names for Site
        const siteValue = record.Site || record.Site_ID || record['Site ID'] || record.site_id
        if (siteValue) {
          sites.add(siteValue)
        }
      })
    }
  })

  const sitesArray = Array.from(sites)

  // Natural sort to handle numeric parts correctly (1_UL, 2_UL, 10_UL)
  sitesArray.sort((a, b) => {
    // Extract numeric and text parts
    const aMatch = a.match(/^(\d+)(.*)$/)
    const bMatch = b.match(/^(\d+)(.*)$/)

    if (aMatch && bMatch) {
      const aNum = parseInt(aMatch[1])
      const bNum = parseInt(bMatch[1])

      // First compare numbers
      if (aNum !== bNum) {
        return aNum - bNum
      }

      // If numbers are equal, compare the rest
      return aMatch[2].localeCompare(bMatch[2])
    }

    // Fallback to regular string comparison
    return a.localeCompare(b)
  })

  console.log('🔍 [DataTrendPage] Unique sites found (sorted):', sitesArray)
  return sitesArray
})


// Computed properties for time series dropdowns
const availableItems = computed(() => {
  // Standard statistic items
  return ['MEAN', 'STDEV', 'MIN', 'MAX', 'RANGE']
})

const nmColumns = computed(() => {
  if (!groupSummaryData.value || Object.keys(groupSummaryData.value).length === 0) return []

  // Get the first file's summary data to extract column names
  const firstFile = Object.keys(groupSummaryData.value)[0]
  const summaryData = groupSummaryData.value[firstFile]?.summary || []

  if (summaryData.length === 0) return []

  // Extract columns that contain "(nm)"
  const firstRecord = summaryData[0]
  const allKeys = Object.keys(firstRecord)

  return allKeys.filter(key =>
    key.includes('(nm)') || key.toLowerCase().includes('nm')
  ).sort()
})

// Computed property for time series data
const timeSeriesData = computed(() => {
  if (!selectedSites.value || selectedSites.value.length === 0 || !selectedItem.value || !selectedColumn.value) return []
  if (!groupSummaryData.value || Object.keys(groupSummaryData.value).length === 0) return []

  console.log('🔍 [Time Series] Computing time series data...')
  console.log('Selected Sites:', selectedSites.value)
  console.log('Selected Item:', selectedItem.value)
  console.log('Selected Column:', selectedColumn.value)
  console.log('Available files:', Object.keys(groupSummaryData.value))

  // Create a series for each selected site
  const seriesData = selectedSites.value.map(site => {
    const dataPoints = []

    // Process each measurement file for this site
    Object.entries(groupSummaryData.value).forEach(([filename, fileData]) => {
      const { info, summary } = fileData

      if (!summary || !Array.isArray(summary)) {
        console.warn(`⚠️ No summary data for file: ${filename}`)
        return
      }

      // Find the corresponding original measurement from dataStore to get the correct timestamp
      const originalMeasurement = dataStore.groupedData.find(m => m.filename === filename)
      
      // Priority: Use Start Time from info first, then fall back to other timestamps
      const startTime = info?.['Start Time']
      const timestamp = startTime ||
        originalMeasurement?.event_time ||
        originalMeasurement?.formatted_date ||
        originalMeasurement?.measurement_date ||
        info?.event_time ||
        info?.formatted_date ||
        info?.measurement_date ||
        new Date().toISOString()
      
      // Debug log to verify Start Time usage
      if (startTime) {
        console.log(`📅 Using Start Time for ${filename}: ${startTime}`)
      } else {
        console.log(`⚠️ No Start Time found for ${filename}, using fallback: ${timestamp}`)
      }

      // Find record for the current site
      const record = summary.find(r => {
        // Check various possible field names for Site
        const siteValue = r.Site || r.Site_ID || r['Site ID'] || r.site_id
        const siteMatch = siteValue === site
        const itemMatch = r.ITEM === selectedItem.value

        return siteMatch && itemMatch
      })

      if (record && record[selectedColumn.value] !== undefined) {
        const dataPoint = {
          timestamp: timestamp,
          value: parseFloat(record[selectedColumn.value]),
          lotId: originalMeasurement?.lot_id || info?.lot_id || extractLotIdFromFilename(filename),
          recipe: originalMeasurement?.rcp_id || originalMeasurement?.recipe_name || info?.rcp_id || info?.recipe_name || 'Unknown',
          filename: filename,
          site: site
        }

        dataPoints.push(dataPoint)
      }
    })

    // Sort by timestamp
    dataPoints.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))

    return {
      name: site,
      data: dataPoints
    }
  })

  console.log(`📊 Time series data for ${selectedSites.value.length} sites:`, seriesData)
  return seriesData
})

// Lifecycle
onMounted(() => {
  console.log('🚀 [DataTrendPage] Mounted with grouped data:', dataStore.groupedData)
  console.log('🚀 [DataTrendPage] Selected tool:', dataStore.selectedTool)

  // Check if we have pre-loaded data from sessionStorage
  const storedData = sessionStorage.getItem('groupDetailedData')
  if (storedData) {
    try {
      const loadedResults = JSON.parse(storedData)
      console.log(`📊 [DataTrendPage] Found pre-loaded data in sessionStorage: ${loadedResults.length} measurements`)

      // Process the loaded data
      processLoadedGroupData(loadedResults)

      // Clear the sessionStorage to prevent stale data on refresh
      sessionStorage.removeItem('groupDetailedData')

      // Auto-switch to time series tab to show the data
      activeTab.value = 'time-series'
    } catch (error) {
      console.error('❌ [DataTrendPage] Error parsing stored data:', error)
    }
  } else {
    console.log('📊 [DataTrendPage] No pre-loaded data found, auto-loading measurement data...')

    // Auto-load measurement data if we have grouped data
    if (dataStore.groupedData && dataStore.groupedData.length > 0) {
      console.log('✅ [DataTrendPage] Found', dataStore.groupedData.length, 'measurements, auto-loading data...')
      loadGroupDataFromFlask()
    } else {
      console.warn('⚠️ [DataTrendPage] No grouped data available for auto-loading')
    }
  }
})

// Helper functions
function extractLotIdFromFilename(filename) {
  if (!filename) return 'Unknown'

  // Extract lot ID from filename pattern #date#recipe#lot_id_time#slot_measured#
  const parts = filename.split('#')
  if (parts.length >= 4) {
    const lotPart = parts[3]
    const lotId = lotPart.split('_')[0] // Get lot ID before underscore
    return lotId || 'Unknown'
  }
  return 'Unknown'
}

function generateCarrierId(measurement) {
  // Generate carrier ID from available data
  if (measurement.carrier_id) return measurement.carrier_id
  if (measurement.lot_wf) return measurement.lot_wf

  const lotId = measurement.lot_id || extractLotIdFromFilename(measurement.filename)
  const wfId = measurement.wf_id || 'W01'

  return `${lotId}_${wfId}`
}

function validateMeasurementData(measurement) {
  // Check if measurement has minimum required data for navigation
  const hasFilename = !!(measurement.filename)
  const hasRecipe = !!(measurement.rcp_id || measurement.recipe_name)

  return hasFilename && hasRecipe
}

function goBack() {
  // Use browser's back navigation to respect history
  router.back()
}

// Process pre-loaded group data
function processLoadedGroupData(loadedResults) {
  console.log('📊 [DataTrendPage] Processing loaded group data...')

  // Process and combine the detailed data
  const allDetailedData = []
  const summaryByFile = {}

  loadedResults.forEach(result => {
    // Add filename to each detailed record for tracking
    if (result.detailedData && Array.isArray(result.detailedData)) {
      const enrichedData = result.detailedData.map(record => ({
        ...record,
        _filename: result.filename,
        _tool: result.tool
      }))
      allDetailedData.push(...enrichedData)
    }

    // Store summary data by filename
    summaryByFile[result.filename] = {
      info: result.info,
      summary: result.summary,
      availablePoints: result.availablePoints
    }
  })

  groupDetailedData.value = allDetailedData
  groupSummaryData.value = summaryByFile

  console.log(`📊 Total detailed records loaded: ${allDetailedData.length}`)
  console.log(`📊 Unique sites found: ${uniqueSites.value.length}`)

  // Debug: Log sample data structure
  if (Object.keys(summaryByFile).length > 0) {
    const firstFile = Object.keys(summaryByFile)[0]
    const sampleData = summaryByFile[firstFile]
    console.log('📊 [DataTrendPage] Sample data structure from first file:')
    console.log('   File:', firstFile)
    console.log('   Info:', sampleData.info)
    console.log('   Info keys:', Object.keys(sampleData.info || {}))
    console.log('   Start Time:', sampleData.info?.['Start Time'])
    if (sampleData.summary && sampleData.summary.length > 0) {
      console.log('   First summary record:', sampleData.summary[0])
      console.log('   Available columns:', Object.keys(sampleData.summary[0]))
    }
  }
}

// Load detailed data for all measurements in the group
async function loadGroupDataFromFlask() {
  console.log('🚀 [DataTrendPage] Loading group data from Flask...')

  if (dataStore.groupedData.length === 0) {
    console.warn('⚠️ No measurements in group to load')
    return
  }

  isLoadingGroupData.value = true
  groupDetailedData.value = []
  groupSummaryData.value = {}

  try {
    // Load data for each measurement in the group
    const loadPromises = dataStore.groupedData.map(async (measurement) => {
      if (!measurement.filename) {
        console.warn(`⚠️ Skipping measurement without filename:`, measurement)
        return null
      }

      try {
        console.log(`📊 Loading data for: ${measurement.filename}`)
        const toolName = measurement.tool || dataStore.selectedTool || 'MAP608'

        // Fetch detailed measurement data
        const response = await apiService.getAfmFileDetail(measurement.filename, toolName)

        if (response.success && response.data) {
          return {
            filename: measurement.filename,
            tool: toolName,
            info: response.data.information || {},
            summary: response.data.summary || [],
            detailedData: response.data.data || [],
            availablePoints: response.data.available_points || []
          }
        } else {
          console.error(`❌ Failed to load data for ${measurement.filename}:`, response.error)
          return null
        }
      } catch (error) {
        console.error(`❌ Error loading ${measurement.filename}:`, error)
        return null
      }
    })

    // Wait for all measurements to load
    const results = await Promise.all(loadPromises)
    const validResults = results.filter(r => r !== null)

    console.log(`✅ Loaded ${validResults.length} out of ${dataStore.groupedData.length} measurements`)

    // Process and combine the detailed data
    const allDetailedData = []
    const summaryByFile = {}

    validResults.forEach(result => {
      // Add filename to each detailed record for tracking
      if (result.detailedData && Array.isArray(result.detailedData)) {
        const enrichedData = result.detailedData.map(record => ({
          ...record,
          _filename: result.filename,
          _tool: result.tool
        }))
        allDetailedData.push(...enrichedData)
      }

      // Store summary data by filename
      summaryByFile[result.filename] = {
        info: result.info,
        summary: result.summary,
        availablePoints: result.availablePoints
      }
    })

    groupDetailedData.value = allDetailedData
    groupSummaryData.value = summaryByFile

    console.log(`📊 Total detailed records loaded: ${allDetailedData.length}`)
    console.log(`📊 Unique sites found: ${uniqueSites.value.length}`)
    
    // Debug: Log sample data structure
    if (Object.keys(summaryByFile).length > 0) {
      const firstFile = Object.keys(summaryByFile)[0]
      const sampleData = summaryByFile[firstFile]
      console.log('📊 [DataTrendPage] Sample data structure from first file:')
      console.log('   File:', firstFile)
      console.log('   Info:', sampleData.info)
      console.log('   Info keys:', Object.keys(sampleData.info || {}))
      console.log('   Start Time:', sampleData.info?.['Start Time'])
    }

    // Auto-switch to time series tab to show the data
    activeTab.value = 'time-series'

  } catch (error) {
    console.error('❌ Error loading group data:', error)
  } finally {
    isLoadingGroupData.value = false
  }
}

</script>

<style scoped>
/* Distinctive back button */
.back-button {
  border-radius: 12px;
  font-weight: 600;
  text-transform: none;
  letter-spacing: 0.5px;
  box-shadow: 0 4px 12px rgba(var(--v-theme-primary), 0.3);
  transition: all 0.3s ease;
}

.back-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(var(--v-theme-primary), 0.4);
}

/* Card hover effects */
.v-card {
  transition: all 0.3s ease;
}

.v-card:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12) !important;
}

/* Breadcrumb styling */
.v-breadcrumbs-item {
  cursor: pointer;
  transition: color 0.2s ease;
}

.v-breadcrumbs-item:not([disabled]):hover {
  color: rgb(var(--v-theme-primary));
}
</style>
