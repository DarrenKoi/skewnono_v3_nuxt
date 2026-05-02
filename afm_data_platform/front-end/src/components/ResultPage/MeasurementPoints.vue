<template>
  <div>
    <!-- Display detailed data when available -->
    <div v-if="detailedData && detailedData.length > 0">
      <!-- Main card without tabs -->
      <v-card elevation="2">
        <v-card-title class="bg-primary text-white py-2 text-subtitle-1">
          <v-icon start size="small">mdi-dots-grid</v-icon>
          Details
          <v-spacer />
          <v-chip 
            color="white" 
            variant="outlined"
            size="small"
            class="text-primary"
          >
            <v-icon start size="small">mdi-table-row</v-icon>
            {{ filteredData.length.toLocaleString() }} rows
          </v-chip>
        </v-card-title>
        
        <!-- Controls and filters -->
        <v-card-text class="pa-3 border-b">
          <v-row align="center">
            <v-col cols="12" sm="6">
              <v-text-field
                v-model="searchFilter"
                label="Search in data"
                density="compact"
                variant="outlined"
                prepend-inner-icon="mdi-magnify"
                clearable
                placeholder="Search by Site ID, Point No, etc."
              />
            </v-col>
            
            <v-col cols="12" sm="6">
              <v-select
                v-model="selectedMeasurementPoint"
                :items="availableMeasurementPoints"
                label="Select Measurement Point"
                density="compact"
                variant="outlined"
                clearable
                placeholder="All Points"
              />
            </v-col>
          </v-row>
          
          <!-- Column selector -->
          <v-row class="mt-2">
            <v-col cols="12">
              <div class="text-subtitle-2 mb-2">Select Columns to Display:</div>
              <v-chip-group
                v-model="selectedColumns"
                multiple
                column
              >
                <v-chip
                  v-for="header in allAvailableHeaders"
                  :key="header.key"
                  :value="header.key"
                  size="small"
                  variant="outlined"
                  filter
                >
                  {{ header.title }}
                </v-chip>
              </v-chip-group>
            </v-col>
          </v-row>
        </v-card-text>
        
        <!-- Data Table (no tabs) -->
        <div class="d-flex justify-space-between align-center pa-3 bg-info text-white">
          <div class="d-flex align-center">
            <v-icon start>mdi-table</v-icon>
            <span v-if="selectedMeasurementPoint">
              Point {{ selectedMeasurementPoint }} - Detailed Data
            </span>
            <span v-else>
              All Measurement Points - Detailed Data
            </span>
          </div>
          <v-btn
            v-if="filteredData.length > 0"
            icon="mdi-download"
            variant="text"
            color="white"
            @click="exportData"
            title="Export to CSV"
          />
        </div>
    
        <v-card-text class="pa-0">
          <v-data-table
            v-model:page="currentPage"
            :headers="visibleHeaders"
            :items="filteredData"
            :items-per-page="itemsPerPage"
            :loading="loading"
            density="compact"
            class="measurement-points-table"
            hover
            show-current-page
            :height="400"
            fixed-header
          >
            <!-- Custom template for measurement point column -->
            <template v-slot:item.measurement_point="{ item }">
              <v-chip
                size="small"
                :color="getPointColor(item.measurement_point)"
                variant="outlined"
                class="font-weight-medium"
              >
                {{ item.measurement_point }}
              </v-chip>
            </template>

            <!-- Custom template for Point No column -->
            <template v-slot:item.Point_No="{ item }">
              <span class="font-weight-bold text-primary">
                {{ item['Point No'] || item.Point_No || 'N/A' }}
              </span>
            </template>

            <!-- Custom template for coordinate columns -->
            <template v-slot:item.X_um="{ item }">
              <span class="font-mono">{{ formatCoordinate(item['X (um)'] || item.X_um) }}</span>
            </template>
            
            <template v-slot:item.Y_um="{ item }">
              <span class="font-mono">{{ formatCoordinate(item['Y (um)'] || item.Y_um) }}</span>
            </template>

            <!-- Custom template for Site coordinates -->
            <template v-slot:item.Site_X="{ item }">
              <span class="font-mono">{{ formatCoordinate(item['Site X'] || item.Site_X) }}</span>
            </template>
            
            <template v-slot:item.Site_Y="{ item }">
              <span class="font-mono">{{ formatCoordinate(item['Site Y'] || item.Site_Y) }}</span>
            </template>

            <!-- Custom template for numeric values -->
            <template v-slot:item.Roughness_R="{ item }">
              <span class="font-mono">{{ formatNumericValue(item.Roughness_R || item['Roughness_R']) }}</span>
            </template>

            <template v-slot:item.pickup_count="{ item }">
              <span class="font-mono">{{ formatInteger(item.pickup_count) }}</span>
            </template>

            <template v-slot:item.Mileage="{ item }">
              <span class="font-mono">{{ formatNumericValue(item.Mileage) }}</span>
            </template>

            <!-- Custom template for Valid column -->
            <template v-slot:item.Valid="{ item }">
              <v-chip
                size="x-small"
                :color="item.Valid ? 'success' : 'error'"
                :variant="item.Valid ? 'elevated' : 'outlined'"
              >
                {{ item.Valid ? 'Valid' : 'Invalid' }}
              </v-chip>
            </template>

            <!-- Custom template for Methods ID -->
            <template v-slot:item.Methods_ID="{ item }">
              <v-chip
                size="x-small"
                color="secondary"
                variant="outlined"
              >
                {{ item['Methods ID'] || item.Methods_ID || 'N/A' }}
              </v-chip>
            </template>

        <!-- Loading template -->
        <template v-slot:loading>
          <v-skeleton-loader type="table-row@10" />
        </template>

        <!-- No data template -->
        <template v-slot:no-data>
          <v-empty-state
            icon="mdi-table-off"
            title="No measurement data found"
            text="No detailed measurement points match your current filters"
          />
        </template>
          </v-data-table>
        </v-card-text>
      </v-card>

      <!-- Summary information -->
      <v-card elevation="1" class="mt-4" variant="outlined">
        <v-card-text class="pa-3">
          <v-row>
            <v-col cols="12" sm="6" md="3">
              <v-alert density="compact" variant="tonal" color="primary">
                <div class="text-caption">Total Points</div>
                <div class="text-h6">{{ detailedData.length.toLocaleString() }}</div>
              </v-alert>
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-alert density="compact" variant="tonal" color="info">
                <div class="text-caption">Measurement Points</div>
                <div class="text-h6">{{ availableMeasurementPoints.length }}</div>
              </v-alert>
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-alert density="compact" variant="tonal" color="success">
                <div class="text-caption">Valid Points</div>
                <div class="text-h6">{{ validPointsCount.toLocaleString() }}</div>
              </v-alert>
            </v-col>
            <v-col cols="12" sm="6" md="3">
              <v-alert density="compact" variant="tonal" color="warning">
                <div class="text-caption">Data Columns</div>
                <div class="text-h6">{{ tableHeaders.length - 1 }}</div>
              </v-alert>
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>
    </div>
    
    <!-- No data message -->
    <div v-else class="text-center pa-6 text-medium-emphasis">
      <v-card elevation="2" style="min-height: 600px;">
        <v-card-title class="bg-primary text-white py-2 text-subtitle-1">
          <v-icon start size="small">mdi-dots-grid</v-icon>
          Details
        </v-card-title>
        <v-card-text class="pa-6" style="min-height: 550px; display: flex; align-items: center; justify-content: center; flex-direction: column;">
          <v-icon size="64" class="mb-3">mdi-dots-grid</v-icon>
          <div class="text-h6 mb-2">No Detailed Measurement Data Available</div>
          <div class="text-body-2">Load measurement data to view detailed point-by-point measurements</div>
        </v-card-text>
      </v-card>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  detailedData: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    default: false
  },
  filename: {
    type: String,
    default: ''
  },
  measurementPoints: {
    type: Array,
    default: () => []
  },
  selectedPoint: {
    type: String,
    default: null
  }
})

// Emits
const emit = defineEmits(['point-selected', 'point-data-loaded', 'simple-point-selected'])

// Reactive data
const selectedMeasurementPoint = ref(null)
const searchFilter = ref('')
const currentPage = ref(1)
const itemsPerPage = ref(25)
const selectedChipIndex = ref(0)
const selectedColumns = ref([])

// Computed properties
const availableMeasurementPoints = computed(() => {
  if (!props.detailedData || props.detailedData.length === 0) return []
  
  const points = new Set()
  props.detailedData.forEach(item => {
    if (item.measurement_point) {
      points.add(item.measurement_point)
    }
  })
  
  return Array.from(points).sort()
})

const filteredData = computed(() => {
  let filtered = props.detailedData || []
  
  // Filter by selected measurement point
  if (selectedMeasurementPoint.value) {
    filtered = filtered.filter(item => 
      item.measurement_point === selectedMeasurementPoint.value
    )
  }
  
  // Filter by search text
  if (searchFilter.value && searchFilter.value.trim()) {
    const searchTerm = searchFilter.value.toLowerCase().trim()
    filtered = filtered.filter(item => {
      // Search in key fields
      const searchableText = [
        item['Site ID'],
        item.Site_ID,
        item['Point No'],
        item.Point_No,
        item['Methods ID'],
        item.Methods_ID,
        item.measurement_point,
        item.statd
      ].filter(val => val != null)
       .join(' ')
       .toLowerCase()
      
      return searchableText.includes(searchTerm)
    })
  }
  
  return filtered
})

const validPointsCount = computed(() => {
  if (!props.detailedData) return 0
  return props.detailedData.filter(item => item.Valid === true || item.Valid === 1).length
})

// Compute all available headers with priority order
const allAvailableHeaders = computed(() => {
  if (!props.detailedData || props.detailedData.length === 0) {
    return []
  }
  
  const sampleItem = props.detailedData[0]
  const headers = []
  
  // Define preferred columns in the exact order requested
  const preferredColumns = [
    { key: 'Site', title: 'Site', priority: 0, altKeys: ['Site'] },
    { key: 'Site_ID', title: 'Site ID', priority: 1, altKeys: ['Site ID'] },
    { key: 'Site_X', title: 'Site X', priority: 2, altKeys: ['Site X'] },
    { key: 'Site_Y', title: 'Site Y', priority: 3, altKeys: ['Site Y'] },
    { key: 'X_um', title: 'X', priority: 4, altKeys: ['X (um)', 'X'] },
    { key: 'Y_um', title: 'Y', priority: 5, altKeys: ['Y (um)', 'Y'] },
    { key: 'Point_No', title: 'Point', priority: 6, altKeys: ['Point No', 'Point', 'measurement_point'] }
  ]
  
  // Add preferred columns that exist in data
  preferredColumns.forEach(col => {
    let actualKey = col.key
    let found = false
    
    // Check if the primary key exists
    if (sampleItem.hasOwnProperty(col.key)) {
      found = true
    } else if (col.altKeys) {
      // Check alternative keys
      for (const altKey of col.altKeys) {
        if (sampleItem.hasOwnProperty(altKey)) {
          actualKey = altKey
          found = true
          break
        }
      }
    }
    
    if (found) {
      headers.push({
        title: col.title,
        key: actualKey,
        align: col.key.includes('ID') || col.key.includes('Point') ? 'center' : 
               (typeof sampleItem[actualKey] === 'number' ? 'end' : 'start'),
        sortable: true,
        width: col.key.includes('Point') ? '100px' : '120px',
        priority: col.priority
      })
    }
  })
  
  // Get remaining columns and categorize them
  const remainingColumns = []
  const nmColumns = []
  
  Object.keys(sampleItem).forEach(key => {
    if (!headers.some(h => h.key === key) && key !== 'index') {
      const title = key.replace(/_/g, ' ').replace(/([A-Z])/g, ' $1').trim()
      const header = {
        title: title,
        key: key,
        align: typeof sampleItem[key] === 'number' ? 'end' : 'start',
        sortable: true,
        width: '120px'
      }
      
      // Check if column contains "(nm)" string
      if (title.includes('(nm)') || key.includes('nm') || key.toLowerCase().includes('height')) {
        nmColumns.push(header)
      } else {
        remainingColumns.push(header)
      }
    }
  })
  
  // Sort nm columns alphabetically
  nmColumns.sort((a, b) => a.title.localeCompare(b.title))
  
  // Sort remaining columns alphabetically
  remainingColumns.sort((a, b) => a.title.localeCompare(b.title))
  
  // Assign priorities: preferred (0-6), nm columns (10+), other columns (100+)
  nmColumns.forEach((col, index) => {
    col.priority = 10 + index
  })
  
  remainingColumns.forEach((col, index) => {
    col.priority = 100 + index
  })
  
  // Combine all headers and sort by priority
  const allHeaders = [...headers, ...nmColumns, ...remainingColumns]
  return allHeaders.sort((a, b) => (a.priority || 100) - (b.priority || 100))
})

// Get visible headers based on user selection
const visibleHeaders = computed(() => {
  if (selectedColumns.value.length === 0) {
    // Show all columns by default
    return allAvailableHeaders.value
  }
  
  return allAvailableHeaders.value.filter(h => selectedColumns.value.includes(h.key))
})

// Legacy computed for compatibility
const tableHeaders = computed(() => visibleHeaders.value)

// Methods
function formatCoordinate(value) {
  if (value == null || value === undefined || value === '') return 'N/A'
  if (typeof value === 'number') {
    return value.toFixed(2)
  }
  return value.toString()
}

function formatNumericValue(value) {
  if (value == null || value === undefined || value === '') return 'N/A'
  if (typeof value === 'number') {
    if (Math.abs(value) >= 1000) {
      return value.toFixed(1)
    } else if (Math.abs(value) >= 1) {
      return value.toFixed(3)
    } else {
      return value.toFixed(4)
    }
  }
  return value.toString()
}

function formatInteger(value) {
  if (value == null || value === undefined || value === '') return 'N/A'
  if (typeof value === 'number') {
    return Math.round(value).toLocaleString()
  }
  return value.toString()
}

function getPointColor(pointName) {
  if (!pointName) return 'grey'
  
  const colorMap = {
    '1_UL': 'primary',
    '2_UL': 'success', 
    '3_UL': 'warning',
    '4_UL': 'error',
    '5_UL': 'info',
    '1_LL': 'purple',
    '2_LL': 'orange',
    '3_LL': 'cyan',
    '4_LL': 'pink',
    '5_LL': 'indigo'
  }
  
  return colorMap[pointName] || 'secondary'
}

function exportData() {
  if (!filteredData.value || filteredData.value.length === 0) return
  
  // Create CSV content
  const headers = tableHeaders.value.map(h => h.title).join(',')
  const rows = filteredData.value.map(item => 
    tableHeaders.value.map(header => {
      const value = item[header.key]
      if (value == null || value === undefined) return ''
      return typeof value === 'string' && value.includes(',') ? `"${value}"` : value
    }).join(',')
  ).join('\n')
  
  const csvContent = headers + '\n' + rows
  
  // Download CSV
  const blob = new Blob([csvContent], { type: 'text/csv' })
  const url = window.URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `measurement_points_${selectedMeasurementPoint.value || 'all'}_${new Date().toISOString().split('T')[0]}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  window.URL.revokeObjectURL(url)
}

// Watch for measurement point selection changes
watch(selectedMeasurementPoint, (newPoint, oldPoint) => {
  if (newPoint && newPoint !== oldPoint) {
    console.log(`🎯 [MeasurementPoints] Selected Site ID changed to:`, newPoint)
    
    // Extract point number from Site ID (e.g., "1_UL" -> 1)
    const pointNumber = extractPointNumber(newPoint)
    
    // Find complete site information from detailed data
    const siteInfo = extractSiteInfo(newPoint)
    
    console.log(`📍 [MeasurementPoints] Complete site info extracted:`)
    console.log(`   Site ID: ${siteInfo.site_id}`)
    console.log(`   Site X: ${siteInfo.site_x}`)
    console.log(`   Site Y: ${siteInfo.site_y}`)
    console.log(`   Point No: ${siteInfo.point_no}`)
    
    // Emit point selection event with complete site information
    emit('point-selected', {
      measurementPoint: newPoint,      // Site ID (e.g., '1_UL')
      pointNumber: pointNumber,        // Point number (e.g., 1)
      filename: props.filename,
      siteInfo: siteInfo
    })
  }
})

// Load column preferences from localStorage
function loadColumnPreferences() {
  const saved = localStorage.getItem('measurementPointsColumns')
  if (saved) {
    try {
      const parsedColumns = JSON.parse(saved)
      if (Array.isArray(parsedColumns)) {
        selectedColumns.value = parsedColumns
        return true
      }
    } catch (e) {
      console.warn('Failed to parse column preferences from localStorage:', e)
    }
  }
  return false
}

// Save column preferences to localStorage
function saveColumnPreferences() {
  try {
    localStorage.setItem('measurementPointsColumns', JSON.stringify(selectedColumns.value))
  } catch (e) {
    console.warn('Failed to save column preferences to localStorage:', e)
  }
}

// Watch for column selection changes and save to localStorage
watch(selectedColumns, (newColumns) => {
  if (newColumns && newColumns.length > 0) {
    saveColumnPreferences()
  }
}, { deep: true })

// Watch for data changes and auto-select first measurement point
watch(() => props.detailedData, (newData) => {
  console.log(`🔍 [MeasurementPoints] Received detailed data:`)
  console.log(`🔍 [MeasurementPoints] Length:`, newData?.length || 0)
  
  if (newData && newData.length > 0) {
    console.log(`🔍 [MeasurementPoints] First record:`, newData[0])
    console.log(`🔍 [MeasurementPoints] Available measurement points:`, availableMeasurementPoints.value)
    
    // Don't auto-select first measurement point - wait for user interaction
    // This prevents unwanted API calls when the page loads
    if (!selectedMeasurementPoint.value && availableMeasurementPoints.value.length > 0) {
      console.log(`🔍 [MeasurementPoints] ${availableMeasurementPoints.value.length} points available, waiting for user selection`)
    }
    
    // Initialize selected columns - first try to load from localStorage, then show all by default
    if (selectedColumns.value.length === 0) {
      const loadedFromStorage = loadColumnPreferences()
      if (!loadedFromStorage) {
        // Show all columns by default
        selectedColumns.value = allAvailableHeaders.value.map(h => h.key)
      }
    }
    
    // Emit data loaded event
    emit('point-data-loaded', {
      totalPoints: newData.length,
      availablePoints: availableMeasurementPoints.value,
      filename: props.filename
    })
  }
}, { immediate: true })

// Helper function to extract point number from measurement point name
function extractPointNumber(measurementPoint) {
  if (!measurementPoint) return null
  
  // Extract first number from measurement point (e.g., "1_UL" -> "1", "2_LL" -> "2")
  const match = measurementPoint.match(/^(\d+)/)
  return match ? parseInt(match[1]) : null
}

// Helper function to extract complete site information from detailed data
function extractSiteInfo(measurementPoint) {
  console.log(`🔍 [MeasurementPoints] extractSiteInfo called with: "${measurementPoint}"`)
  console.log(`🔍 [MeasurementPoints] detailedData available:`, !!props.detailedData)
  console.log(`🔍 [MeasurementPoints] detailedData length:`, props.detailedData?.length || 0)
  
  if (!measurementPoint || !props.detailedData || !Array.isArray(props.detailedData)) {
    console.log(`⚠️ [MeasurementPoints] Using fallback (no detailed data) for: "${measurementPoint}"`)
    const fallbackResult = {
      site_id: measurementPoint,  // measurement point IS the Site ID (e.g., '1_UL')
      site_x: null,
      site_y: null,
      point_no: extractPointNumber(measurementPoint)
    }
    console.log(`⚠️ [MeasurementPoints] Fallback result:`, fallbackResult)
    return fallbackResult
  }
  
  console.log(`🔍 [MeasurementPoints] Searching in ${props.detailedData.length} records...`)
  console.log(`🔍 [MeasurementPoints] Sample record structure:`, props.detailedData[0])
  
  // Find the first record that matches this measurement point (Site ID)
  const record = props.detailedData.find(item => 
    item.measurement_point === measurementPoint ||
    item['Site ID'] === measurementPoint ||
    item.Site_ID === measurementPoint
  )
  
  if (record) {
    console.log(`✅ [MeasurementPoints] Found matching record:`, record)
    const result = {
      site_id: record['Site ID'] || record.Site_ID || measurementPoint,  // Site ID (e.g., '1_UL')
      site_x: record['Site X'] || record.Site_X || null,                 // Site X coordinate
      site_y: record['Site Y'] || record.Site_Y || null,                 // Site Y coordinate
      point_no: record['Point No'] || record.Point_No || extractPointNumber(measurementPoint)  // Point number (e.g., 1)
    }
    console.log(`✅ [MeasurementPoints] Extracted site info:`, result)
    return result
  }
  
  // Fallback: use measurement point as Site ID
  console.log(`⚠️ [MeasurementPoints] No matching record found, using fallback for: "${measurementPoint}"`)
  const fallbackResult = {
    site_id: measurementPoint,  // measurement point IS the Site ID
    site_x: null,
    site_y: null,
    point_no: extractPointNumber(measurementPoint)
  }
  console.log(`⚠️ [MeasurementPoints] Fallback result:`, fallbackResult)
  return fallbackResult
}

// Function to handle measurement point selection from buttons
function selectMeasurementPoint(pointName) {
  selectedMeasurementPoint.value = pointName
  emit('simple-point-selected', pointName)
}

// Watch for external selectedPoint changes to update chip selection
watch(() => props.selectedPoint, (newPoint) => {
  if (newPoint && props.measurementPoints) {
    const index = props.measurementPoints.findIndex(p => p.point === newPoint)
    if (index !== -1) {
      selectedChipIndex.value = index
      selectedMeasurementPoint.value = newPoint
    }
  }
}, { immediate: true })
</script>

<style scoped>
.measurement-points-table {
  border: none;
}

.measurement-points-table :deep(.v-data-table__tr:hover) {
  background-color: rgba(var(--v-theme-primary), 0.08);
}

.measurement-points-table :deep(.v-data-table-header) {
  background-color: rgba(var(--v-theme-surface), 0.8);
}

.measurement-points-table :deep(.v-data-table__th) {
  font-weight: 600;
  font-size: 0.875rem;
  padding: 8px 12px;
  border-bottom: 2px solid rgba(var(--v-theme-outline), 0.2);
}

.measurement-points-table :deep(.v-data-table__td) {
  padding: 8px 12px;
  font-size: 0.9rem;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.1);
}

.font-mono {
  font-family: 'Courier New', monospace;
  font-size: 0.9rem;
  font-weight: 500;
}

.v-chip {
  font-weight: 600;
}

/* Responsive adjustments */
@media (max-width: 960px) {
  .measurement-points-table :deep(.v-data-table__th),
  .measurement-points-table :deep(.v-data-table__td) {
    padding: 6px 8px;
    font-size: 0.8rem;
  }
  
  .font-mono {
    font-size: 0.8rem;
  }
}

/* Chip styles */
.v-chip {
  margin: 4px;
  transition: all 0.2s ease;
}

.v-chip:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.v-chip--selected {
  background-color: rgb(var(--v-theme-primary)) !important;
  color: white !important;
}

.border-b {
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.12);
}

.border-t {
  border-top: 1px solid rgba(var(--v-theme-outline), 0.12);
}
</style>