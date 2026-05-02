<template>
  <v-card class="mb-4" elevation="3">
    <v-card-title>
      <v-icon start>mdi-group</v-icon>
      Data Grouping ({{ groupedCount }})
      <v-spacer />
      <v-btn v-if="groupedCount > 0" variant="text" size="small" @click="clearGroup">
        Clear All
      </v-btn>
    </v-card-title>
    <v-divider />
    
    <v-list v-if="groupedCount > 0" density="compact">
      <v-list-item v-for="(item, index) in sortedGroupedData" :key="index">
        <v-list-item-title class="text-body-2">
          {{ item.formatted_date || item.date }} - {{ item.recipe_name }} - {{ item.lot_id }}
          <v-chip size="x-small" color="info" variant="outlined" class="ml-2">
            {{ item.tool_name || item.tool || 'MAP608' }}
          </v-chip>
        </v-list-item-title>
        <v-list-item-subtitle class="text-caption">
          Slot: {{ item.slot_number }} | {{ item.measured_info }}
        </v-list-item-subtitle>
        <!-- Data availability indicators -->
        <v-list-item-subtitle class="mt-1 d-flex align-center gap-1">
          <v-icon v-if="item.has_profile" size="x-small" color="success" title="Profile Data">mdi-chart-line</v-icon>
          <v-icon v-if="item.has_data" size="x-small" color="info" title="Measurement Data">mdi-database</v-icon>
          <v-icon v-if="item.has_image" size="x-small" color="primary" title="Image">mdi-image</v-icon>
          <v-icon v-if="item.has_align" size="x-small" color="warning" title="Alignment Data">mdi-align-vertical-center</v-icon>
          <v-icon v-if="item.has_tip" size="x-small" color="deep-purple" title="Tip Data">mdi-pin</v-icon>
        </v-list-item-subtitle>
        
        <template v-slot:append>
          <v-btn variant="text" size="small" @click="removeFromGroup(item.filename)">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </template>
      </v-list-item>
    </v-list>
    
    <v-card-text v-else class="text-center text-medium-emphasis">
      No grouped data yet
    </v-card-text>

    <v-card-actions v-if="groupedCount > 0">
      <v-btn color="primary" @click="viewTrendAnalysis">
        <v-icon start>mdi-chart-line</v-icon>
        See Together
      </v-btn>
      <v-btn v-if="groupedCount > 1" color="secondary" variant="outlined" @click="saveCurrentGroup">
        <v-icon start>mdi-content-save</v-icon>
        Save Group
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { computed } from 'vue'

// Props
const props = defineProps({
  groupedData: {
    type: Array,
    default: () => []
  },
  groupedCount: {
    type: Number,
    default: 0
  }
})

// Computed property to sort grouped data by date (latest to oldest)
const sortedGroupedData = computed(() => {
  return [...props.groupedData].sort((a, b) => {
    // Sort by addedAt timestamp first (newest first), then by formatted_date as fallback
    const dateA = new Date(a.addedAt || a.formatted_date || a.date)
    const dateB = new Date(b.addedAt || b.formatted_date || b.date)
    return dateB - dateA // Latest first (descending order)
  })
})

// Emits
const emit = defineEmits(['remove-from-group', 'clear-group', 'view-trend-analysis', 'save-current-group'])

// Functions
function removeFromGroup(filename) {
  emit('remove-from-group', filename)
}

function clearGroup() {
  emit('clear-group')
}

function viewTrendAnalysis() {
  emit('view-trend-analysis')
}

function saveCurrentGroup() {
  emit('save-current-group')
}
</script>