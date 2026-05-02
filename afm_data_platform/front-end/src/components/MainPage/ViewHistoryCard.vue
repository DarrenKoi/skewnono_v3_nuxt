<template>
  <v-card class="mb-4" elevation="3">
    <v-card-title>
      <v-icon start>mdi-eye</v-icon>
      View History
      <v-spacer />
      <v-btn v-if="historyCount > 0" variant="text" size="small" @click="clearHistory">
        Clear All
      </v-btn>
    </v-card-title>
    <v-divider />
    
    <v-list v-if="historyCount > 0" density="compact">
      <v-list-item 
        v-for="(item, index) in viewHistory" 
        :key="index"
        @click="viewDetails(item)"
        class="cursor-pointer"
      >
        <v-list-item-title class="text-body-2">
          {{ item.formatted_date || item.date }} - {{ item.recipe_name }} - {{ item.lot_id }}
          <v-chip size="x-small" color="info" variant="outlined" class="ml-2">
            {{ item.tool_name || item.tool || 'MAP608' }}
          </v-chip>
        </v-list-item-title>
        <v-list-item-subtitle class="text-caption">
          Slot: {{ item.slot_number }} | {{ item.measured_info }} | {{ new Date(item.viewedAt).toLocaleString() }}
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
          <v-btn variant="text" size="small" @click.stop="removeFromHistory(item.filename)">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </template>
      </v-list-item>
    </v-list>
    <v-card-text v-else class="text-center text-medium-emphasis">
      No view history yet
    </v-card-text>
  </v-card>
</template>

<script setup>
// Props
defineProps({
  viewHistory: {
    type: Array,
    default: () => []
  },
  historyCount: {
    type: Number,
    default: 0
  }
})

// Emits
const emit = defineEmits(['view-details', 'clear-history', 'remove-from-history'])

// Functions
function viewDetails(item) {
  emit('view-details', item)
}

function clearHistory() {
  emit('clear-history')
}

function removeFromHistory(filename) {
  console.log(`🖱️ ViewHistoryCard: Clicked remove for filename: ${filename}`)
  emit('remove-from-history', filename)
}
</script>