<template>
  <div>
    <!-- Dynamic grid layout for any number of key-value pairs -->
    <v-row v-if="informationEntries.length > 0">
      <v-col 
        v-for="(entry, index) in informationEntries" 
        :key="entry.key"
        :cols="getColumnSize(informationEntries.length)"
        :md="getMdColumnSize(informationEntries.length)"
      >
        <div class="info-item">
          <div class="info-label">{{ formatLabel(entry.key) }}</div>
          <div 
            class="info-value"
            :class="[getValueClass(entry.key, index), compact ? 'text-body-2' : 'text-h6']"
          >
            {{ formatValue(entry.value, entry.key) }}
          </div>
        </div>
      </v-col>
    </v-row>
    
    <!-- Fallback message when no data -->
    <div v-else class="text-center pa-6 text-medium-emphasis">
      <v-icon size="48" class="mb-3">mdi-information-outline</v-icon>
      <div class="text-h6 mb-2">No Measurement Information Available</div>
      <div class="text-body-2">Load measurement data to view detailed information</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

// Props
const props = defineProps({
  measurementInfo: {
    type: Object,
    default: () => ({})
  },
  compact: {
    type: Boolean,
    default: false
  }
})

// Computed property to convert measurementInfo object to array of entries
const informationEntries = computed(() => {
  if (!props.measurementInfo || typeof props.measurementInfo !== 'object') {
    return []
  }
  
  return Object.entries(props.measurementInfo)
    .filter(([key, value]) => value !== null && value !== undefined && value !== '')
    .map(([key, value]) => ({ key, value }))
})

// Functions
function formatLabel(key) {
  // Convert snake_case and camelCase to Title Case
  return key
    .replace(/[_-]/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .split(' ')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ')
}

function formatValue(value, key) {
  if (value === null || value === undefined) return 'N/A'
  
  // Special formatting for specific key types
  const lowerKey = key.toLowerCase()
  
  if (lowerKey.includes('time') || lowerKey.includes('date')) {
    try {
      return new Date(value).toLocaleString()
    } catch (error) {
      return value.toString()
    }
  }
  
  if (typeof value === 'number') {
    // Format numbers with appropriate precision
    if (Number.isInteger(value)) {
      return value.toLocaleString()
    } else {
      return value.toFixed(3)
    }
  }
  
  return value.toString()
}

function getColumnSize(totalItems) {
  // Responsive column sizing based on number of items
  if (totalItems <= 2) return 12
  if (totalItems <= 4) return 6
  if (totalItems <= 6) return 4
  return 3
}

function getMdColumnSize(totalItems) {
  // Medium screen column sizing
  if (totalItems <= 1) return 12
  if (totalItems <= 2) return 6
  if (totalItems <= 3) return 4
  if (totalItems <= 6) return 4
  return 3
}

function getValueClass(key, index) {
  // Assign different colors to values for visual distinction
  const colorClasses = [
    'text-primary',
    'text-success', 
    'text-info',
    'text-warning',
    'text-secondary',
    'text-purple'
  ]
  
  // Special colors for important keys - orange for Recipe ID, Lot ID, and Start Time
  const lowerKey = key.toLowerCase()
  if (lowerKey.includes('recipe')) return 'text-orange'
  if (lowerKey.includes('lot')) return 'text-orange'
  if (lowerKey.includes('start') && lowerKey.includes('time')) return 'text-orange'
  
  // Other special colors
  if (lowerKey.includes('id')) return 'text-primary'
  if (lowerKey.includes('time') || lowerKey.includes('date')) return 'text-info'
  
  // Default cycling through colors
  return colorClasses[index % colorClasses.length]
}
</script>

<style scoped>
.info-item {
  margin-bottom: 8px;
}

.info-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: rgba(var(--v-theme-on-surface), 0.8);
  margin-bottom: 2px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.info-value {
  font-weight: 600;
  word-break: break-word;
}
</style>