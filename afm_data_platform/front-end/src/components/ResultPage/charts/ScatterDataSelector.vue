<template>
  <v-card elevation="2" class="selector-card">
    <v-card-title class="bg-secondary text-white py-2 text-subtitle-1">
      <v-icon start size="small">mdi-chart-scatter-plot</v-icon>
      Scatter Chart Data Selector
      <v-spacer />
      <v-btn
        v-if="hasValidSelections"
        @click="generateChart"
        size="small"
        variant="elevated"
        color="primary"
        class="ml-2"
      >
        <v-icon start size="small">mdi-chart-line</v-icon>
        Generate Chart
      </v-btn>
    </v-card-title>

    <v-card-text class="pa-3">
      <v-row>
        <!-- X-Axis Selection -->
        <v-col cols="12" sm="4">
          <v-select
            v-model="selectedXColumn"
            :items="availableColumns"
            label="X-Axis (Slot ID, Points, Parameter)"
            density="compact"
            variant="outlined"
            clearable
            placeholder="Select X-Axis column"
            item-title="title"
            item-value="key"
          >
            <template v-slot:item="{ props, item }">
              <v-list-item v-bind="props">
                <template v-slot:prepend>
                  <v-icon size="small" color="primary">
                    {{ getColumnIcon(item.raw.key) }}
                  </v-icon>
                </template>
                <v-list-item-title>{{ item.raw.title }}</v-list-item-title>
                <v-list-item-subtitle>{{ getColumnType(item.raw.key) }}</v-list-item-subtitle>
              </v-list-item>
            </template>
          </v-select>
        </v-col>

        <!-- Y-Axis Selection -->
        <v-col cols="12" sm="4">
          <v-select
            v-model="selectedYColumn"
            :items="availableColumns"
            label="Y-Axis (Slot ID, Points, Parameter)"
            density="compact"
            variant="outlined"
            clearable
            placeholder="Select Y-Axis column"
            item-title="title"
            item-value="key"
          >
            <template v-slot:item="{ props, item }">
              <v-list-item v-bind="props">
                <template v-slot:prepend>
                  <v-icon size="small" color="success">
                    {{ getColumnIcon(item.raw.key) }}
                  </v-icon>
                </template>
                <v-list-item-title>{{ item.raw.title }}</v-list-item-title>
                <v-list-item-subtitle>{{ getColumnType(item.raw.key) }}</v-list-item-subtitle>
              </v-list-item>
            </template>
          </v-select>
        </v-col>

        <!-- Color By Selection (Optional) -->
        <v-col cols="12" sm="4">
          <v-select
            v-model="selectedColorColumn"
            :items="categoricalColumns"
            label="Color By (Optional)"
            density="compact"
            variant="outlined"
            clearable
            placeholder="Select grouping column"
            item-title="title"
            item-value="key"
          >
            <template v-slot:item="{ props, item }">
              <v-list-item v-bind="props">
                <template v-slot:prepend>
                  <v-icon size="small" color="warning">
                    {{ getColumnIcon(item.raw.key) }}
                  </v-icon>
                </template>
                <v-list-item-title>{{ item.raw.title }}</v-list-item-title>
                <v-list-item-subtitle>{{ getColumnType(item.raw.key) }}</v-list-item-subtitle>
              </v-list-item>
            </template>
          </v-select>
        </v-col>
      </v-row>

      <!-- Data Preview -->
      <v-row v-if="hasValidSelections" class="mt-2">
        <v-col cols="12">
          <v-card variant="outlined" class="preview-card">
            <v-card-text class="pa-2">
              <div class="d-flex align-center mb-2">
                <v-icon size="small" color="info" class="mr-2">mdi-eye</v-icon>
                <span class="text-caption font-weight-medium">Data Preview</span>
                <v-spacer />
                <v-chip size="x-small" color="info" variant="tonal">
                  {{ chartData.length }} points
                </v-chip>
              </div>
              
              <v-row dense>
                <v-col cols="4">
                  <v-chip size="x-small" color="primary" variant="outlined" class="mb-1">
                    X: {{ getColumnTitle(selectedXColumn) }}
                  </v-chip>
                  <div class="text-caption text-medium-emphasis">
                    {{ getDataRange(chartData, selectedXColumn) }}
                  </div>
                </v-col>
                <v-col cols="4">
                  <v-chip size="x-small" color="success" variant="outlined" class="mb-1">
                    Y: {{ getColumnTitle(selectedYColumn) }}
                  </v-chip>
                  <div class="text-caption text-medium-emphasis">
                    {{ getDataRange(chartData, selectedYColumn) }}
                  </div>
                </v-col>
                <v-col cols="4" v-if="selectedColorColumn">
                  <v-chip size="x-small" color="warning" variant="outlined" class="mb-1">
                    Color: {{ getColumnTitle(selectedColorColumn) }}
                  </v-chip>
                  <div class="text-caption text-medium-emphasis">
                    {{ getUniqueValues(chartData, selectedColorColumn) }}
                  </div>
                </v-col>
              </v-row>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>

      <!-- Selection Status -->
      <v-row class="mt-2">
        <v-col cols="12">
          <div class="d-flex align-center">
            <v-icon 
              :color="hasValidSelections ? 'success' : 'warning'" 
              size="small" 
              class="mr-2"
            >
              {{ hasValidSelections ? 'mdi-check-circle' : 'mdi-alert-circle' }}
            </v-icon>
            <span class="text-caption">
              {{ hasValidSelections 
                ? 'Ready to generate scatter chart' 
                : 'Please select both X and Y axis columns' 
              }}
            </span>
          </div>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  detailedData: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['chart-config-changed'])

// Reactive data
const selectedXColumn = ref(null)
const selectedYColumn = ref(null)
const selectedColorColumn = ref(null)

// Computed properties
const availableColumns = computed(() => {
  if (!props.detailedData || props.detailedData.length === 0) return []
  
  const sampleItem = props.detailedData[0]
  const columns = []
  
  // Get all columns from the data
  Object.keys(sampleItem).forEach(key => {
    if (key === 'index') return // Skip index column
    
    const title = formatColumnTitle(key)
    columns.push({
      key: key,
      title: title,
      type: getDataType(sampleItem[key])
    })
  })
  
  // Sort columns: numeric columns first, then categorical
  return columns.sort((a, b) => {
    if (a.type === 'number' && b.type !== 'number') return -1
    if (a.type !== 'number' && b.type === 'number') return 1
    return a.title.localeCompare(b.title)
  })
})

const categoricalColumns = computed(() => {
  return availableColumns.value.filter(col => 
    col.type === 'string' || 
    col.key.includes('ID') || 
    col.key.includes('Point') ||
    col.key === 'measurement_point' ||
    col.key === 'Valid'
  )
})

const hasValidSelections = computed(() => {
  return selectedXColumn.value && selectedYColumn.value
})

const chartData = computed(() => {
  if (!hasValidSelections.value || !props.detailedData) return []
  
  return props.detailedData
    .filter(item => {
      // Filter out rows with null/undefined values for selected columns
      const xValue = item[selectedXColumn.value]
      const yValue = item[selectedYColumn.value]
      return xValue != null && yValue != null && xValue !== '' && yValue !== ''
    })
    .map(item => ({
      x: item[selectedXColumn.value],
      y: item[selectedYColumn.value],
      color: selectedColorColumn.value ? item[selectedColorColumn.value] : 'Default',
      raw: item
    }))
})

// Methods
function formatColumnTitle(key) {
  return key
    .replace(/_/g, ' ')
    .replace(/([A-Z])/g, ' $1')
    .trim()
    .replace(/\b\w/g, l => l.toUpperCase())
}

function getDataType(value) {
  if (typeof value === 'number') return 'number'
  if (typeof value === 'boolean') return 'boolean'
  return 'string'
}

function getColumnIcon(key) {
  if (key.includes('ID') || key.includes('Point') || key === 'measurement_point') {
    return 'mdi-identifier'
  }
  if (key.includes('X') || key.includes('Y')) {
    return 'mdi-map-marker'
  }
  if (key.includes('nm') || key.includes('height') || key.includes('Roughness')) {
    return 'mdi-ruler'
  }
  if (key === 'Valid') {
    return 'mdi-check-circle'
  }
  return 'mdi-table-column'
}

function getColumnType(key) {
  if (!props.detailedData || props.detailedData.length === 0) return 'unknown'
  const value = props.detailedData[0][key]
  return getDataType(value)
}

function getColumnTitle(columnKey) {
  const column = availableColumns.value.find(col => col.key === columnKey)
  return column ? column.title : columnKey
}

function getDataRange(data, columnKey) {
  if (!data || data.length === 0) return 'No data'
  
  const values = data.map(item => item.raw[columnKey]).filter(v => v != null)
  if (values.length === 0) return 'No valid values'
  
  const firstValue = values[0]
  if (typeof firstValue === 'number') {
    const min = Math.min(...values)
    const max = Math.max(...values)
    return `${min.toFixed(2)} - ${max.toFixed(2)}`
  }
  
  return `${values.length} values`
}

function getUniqueValues(data, columnKey) {
  if (!data || data.length === 0) return 'No data'
  
  const values = data.map(item => item.raw[columnKey]).filter(v => v != null)
  const unique = [...new Set(values)]
  
  if (unique.length <= 3) {
    return unique.join(', ')
  }
  
  return `${unique.length} categories`
}

function generateChart() {
  if (!hasValidSelections.value) return
  
  const config = {
    xColumn: selectedXColumn.value,
    yColumn: selectedYColumn.value,
    colorColumn: selectedColorColumn.value,
    xTitle: getColumnTitle(selectedXColumn.value),
    yTitle: getColumnTitle(selectedYColumn.value),
    colorTitle: selectedColorColumn.value ? getColumnTitle(selectedColorColumn.value) : null,
    data: chartData.value
  }
  
  emit('chart-config-changed', config)
}

// Watch for selection changes and auto-generate chart
watch([selectedXColumn, selectedYColumn, selectedColorColumn], () => {
  if (hasValidSelections.value) {
    generateChart()
  } else {
    emit('chart-config-changed', null)
  }
}, { deep: true })

// Auto-select some sensible defaults when data is loaded
watch(() => props.detailedData, (newData) => {
  if (newData && newData.length > 0 && availableColumns.value.length > 0) {
    // Auto-select first numeric column for Y if none selected
    if (!selectedYColumn.value) {
      const numericColumn = availableColumns.value.find(col => col.type === 'number')
      if (numericColumn) {
        selectedYColumn.value = numericColumn.key
      }
    }
    
    // Auto-select Point or Site ID for X if none selected
    if (!selectedXColumn.value) {
      const pointColumn = availableColumns.value.find(col => 
        col.key.includes('Point') || col.key.includes('Site_ID') || col.key === 'measurement_point'
      )
      if (pointColumn) {
        selectedXColumn.value = pointColumn.key
      }
    }
  }
}, { immediate: true })
</script>

<style scoped>
.selector-card {
  border-radius: 8px;
}

.preview-card {
  background-color: rgba(var(--v-theme-surface), 0.5);
  border-radius: 6px;
}

.v-chip {
  font-size: 0.75rem;
}

.text-caption {
  font-size: 0.7rem;
}

/* Custom scrollbar for long lists */
:deep(.v-list) {
  max-height: 200px;
  overflow-y: auto;
}

:deep(.v-list)::-webkit-scrollbar {
  width: 6px;
}

:deep(.v-list)::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 3px;
}

:deep(.v-list)::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 3px;
}

:deep(.v-list)::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}
</style>