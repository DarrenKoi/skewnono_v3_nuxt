<template>
  <v-container fluid class="pa-6 px-md-8 px-lg-12">
    <!-- Breadcrumb Navigation -->
    <BreadcrumbNav :items="breadcrumbItems" />
    
    <!-- Distinctive Back Button and Download Options -->
    <div class="mb-3 d-flex justify-space-between align-center flex-wrap ga-3">
      <v-btn color="primary" variant="elevated" size="large" @click="goBack" class="back-button">
        <v-icon start>mdi-arrow-left</v-icon>
        {{ referrer === 'data-trend' ? 'Back to Data Trend' : 'Back to Search' }}
      </v-btn>

      <!-- Download Menu -->
      <div class="d-flex ga-2">
        <v-menu>
          <template v-slot:activator="{ props }">
            <v-btn color="success" variant="elevated" v-bind="props" :disabled="!hasData">
              <v-icon start>mdi-download</v-icon>
              Download Data
              <v-icon end>mdi-menu-down</v-icon>
            </v-btn>
          </template>
          <v-list>
            <v-list-item @click="downloadMeasurementInfo"
              :disabled="!measurementInfo || Object.keys(measurementInfo).length === 0">
              <template v-slot:prepend>
                <v-icon :color="measurementInfo && Object.keys(measurementInfo).length > 0 ? 'success' : 'grey'">
                  {{ measurementInfo && Object.keys(measurementInfo).length > 0 ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
              </template>
              <v-list-item-title>
                Measurement Info
                <span v-if="measurementInfo && Object.keys(measurementInfo).length > 0" class="text-caption text-success ml-1">
                  ({{ Object.keys(measurementInfo).length }} fields)
                </span>
              </v-list-item-title>
            </v-list-item>

            <v-list-item @click="downloadSummaryStatistics" :disabled="!summaryData || summaryData.length === 0">
              <template v-slot:prepend>
                <v-icon :color="summaryData && summaryData.length > 0 ? 'success' : 'grey'">
                  {{ summaryData && summaryData.length > 0 ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
              </template>
              <v-list-item-title>
                Summary Statistics
                <span v-if="summaryData && summaryData.length > 0" class="text-caption text-success ml-1">
                  ({{ summaryData.length }} points)
                </span>
              </v-list-item-title>
            </v-list-item>

            <v-list-item @click="downloadDetailedData" :disabled="!detailedData || detailedData.length === 0">
              <template v-slot:prepend>
                <v-icon :color="detailedData && detailedData.length > 0 ? 'success' : 'grey'">
                  {{ detailedData && detailedData.length > 0 ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
              </template>
              <v-list-item-title>
                Detailed Data
                <span v-if="detailedData && detailedData.length > 0" class="text-caption text-success ml-1">
                  ({{ detailedData.length }} rows)
                </span>
              </v-list-item-title>
            </v-list-item>

            <v-list-item @click="downloadProfileData" :disabled="!profileData || profileData.length === 0">
              <template v-slot:prepend>
                <v-icon :color="profileData && profileData.length > 0 ? 'success' : 'grey'">
                  {{ profileData && profileData.length > 0 ? 'mdi-check-circle' : 'mdi-close-circle' }}
                </v-icon>
              </template>
              <v-list-item-title>
                Profile Data (X,Y,Z)
                <span v-if="profileData && profileData.length > 0" class="text-caption text-success ml-1">
                  ({{ profileData.length.toLocaleString() }} points)
                </span>
              </v-list-item-title>
            </v-list-item>

            <v-divider></v-divider>

            <v-list-item @click="downloadAllData" :disabled="!hasData">
              <template v-slot:prepend>
                <v-icon :color="hasData ? 'primary' : 'grey'">mdi-package-down</v-icon>
              </template>
              <v-list-item-title class="font-weight-medium">
                Download All (CSV)
                <v-chip v-if="hasData" size="x-small" color="primary" variant="tonal" class="ml-2">
                  Combined
                </v-chip>
              </v-list-item-title>
            </v-list-item>
          </v-list>
        </v-menu>
      </div>
    </div>

    <!-- First row: Information and Scatter Chart with equal heights -->
    <v-row dense class="mb-3 equal-height-row">
      <!-- First column: Information -->
      <v-col cols="12" lg="6" class="d-flex">
        <div class="info-scatter-container w-100">
          <MeasurementInfo :measurement-info="measurementInfo" :summary-data="summaryData" :compact="true" />
        </div>
      </v-col>

      <!-- Second column: Scatter Chart -->
      <v-col cols="12" lg="6" class="d-flex">
        <div class="info-scatter-container w-100">
          <StatisticalInfoByPoints :summary-data="summaryData" @row-click="handleStatisticRowClick"
            @statistic-selected="handleStatisticSelected" :compact="true" />
        </div>
      </v-col>
    </v-row>

    <!-- Additional Images Row: Measure Profile Analysis, Align, and Tip Images -->
    <v-row dense class="mb-3">
      <v-col cols="12">
        <AdditionalAnalysisImages :filename="filename" />
      </v-col>
    </v-row>

    <!-- Second row: Two-column layout for detailed data and heat map -->
    <v-row dense>
      <!-- Column 1: Detailed Data (Half Width) -->
      <v-col cols="12" lg="6">
        <MeasurementPoints :detailed-data="detailedData" :loading="isLoadingProfile" :filename="filename"
          :measurement-points="measurementPoints"
          :selected-point="String(selectedPoint?.value || selectedPoint || '')" @point-selected="handlePointSelected"
          @point-data-loaded="handlePointDataLoaded" @simple-point-selected="selectPoint" />
      </v-col>

      <!-- Column 2: Scatter Chart, Heat Map and Charts -->
      <v-col cols="12" lg="6">
        <!-- Data Scatter Chart -->
        <v-card class="scatter-chart-card mb-3" elevation="2" height="520">
          <v-card-title class="bg-info text-white py-2 text-subtitle-1">
            <v-icon start size="small">mdi-chart-scatter-plot</v-icon>
            Data Scatter Chart
            <v-spacer />
            <v-chip v-if="detailedData && detailedData.length > 0" size="x-small" color="white" variant="outlined">
              {{ detailedData.length.toLocaleString() }} points available
            </v-chip>
          </v-card-title>
          <v-card-text class="pa-3">
            <div v-if="!detailedData || detailedData.length === 0" class="text-center pa-6 text-medium-emphasis" style="height: 460px; display: flex; align-items: center; justify-content: center; flex-direction: column;">
              <v-icon size="64" color="grey" class="mb-3">mdi-chart-scatter-plot</v-icon>
              <div class="text-h6 mb-2">No Detailed Data Available</div>
              <div class="text-body-2">Scatter chart will appear here when detailed data is loaded</div>
            </div>
            <div v-else style="height: 460px;">
              <!-- Data Selector (compact) -->
              <div class="mb-3">
                <ScatterDataSelector 
                  :detailed-data="detailedData" 
                  @chart-config-changed="handleScatterChartConfigChanged"
                />
              </div>
              
              <!-- Scatter Chart -->
              <div style="height: 300px;">
                <DataScatterChart 
                  :chart-config="scatterChartConfig"
                  :chart-height="300"
                />
              </div>
            </div>
          </v-card-text>
        </v-card>

        <!-- Heat Map aligned with Details -->
        <v-card class="heat-map-card mb-3" elevation="2" height="480">
          <v-card-title class="bg-primary text-white py-2 text-subtitle-1">
            <v-icon start size="small">mdi-grid</v-icon>
            Wafer Heat Map
            <v-spacer />
            <v-progress-circular v-if="isLoadingWafer" indeterminate size="16" width="2" color="white" />
          </v-card-title>
          <v-card-text class="pa-3">
            <div v-if="!isLoadingWafer && (!waferData || waferData.length === 0)" class="text-center pa-6 text-medium-emphasis" style="height: 420px; display: flex; align-items: center; justify-content: center; flex-direction: column;">
              <v-icon size="64" color="grey" class="mb-3">mdi-grid</v-icon>
              <div class="text-h6 mb-2">No Wafer Data Available</div>
              <div class="text-body-2">Heat map data will appear here when available</div>
            </div>
            <HeatmapChart v-else :profile-data="waferData" :chart-height="420" :clickable="true"
              :selected-point="selectedPoint?.value || selectedPoint"
              @point-selected="handleWaferPointSelected" />
          </v-card-text>
        </v-card>
        
        <!-- Profile Image below Heat Map -->
        <v-card class="profile-card mb-3" elevation="2" height="500">
          <v-card-title class="bg-primary text-white py-2 text-subtitle-1">
            <v-icon start size="small">mdi-image</v-icon>
            Profile Image
            <v-spacer />
            <v-btn 
              v-if="profileImageUrl && (selectedPoint?.value || selectedPoint)"
              @click="downloadRawImage" 
              :loading="isDownloadingImage"
              size="x-small" 
              variant="text" 
              color="white"
              class="mr-2">
              <v-icon start size="small">mdi-download</v-icon>
              Download Raw
            </v-btn>
            <v-chip v-if="selectedPoint?.value || selectedPoint" size="x-small" color="white"
              variant="outlined">
              Point {{ selectedPoint?.value || selectedPoint }}
            </v-chip>
          </v-card-title>
          <v-card-text class="pa-3">
            <div v-if="isLoadingProfileImage" class="text-center pa-4" style="height: 430px; display: flex; align-items: center; justify-content: center; flex-direction: column;">
              <v-progress-circular indeterminate color="primary" size="small" />
              <p class="mt-2 text-caption">Loading profile image...</p>
            </div>
            <div v-else-if="profileImageUrl" class="profile-image-container"
              style="height: 430px; display: flex; align-items: center; justify-content: center;">
              <img :src="profileImageUrl" alt="Profile Image" class="profile-image"
                style="max-height: 100%; max-width: 100%; object-fit: contain;" @error="handleImageError"
                @load="handleImageLoad" />
            </div>
            <div v-else class="text-center pa-6 text-medium-emphasis" style="height: 430px; display: flex; align-items: center; justify-content: center; flex-direction: column;">
              <v-icon size="64" color="grey" class="mb-3">mdi-image-off</v-icon>
              <div class="text-h6 mb-2">No Profile Image Available</div>
              <div class="text-body-2">Profile image will appear here when available</div>
            </div>
          </v-card-text>
        </v-card>
        
        <!-- Z-Value Distribution below Profile Image -->
        <v-card class="distribution-card" elevation="2" height="500">
          <v-card-title class="bg-primary text-white py-2 text-subtitle-1">
            <v-icon start size="small">mdi-chart-bar</v-icon>
            Z-Value Distribution
            <v-spacer />
            <v-chip v-if="profileData.length > 0" size="x-small" color="white" variant="outlined">
              {{ profileData.length.toLocaleString() }} points
            </v-chip>
          </v-card-title>
          <v-card-text class="pa-3">
            <div v-if="isLoadingProfile" class="text-center pa-4" style="height: 430px; display: flex; align-items: center; justify-content: center; flex-direction: column;">
              <v-progress-circular indeterminate color="primary" size="small" />
              <p class="mt-2 text-caption">Loading...</p>
            </div>
            <div v-else-if="!profileData || profileData.length === 0" class="text-center pa-6 text-medium-emphasis" style="height: 430px; display: flex; align-items: center; justify-content: center; flex-direction: column;">
              <v-icon size="64" color="grey" class="mb-3">mdi-chart-bar</v-icon>
              <div class="text-h6 mb-2">No Z-Value Data Available</div>
              <div class="text-body-2">Distribution chart will appear here when data is available</div>
            </div>
            <HistogramChart v-else :profile-data="profileData" :chart-height="430" :compact="false" />
          </v-card-text>
        </v-card>
      </v-col>

    </v-row>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useResultPageData } from '@/composables/useResultPageQueries.js'
import { usePointSelection } from '@/composables/usePointSelection.js'
import { useDataDownload } from '@/composables/useDataDownload.js'

// Import components
import MeasurementInfo from '@/components/ResultPage/MeasurementInfo.vue'
import HistogramChart from '@/components/ResultPage/charts/HistogramChart.vue'
import StatisticalInfoByPoints from '@/components/ResultPage/StatisticalInfoByPoints.vue'
import MeasurementPoints from '@/components/ResultPage/MeasurementPoints.vue'
import HeatmapChart from '@/components/ResultPage/charts/HeatmapChart.vue'
import ScatterDataSelector from '@/components/ResultPage/charts/ScatterDataSelector.vue'
import DataScatterChart from '@/components/ResultPage/charts/DataScatterChart.vue'
import AdditionalAnalysisImages from '@/components/ResultPage/AdditionalAnalysisImages.vue'
import BreadcrumbNav from '@/components/common/BreadcrumbNav.vue'

const route = useRoute()
const router = useRouter()

// Navigation tracking
const referrer = ref('')

// Computed breadcrumb items
const breadcrumbItems = computed(() => {
  const items = []
  
  if (referrer.value === 'data-trend') {
    items.push({
      title: 'Data Trend',
      to: '/result/data_trend'
    })
  }
  
  items.push({
    title: filename.value ? 
      (filename.value.length > 30 ? filename.value.substring(0, 30) + '...' : filename.value) : 
      'Result',
    disabled: true
  })
  
  return items
})

// Basic route data
const filename = ref(decodeURIComponent(route.params.filename || ''))
const toolName = ref(route.query.tool || 'MAP608')
const selectedStatistic = ref(null)
const isDownloadingImage = ref(false)

// Scatter chart data
const scatterChartConfig = ref(null)

// Point selection logic
const pointSelection = usePointSelection()
const { selectedPoint, selectPoint, handlePointSelected, handleWaferPointSelected, handlePointDataLoaded } = pointSelection

// Vue Query data fetching
const {
  measurementInfo,
  summaryData,
  detailedData,
  measurementPoints,
  profileData,
  profileImageUrl,
  waferData,
  isLoadingProfile,
  isLoadingProfileImage,
  isLoadingWafer,
  hasData
} = useResultPageData(filename.value, selectedPoint, toolName.value)

// Download functionality
const downloadFunctions = useDataDownload(
  measurementInfo,
  summaryData,
  detailedData,
  profileData,
  computed(() => selectedPoint.value?.value || selectedPoint.value)
)

const {
  downloadMeasurementInfo,
  downloadSummaryStatistics,
  downloadDetailedData,
  downloadProfileData,
  downloadAllData
} = downloadFunctions


// Handler for statistical row clicks
function handleStatisticRowClick(rowItem) {
  selectedStatistic.value = rowItem.ITEM
}

// Handler for statistic selection
function handleStatisticSelected(statisticName) {
  selectedStatistic.value = statisticName
}

// Handler for scatter chart configuration changes
function handleScatterChartConfigChanged(config) {
  scatterChartConfig.value = config
}


// Image handling functions
function handleImageError(event) {
  console.warn('Profile image failed to load:', event)
}

function handleImageLoad(event) {
  // Profile image loaded successfully
}

function goBack() {
  // Use browser's back navigation to respect history
  router.back()
}

// Download raw image function
async function downloadRawImage() {
  if (!filename.value || !(selectedPoint.value?.value || selectedPoint.value)) {
    return
  }
  
  isDownloadingImage.value = true
  try {
    const pointId = selectedPoint.value?.value || selectedPoint.value
    const response = await fetch(
      `/api/afm-files/download-raw-image/${encodeURIComponent(filename.value)}/${pointId}?tool=${toolName.value}`,
      {
        method: 'GET',
        headers: {
          'Accept': 'image/tiff, image/webp, */*'
        }
      }
    )
    
    if (!response.ok) {
      throw new Error(`Failed to download image: ${response.statusText}`)
    }
    
    // Get filename from Content-Disposition header or create one
    const contentDisposition = response.headers.get('Content-Disposition')
    let downloadFilename = `${filename.value}_point_${pointId}.tiff`
    
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="?(.+)"?/i)
      if (filenameMatch) {
        downloadFilename = filenameMatch[1]
      }
    }
    
    // Convert response to blob and download
    const blob = await response.blob()
    const url = window.URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = downloadFilename
    document.body.appendChild(a)
    a.click()
    window.URL.revokeObjectURL(url)
    document.body.removeChild(a)
    
  } catch (error) {
    console.error('Error downloading raw image:', error)
    alert('Failed to download raw image. Please try again.')
  } finally {
    isDownloadingImage.value = false
  }
}


// Lifecycle
onMounted(() => {
  // Check if we have a referrer in the route query
  if (route.query.from) {
    referrer.value = route.query.from
  }
})

// Auto-select first point when measurement points are loaded
watch(measurementPoints, (newPoints) => {
  if (newPoints && newPoints.length > 0 && !selectedPoint.value) {
    console.log(`📍 Auto-selecting first point: ${newPoints[0].point}`)
    selectPoint(newPoints[0].point)
  }
}, { immediate: true })
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

/* Professional layout */
.scatter-chart-card .v-card-text,
.heat-map-card .v-card-text,
.profile-card .v-card-text,
.distribution-card .v-card-text {
  padding: 12px;
  height: calc(100% - 48px);
  overflow: hidden;
}

/* Responsive adjustments */
@media (max-width: 1280px) {
  .main-content-row {
    height: auto;
  }

  .heat-map-card {
    margin-bottom: 16px;
  }
}

/* Card spacing */
.v-card {
  margin-bottom: 12px;
}


/* Profile image styles */
.profile-image-container {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.profile-image {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
  border-radius: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  transition: transform 0.2s ease;
}

.profile-image:hover {
  transform: scale(1.02);
}


/* Equal height row styling */
.equal-height-row {
  min-height: 750px;
}

.equal-height-row>.v-col {
  display: flex;
}

/* Fixed height containers for first row - both use same class now */
.info-scatter-container {
  min-height: 750px;
  height: 750px;
  position: relative;
  display: flex;
  flex-direction: column;
}

/* Ensure child components fill the container */
.info-scatter-container>* {
  height: 100%;
  flex: 1;
}

/* Make both cards consistent */
.info-scatter-container :deep(.v-card) {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.info-scatter-container :deep(.v-card-title) {
  flex-shrink: 0;
}

.info-scatter-container :deep(.v-card-text) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow-y: auto;
  overflow-x: hidden;
}

/* Special handling for scatter chart to ensure it fills space */
.info-scatter-container :deep(.v-row) {
  flex-shrink: 0;
}

/* Ensure the chart itself fills remaining space */
.info-scatter-container :deep(.v-card-text > div:last-child) {
  flex: 1;
  min-height: 0;
}

/* Custom scrollbar styling */
.info-scatter-container :deep(.v-card-text)::-webkit-scrollbar {
  width: 6px;
}

.info-scatter-container :deep(.v-card-text)::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

.info-scatter-container :deep(.v-card-text)::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

.info-scatter-container :deep(.v-card-text)::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* Prevent horizontal overflow in Column 2 */
.scatter-chart-card,
.heat-map-card,
.profile-card,
.distribution-card {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

.scatter-chart-card .v-card-text,
.heat-map-card .v-card-text,
.profile-card .v-card-text,
.distribution-card .v-card-text {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  overflow: hidden;
}

/* Ensure charts don't exceed container width */
.scatter-chart-card :deep(.echarts-container),
.heat-map-card :deep(.echarts),
.distribution-card :deep(.echarts) {
  max-width: 100% !important;
  width: 100% !important;
}

/* Since mobile/tablet views are not needed, removed responsive adjustments */
</style>
