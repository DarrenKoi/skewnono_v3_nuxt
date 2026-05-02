<template>
  <v-card 
    class="measurement-card compact" 
    elevation="2" 
    :loading="loading"
    hover
  >
    <!-- Compact Card Content -->
    <v-card-text class="pa-3 pb-2">
      <!-- Order Number Badge -->
      <div class="order-badge">
        {{ orderNumber }}
      </div>
      
      <!-- Essential Information -->
      <div class="info-row">
        <v-icon size="x-small" class="mr-1">mdi-clock-outline</v-icon>
        <span class="info-text">{{ formatDateTime(measurement.event_time || measurement.formatted_date) }}</span>
      </div>
      
      <div class="info-row">
        <v-icon size="x-small" class="mr-1">mdi-flask-outline</v-icon>
        <span class="info-text font-weight-medium">{{ measurement.rcp_id || measurement.recipe_name || 'Unknown Recipe' }}</span>
      </div>
      
      <div class="info-row">
        <v-icon size="x-small" class="mr-1">mdi-chip</v-icon>
        <span class="info-text">{{ measurement.lot_id || 'Unknown Lot' }}</span>
      </div>
    </v-card-text>
    
    <!-- Compact Actions -->
    <v-card-actions class="pa-2 pt-0">
      <v-spacer />
      <v-btn
        size="small"
        color="primary"
        variant="tonal"
        :loading="navigating"
        @click="viewDetails"
      >
        View Details
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

// Props
const props = defineProps({
  measurement: {
    type: Object,
    required: true
  },
  orderNumber: {
    type: Number,
    required: true
  },
  loading: {
    type: Boolean,
    default: false
  }
})

// Setup
const router = useRouter()
const navigating = ref(false)

// Computed properties
const isValidForNavigation = computed(() => {
  return !!(props.measurement.filename && (props.measurement.rcp_id || props.measurement.recipe_name))
})

// Methods
function formatDateTime(dateString) {
  if (!dateString) return 'N/A'
  
  try {
    const date = new Date(dateString)
    // Korean-friendly format: yy/mm/dd hh:mm:ss
    const year = String(date.getFullYear()).slice(-2)
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hours = String(date.getHours()).padStart(2, '0')
    const minutes = String(date.getMinutes()).padStart(2, '0')
    const seconds = String(date.getSeconds()).padStart(2, '0')
    
    return `${year}/${month}/${day} ${hours}:${minutes}:${seconds}`
  } catch (error) {
    return dateString.toString()
  }
}

async function viewDetails() {
  if (!isValidForNavigation.value) {
    console.warn('Cannot navigate: missing required data', props.measurement)
    return
  }

  navigating.value = true
  
  try {
    // Extract parameters for navigation
    const filename = props.measurement.filename
    const recipeId = props.measurement.rcp_id || props.measurement.recipe_name || 'Unknown'
    const tool = props.measurement.tool || 'MAP608'
    
    console.log('🚀 Navigating to ResultPage with:', {
      filename,
      recipeId,
      tool
    })
    
    // Build route parameters
    const routeParams = {
      name: 'ResultPage',
      params: {
        filename: encodeURIComponent(filename),
        recipeId: encodeURIComponent(recipeId)
      },
      query: {
        tool: tool,
        from: 'data-trend'
      }
    }
    
    // Navigate to ResultPage
    await router.push(routeParams)
    
  } catch (error) {
    console.error('❌ Navigation error:', error)
    // Could show a toast notification here
  } finally {
    navigating.value = false
  }
}
</script>

<style scoped>
.measurement-card.compact {
  transition: all 0.2s ease;
  position: relative;
  min-height: 140px;
}

.measurement-card.compact:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.order-badge {
  position: absolute;
  top: 8px;
  right: 8px;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background-color: rgba(var(--v-theme-primary), 0.1);
  color: rgb(var(--v-theme-primary));
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  font-size: 0.75rem;
}

.info-row {
  display: flex;
  align-items: center;
  margin-bottom: 6px;
  color: rgba(var(--v-theme-on-surface), 0.8);
}

.info-row:last-child {
  margin-bottom: 0;
}

.info-text {
  font-size: 0.875rem;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.info-row .v-icon {
  color: rgba(var(--v-theme-on-surface), 0.6);
  flex-shrink: 0;
}

/* Responsive adjustments */
@media (max-width: 960px) {
  .info-text {
    font-size: 0.8rem;
  }
  
  .order-badge {
    width: 20px;
    height: 20px;
    font-size: 0.7rem;
  }
}
</style>