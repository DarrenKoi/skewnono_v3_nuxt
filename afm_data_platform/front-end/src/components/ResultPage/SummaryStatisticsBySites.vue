<template>
  <div v-if="summaryData && summaryData.length > 0">
    <div class="text-subtitle-2 mb-3">
      <v-icon start size="small">mdi-table</v-icon>
      Summary Statistics by Sites
    </div>
    
    <!-- Create separate cards for each site -->
    <v-row class="ma-0">
      <v-col 
        v-for="(siteData, siteName) in groupedBySite" 
        :key="siteName" 
        cols="12" 
        sm="6" 
        md="4" 
        class="pa-2"
      >
        <v-card elevation="2" class="site-card h-100">
          <!-- Site header -->
          <v-card-title class="bg-primary text-white py-2 text-body-1">
            <v-icon start size="small">mdi-target</v-icon>
            {{ siteName }}
          </v-card-title>
          
          <!-- Statistics table for this site -->
          <v-card-text class="pa-2">
            <v-data-table
              :headers="siteTableHeaders"
              :items="siteData"
              density="compact"
              class="site-summary-table"
              hide-default-footer
              :items-per-page="-1"
            >
              <!-- Custom template for statistic name column -->
              <template v-slot:item.ITEM="{ item }">
                <v-chip
                  size="x-small"
                  :color="getStatisticColor(item.ITEM)"
                  variant="outlined"
                  class="font-weight-medium"
                >
                  {{ item.ITEM }}
                </v-chip>
              </template>

              <!-- Custom template for value columns -->
              <template v-for="header in siteValueHeaders" :key="header.key" v-slot:[`item.${header.key}`]="{ item }">
                <span class="font-mono text-body-2">{{ formatTableValue(item[header.key], item.ITEM) }}</span>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup>
import { computed } from 'vue'

// Props
const props = defineProps({
  summaryData: {
    type: Array,
    default: () => []
  }
})

// Group summary data by Site
const groupedBySite = computed(() => {
  if (!props.summaryData || props.summaryData.length === 0) {
    return {}
  }

  try {
    const firstRecord = props.summaryData[0]
    console.log('🔍 [SummaryStatisticsBySites] First summary record:', firstRecord)
    console.log('🔍 [SummaryStatisticsBySites] Has Site field:', 'Site' in firstRecord)

    // If data has Site column, group by Site
    if ('Site' in firstRecord) {
      const grouped = {}
      
      // Get unique sites
      const uniqueSites = [...new Set(props.summaryData.map(row => row.Site).filter(site => site !== null && site !== undefined))]
      console.log('🔍 [SummaryStatisticsBySites] Unique sites:', uniqueSites)
      
      uniqueSites.forEach(site => {
        const siteRows = props.summaryData.filter(row => row.Site === site)
        grouped[site] = siteRows.map(row => {
          // Remove Site from the display data since it's already in the card title
          const { Site, ...rowWithoutSite } = row
          return rowWithoutSite
        })
      })
      
      console.log('🔍 [SummaryStatisticsBySites] Grouped data:', grouped)
      return grouped
    } else {
      // No Site column, create a single group
      return {
        'All Measurements': props.summaryData
      }
    }
  } catch (error) {
    console.error('❌ [SummaryStatisticsBySites] Error grouping by site:', error)
    return {
      'All Measurements': props.summaryData
    }
  }
})

// Table headers for site tables (without Site column)
const siteTableHeaders = computed(() => {
  const headers = [{
    title: 'Statistic',
    key: 'ITEM',
    align: 'start',
    sortable: false,
    width: '80px'
  }]

  if (!props.summaryData || props.summaryData.length === 0) {
    return headers
  }

  const firstRecord = props.summaryData[0]
  const allKeys = Object.keys(firstRecord)

  // Find value columns (measurement data columns), excluding Site and ITEM
  const valueColumns = allKeys.filter(key =>
    key !== 'ITEM' && key !== 'Site' &&
    (key.includes('(') || key.includes('nm') || key.includes('_H') || 
     key.includes('Left') || key.includes('Right') || key.includes('Ref'))
  )

  // Create headers for value columns
  valueColumns.forEach(key => {
    headers.push({
      title: key,
      key: key,
      align: 'end',
      sortable: false,
      width: '100px'
    })
  })

  return headers
})

// Get only value headers (excluding ITEM)
const siteValueHeaders = computed(() => {
  return siteTableHeaders.value.filter(header => header.key !== 'ITEM')
})

// Format values for the summary table
function formatTableValue(value, statisticName) {
  if (value == null || value === undefined || value === '') return 'N/A'

  if (typeof value === 'number') {
    // Format based on statistic type
    const upperStat = statisticName?.toUpperCase()
    if (upperStat === 'COUNT' || upperStat === 'CNT') {
      return value.toLocaleString()
    }

    // Most AFM measurements are in nm scale - use appropriate precision
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

// Get color for different statistics
function getStatisticColor(statisticName) {
  const colorMap = {
    'MEAN': 'primary',
    'AVERAGE': 'primary',
    'AVG': 'primary',
    'STDEV': 'warning',
    'STD': 'warning',
    'STDDEV': 'warning',
    'MIN': 'success',
    'MINIMUM': 'success',
    'MAX': 'error',
    'MAXIMUM': 'error',
    'RANGE': 'info',
    'COUNT': 'secondary',
    'CNT': 'secondary',
    'MEDIAN': 'purple',
    'RMS': 'orange'
  }

  const upperStat = statisticName?.toUpperCase()
  return colorMap[upperStat] || 'grey'
}
</script>

<style scoped>
.site-card {
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.site-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.site-card .v-card-title {
  font-size: 0.9rem;
  font-weight: 600;
  padding: 8px 12px;
}

.site-summary-table {
  border: none;
}

.site-summary-table :deep(.v-data-table__tr:hover) {
  background-color: rgba(var(--v-theme-primary), 0.04);
}

.site-summary-table :deep(.v-data-table-header) {
  background-color: rgba(var(--v-theme-surface), 0.3);
}

.site-summary-table :deep(.v-data-table__th) {
  font-weight: 600;
  font-size: 0.7rem;
  padding: 4px 8px;
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.12);
}

.site-summary-table :deep(.v-data-table__td) {
  padding: 4px 8px;
  font-size: 0.8rem;
}

.font-mono {
  font-family: 'Courier New', monospace;
  font-weight: 500;
}

/* Responsive adjustments */
@media (max-width: 960px) {
  .site-card .v-card-title {
    font-size: 0.8rem;
    padding: 6px 10px;
  }
  
  .site-summary-table :deep(.v-data-table__th),
  .site-summary-table :deep(.v-data-table__td) {
    padding: 3px 6px;
    font-size: 0.75rem;
  }
}
</style>