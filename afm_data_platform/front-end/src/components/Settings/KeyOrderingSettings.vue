<template>
  <v-card elevation="2">
    <v-card-title class="bg-primary text-white">
      <v-icon start>mdi-sort-variant</v-icon>
      Key Ordering Settings
    </v-card-title>
    
    <v-card-text class="pa-4">
      <v-alert
        type="info"
        variant="tonal"
        density="compact"
        class="mb-4"
        prepend-icon="mdi-information"
      >
        Drag and drop items to reorder how measurement data keys are displayed in results.
      </v-alert>
      
      <!-- Available Keys Display -->
      <div class="mb-4">
        <v-chip-group 
          column
          class="mb-2"
        >
          <v-chip
            v-for="key in availableKeys"
            :key="key"
            size="small"
            :color="getKeyColor(key)"
            variant="outlined"
          >
            {{ getKeyDisplayName(key) }}
          </v-chip>
        </v-chip-group>
      </div>
      
      <!-- Ordered Keys List (Draggable) -->
      <div class="ordered-keys-container">
        <h3 class="text-h6 mb-3">
          <v-icon start>mdi-drag-vertical</v-icon>
          Current Key Order
        </h3>
        
        <v-list class="key-ordering-list">
          <template v-for="(keyItem, index) in orderedKeysForDisplay" :key="keyItem.key">
            <v-list-item
              :class="['key-ordering-item', { 'is-default': keyItem.isDefault }]"
              density="compact"
            >
              <template v-slot:prepend>
                <v-icon 
                  :color="keyItem.isDefault ? 'primary' : 'grey'"
                  size="small"
                >
                  mdi-drag-vertical
                </v-icon>
              </template>
              
              <v-list-item-title>
                <v-chip
                  size="small"
                  :color="getKeyColor(keyItem.key)"
                  variant="outlined"
                  class="mr-2"
                >
                  {{ keyItem.displayName }}
                </v-chip>
                <span v-if="keyItem.isDefault" class="text-caption text-primary">(Default)</span>
              </v-list-item-title>
              
              <template v-slot:append>
                <v-btn-group variant="text" density="compact">
                  <v-btn
                    icon="mdi-chevron-up"
                    size="small"
                    :disabled="index === 0"
                    @click="moveKeyUp(keyItem.key)"
                  />
                  <v-btn
                    icon="mdi-chevron-down"
                    size="small"
                    :disabled="index === orderedKeysForDisplay.length - 1"
                    @click="moveKeyDown(keyItem.key)"
                  />
                </v-btn-group>
              </template>
            </v-list-item>
            
            <v-divider v-if="index < orderedKeysForDisplay.length - 1" />
          </template>
        </v-list>
      </div>
      
      <!-- Action Buttons -->
      <v-row class="mt-4">
        <v-col cols="12" sm="6">
          <v-btn
            color="warning"
            variant="outlined"
            block
            prepend-icon="mdi-restore"
            @click="resetToDefault"
          >
            Reset to Default
          </v-btn>
        </v-col>
        <v-col cols="12" sm="6">
          <v-btn
            color="success"
            variant="flat"
            block
            prepend-icon="mdi-check"
            @click="applyOrdering"
          >
            Apply Changes
          </v-btn>
        </v-col>
      </v-row>
      
      <!-- Current Order Preview -->
      <v-expansion-panels class="mt-4" variant="accordion">
        <v-expansion-panel>
          <v-expansion-panel-title>
            <v-icon start>mdi-eye</v-icon>
            Preview Current Order
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-chip-group column>
              <v-chip
                v-for="(keyItem, index) in orderedKeysForDisplay"
                :key="keyItem.key"
                size="small"
                :color="getKeyColor(keyItem.key)"
                variant="outlined"
                :prepend-icon="`mdi-numeric-${index + 1}-circle-outline`"
              >
                {{ keyItem.displayName }}
              </v-chip>
            </v-chip-group>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed, watch, inject } from 'vue'
import { useKeyOrdering } from '@/composables/useKeyOrdering.js'

const props = defineProps({
  measurementData: {
    type: Array,
    default: () => []
  }
})

const emit = defineEmits(['order-changed'])

// Use the key ordering composable
const {
  availableKeys,
  customKeyOrder,
  orderedKeysForDisplay,
  updateAvailableKeys,
  moveKeyUp,
  moveKeyDown,
  resetToDefault,
  getKeyDisplayName
} = useKeyOrdering()

// Watch for changes in measurement data to update available keys
watch(() => props.measurementData, (newData) => {
  console.log('🔧 [KeyOrderingSettings] Measurement data changed, updating available keys')
  updateAvailableKeys(newData)
}, { immediate: true })

// Get color for different key types
function getKeyColor(keyName) {
  const colorMap = {
    'filename': 'primary',
    'recipe_name': 'success',
    'lot_id': 'info',
    'slot_number': 'warning',
    'measured_info': 'purple',
    'formatted_date': 'orange',
    'tool_name': 'cyan',
    'date': 'grey',
    'id': 'grey-lighten-1',
    'info': 'blue-grey',
    'data_status': 'green',
    'data_detail': 'indigo'
  }
  
  return colorMap[keyName] || 'grey-lighten-2'
}

// Apply the current ordering
function applyOrdering() {
  console.log('🔧 [KeyOrderingSettings] Applying key ordering:', customKeyOrder.value)
  emit('order-changed', customKeyOrder.value)
  
  // Show success message (could use a toast/snackbar)
  console.log('✅ Key ordering applied successfully')
}

// Watch for changes in custom order to emit updates
watch(customKeyOrder, (newOrder) => {
  emit('order-changed', newOrder)
}, { deep: true })
</script>

<style scoped>
.key-ordering-list {
  border: 1px solid rgba(var(--v-border-color), var(--v-border-opacity));
  border-radius: 4px;
  max-height: 400px;
  overflow-y: auto;
}

.key-ordering-item {
  transition: background-color 0.2s ease;
  cursor: grab;
}

.key-ordering-item:hover {
  background-color: rgba(var(--v-theme-primary), 0.04);
}

.key-ordering-item.is-default {
  background-color: rgba(var(--v-theme-primary), 0.02);
}

.key-ordering-item:active {
  cursor: grabbing;
}

.ordered-keys-container {
  background-color: rgba(var(--v-theme-surface), 0.5);
  border-radius: 8px;
  padding: 16px;
}

/* Responsive adjustments */
@media (max-width: 600px) {
  .key-ordering-list {
    max-height: 300px;
  }
  
  .ordered-keys-container {
    padding: 12px;
  }
}
</style>