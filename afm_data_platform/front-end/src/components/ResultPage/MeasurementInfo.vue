<template>
  <v-card class="h-100" elevation="2">
    <v-card-title class="bg-primary text-white py-2 text-subtitle-1">
      <v-icon start size="small">mdi-information</v-icon>
      Information
    </v-card-title>
    <v-card-text class="pa-3">
      <!-- Information Details Component -->
      <InformationDetails 
        :measurement-info="measurementInfo" 
        :compact="compact" 
      />
      
      <!-- Summary Data by Sites Component -->
      <div v-if="summaryData && summaryData.length > 0" class="mt-4 pt-3 border-t">
        <SummaryStatisticsBySites 
          :summary-data="summaryData" 
        />
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
// Import sub-components
import InformationDetails from './InformationDetails.vue'
import SummaryStatisticsBySites from './SummaryStatisticsBySites.vue'

// Props
const props = defineProps({
  measurementInfo: {
    type: Object,
    default: () => ({})
  },
  compact: {
    type: Boolean,
    default: false
  },
  summaryData: {
    type: Array,
    default: () => []
  }
})
</script>

<style scoped>
/* Ensure full height utilization */
.v-card {
  height: 100%;
  min-height: 750px;
  display: flex;
  flex-direction: column;
}

.v-card-text {
  flex: 1;
  overflow-y: auto;
  min-height: 680px; /* Account for card title */
}

.border-t {
  border-top: 1px solid rgba(var(--v-theme-outline), 0.12);
}
</style>