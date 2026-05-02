<template>
  <v-container fluid class="pa-4">
    <!-- Logo Header -->
    <div class="text-center mb-6">
      <img alt="AFM Logo" class="mb-4" src="@/assets/afm_logo2.png"
        style="max-width: 400px; width: 100%; height: auto;">
    </div>

    <!-- Tool Selection Interface -->
    <div class="text-center mb-6">
      <v-card class="pa-4 mx-auto" style="max-width: 600px;" elevation="2">
        <div class="d-flex justify-center align-center gap-4">
          <v-icon color="primary">mdi-tools</v-icon>
          <span class="text-h6 font-weight-medium mr-4">Tool:</span>
          <v-tooltip v-for="tool in availableTools" :key="tool.id" :text="tool.description" location="bottom">
            <template v-slot:activator="{ props }">
              <v-chip 
                v-bind="props" 
                :color="selectedTool === tool.id ? 'primary' : 'default'"
                :variant="selectedTool === tool.id ? 'elevated' : 'outlined'" 
                size="large" 
                class="px-4 mx-2 tool-chip"
                :class="{ 'tool-selected': selectedTool === tool.id }"
                @click="selectTool(tool.id)"
                :disabled="isLoadingToolData">
                <v-progress-circular 
                  v-if="isLoadingToolData && pendingTool === tool.id" 
                  indeterminate 
                  size="18" 
                  width="2"
                  :color="selectedTool === tool.id ? 'white' : 'primary'"
                  class="mr-2" />
                <v-icon v-else start :color="selectedTool === tool.id ? 'white' : 'primary'">
                  mdi-microscope
                </v-icon>
                <span class="font-weight-medium">{{ tool.name }}</span>
                <v-chip 
                  v-if="toolDataCounts[tool.id] && selectedTool === tool.id" 
                  size="x-small" 
                  color="white" 
                  class="ml-2">
                  {{ toolDataCounts[tool.id].toLocaleString() }}
                </v-chip>
              </v-chip>
            </template>
          </v-tooltip>
        </div>
        
        <!-- Loading indicator -->
        <v-expand-transition>
          <div v-if="isLoadingToolData" class="mt-3">
            <v-progress-linear indeterminate color="primary" height="2" />
            <p class="text-caption text-medium-emphasis mt-1">
              Loading {{ pendingTool }} data...
            </p>
          </div>
        </v-expand-transition>
        
        <!-- Tool data info -->
        <v-expand-transition>
          <v-alert 
            v-if="!isLoadingToolData && toolDataCounts[selectedTool]" 
            type="info" 
            variant="tonal" 
            density="compact"
            class="mt-3">
            <div class="d-flex align-center justify-space-between">
              <span class="text-caption">
                <v-icon size="small" class="mr-1">mdi-database</v-icon>
                {{ toolDataCounts[selectedTool]?.toLocaleString() || 0 }} measurements available
              </span>
              <span class="text-caption text-medium-emphasis">
                Last updated: {{ toolLastUpdated[selectedTool] || 'Just now' }}
              </span>
            </div>
          </v-alert>
        </v-expand-transition>
      </v-card>
    </div>

    <v-row justify="center" style="max-width: 1400px; margin: 0 auto;">
      <!-- Left Column: Search & Results -->
      <v-col cols="12" lg="7" md="6">
        <SearchSection :search-results="searchResults" :is-searching="isSearching" :is-in-group="dataStore.isInGroup"
          @search-performed="handleSearchPerformed" @add-to-group="addToGroup" @view-details="viewDetails" />
      </v-col>

      <!-- Right Column: History & Data Grouping -->
      <v-col cols="12" lg="5" md="6">
        <div class="px-2">
          <!-- View History -->
          <ViewHistoryCard :view-history="dataStore.viewHistory" :history-count="dataStore.historyCount"
            @view-details="viewDetails" @clear-history="dataStore.clearHistory"
            @remove-from-history="dataStore.removeFromHistory" />

          <!-- Data Grouping -->
          <DataGroupingCard :grouped-data="dataStore.groupedData" :grouped-count="dataStore.groupedCount"
            @remove-from-group="dataStore.removeFromGroup" @clear-group="dataStore.clearGroup"
            @view-trend-analysis="viewTrendAnalysis" @save-current-group="saveCurrentGroup" />

          <!-- Saved Groups -->
          <SavedGroupsCard :group-history="dataStore.groupHistory" :group-history-count="dataStore.groupHistoryCount"
            @load-saved-group="loadSavedGroup" @remove-from-group-history="dataStore.removeFromGroupHistory"
            @clear-group-history="dataStore.clearGroupHistory" />
        </div>
      </v-col>
    </v-row>

    <!-- Loading Dialog for SEE TOGETHER -->
    <LoadingDialog
      v-model="showLoadingDialog"
      title="Loading Measurement Data"
      :progress="loadingProgress"
      :current="loadedCount"
      :total="totalCount"
      :message="loadingMessage"
      :detail="currentFileName"
      :errors="loadingErrors"
      :cancelling="isCancelling"
      item-label="measurements"
      error-label="file(s) failed to load"
      @cancel="cancelLoading" />

    <!-- Save Group Dialog -->
    <v-dialog v-model="showSaveDialog" max-width="500px" persistent>
      <v-card>
        <v-card-title class="text-h5 d-flex align-center">
          <v-icon color="primary" class="mr-2">mdi-content-save</v-icon>
          Save Data Group
        </v-card-title>

        <v-card-text>
          <v-container>
            <v-row>
              <v-col cols="12">
                <v-text-field v-model="groupName" label="Group Name *" placeholder="Enter a name for this group"
                  variant="outlined" :rules="[v => !!v || 'Group name is required']" counter="50" maxlength="50"
                  autofocus />
              </v-col>
              <v-col cols="12">
                <v-textarea v-model="groupDescription" label="Description (Optional)"
                  placeholder="Add a description for this group" variant="outlined" rows="3" counter="200"
                  maxlength="200" />
              </v-col>
              <v-col cols="12">
                <v-alert type="info" variant="tonal" class="mb-0">
                  <div class="text-body-2">
                    <strong>Group contains:</strong> {{ dataStore.groupedCount }} measurements
                  </div>
                </v-alert>
              </v-col>
            </v-row>
          </v-container>
        </v-card-text>

        <v-card-actions>
          <v-spacer />
          <v-btn color="grey" variant="text" @click="cancelSaveGroup">
            Cancel
          </v-btn>
          <v-btn color="primary" variant="elevated" :disabled="!groupName.trim()" @click="confirmSaveGroup">
            <v-icon start>mdi-content-save</v-icon>
            Save Group
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useDataStore } from '@/stores/dataStore.js'
import { apiService } from '@/services/api'

// Import components
import SearchSection from '@/components/MainPage/SearchSection.vue'
import ViewHistoryCard from '@/components/MainPage/ViewHistoryCard.vue'
import DataGroupingCard from '@/components/MainPage/DataGroupingCard.vue'
import SavedGroupsCard from '@/components/MainPage/SavedGroupsCard.vue'
import LoadingDialog from '@/components/common/LoadingDialog.vue'

const router = useRouter()
const dataStore = useDataStore()
const searchResults = ref([])
const isSearching = ref(false)

// Tool selection state
const selectedTool = ref('MAP608')
const isLoadingToolData = ref(false)
const pendingTool = ref('')
const toolDataCounts = ref({})
const toolLastUpdated = ref({})
const availableTools = ref([
  {
    id: 'MAP608',
    name: 'MAP608',
    description: 'PKG - Wafer Level Packaging',
    status: 'active'
  },
  {
    id: 'MAPC01',
    name: 'MAPC01',
    description: 'R3 - Research Fab',
    status: 'active'
  }
])

// Handle real-time search results from SearchSection component
function handleSearchPerformed(query, results) {
  if (query && results) {
    searchResults.value = results
    console.log('Real-time search results:', results.length, 'items')
  }
}

function viewDetails(measurement) {
  // Ensure measurement has tool information
  const measurementWithTool = {
    ...measurement,
    tool: measurement.tool || selectedTool.value
  }

  // Add to history with tool information
  dataStore.addToHistory(measurementWithTool)

  // Navigate to details with recipe ID and tool in URL
  const recipeId = measurement.rcp_id || measurement.recipe_name || 'unknown'
  router.push({
    path: `/result/${encodeURIComponent(recipeId)}/${encodeURIComponent(measurement.filename)}`,
    query: { tool: selectedTool.value }
  })
}

function addToGroup(measurement) {
  // Ensure measurement has tool information and preserve all fields
  const measurementWithTool = {
    ...measurement,
    tool: measurement.tool || selectedTool.value
  }
  dataStore.addToGroup(measurementWithTool)
}

async function viewTrendAnalysis() {
  console.log('🚀 [MainPage] Starting trend analysis with grouped data...')

  if (dataStore.groupedCount === 0) {
    console.warn('⚠️ No measurements in group to analyze')
    return
  }

  // Reset loading state
  loadingProgress.value = 0
  loadedCount.value = 0
  totalCount.value = dataStore.groupedData.length
  loadingErrors.value = []
  isCancelling.value = false
  currentFileName.value = ''
  
  // Create abort controller for cancellation
  loadingAbortController.value = new AbortController()

  // Show loading dialog
  loadingMessage.value = 'Preparing to load measurements...'
  showLoadingDialog.value = true

  try {
    // Load detailed data for all measurements in the group
    const loadPromises = dataStore.groupedData.map(async (measurement, index) => {
      // Check for cancellation
      if (loadingAbortController.value.signal.aborted) {
        return null
      }

      if (!measurement.filename) {
        console.warn(`⚠️ Skipping measurement without filename:`, measurement)
        loadedCount.value++
        loadingProgress.value = (loadedCount.value / totalCount.value) * 100
        return null
      }

      try {
        // Update current file being loaded
        currentFileName.value = measurement.filename
        loadingMessage.value = `Loading measurement ${loadedCount.value + 1} of ${totalCount.value}`
        
        console.log(`📊 Loading data for: ${measurement.filename}`)
        const toolName = measurement.tool || measurement.tool_name || selectedTool.value || 'MAP608'

        // Use the apiService to fetch detailed measurement data
        const response = await apiService.getAfmFileDetail(measurement.filename, toolName)

        // Update progress
        loadedCount.value++
        loadingProgress.value = (loadedCount.value / totalCount.value) * 100

        if (response.success && response.data) {
          return {
            filename: measurement.filename,
            tool: toolName,
            info: response.data.information || {},
            summary: response.data.summary || [],
            detailedData: response.data.data || [],
            availablePoints: response.data.available_points || []
          }
        } else {
          const errorMsg = `Failed: ${measurement.filename}`
          loadingErrors.value.push(errorMsg)
          console.error(`❌ Failed to load data for ${measurement.filename}:`, response.error)
          return null
        }
      } catch (error) {
        if (loadingAbortController.value.signal.aborted) {
          return null
        }
        const errorMsg = `Error: ${measurement.filename}`
        loadingErrors.value.push(errorMsg)
        console.error(`❌ Error loading ${measurement.filename}:`, error)
        loadedCount.value++
        loadingProgress.value = (loadedCount.value / totalCount.value) * 100
        return null
      }
    })

    // Wait for all measurements to load
    const results = await Promise.all(loadPromises)
    
    // Check if cancelled
    if (loadingAbortController.value.signal.aborted) {
      console.log('⚠️ Loading cancelled by user')
      showLoadingDialog.value = false
      return
    }
    
    const validResults = results.filter(r => r !== null)

    console.log(`✅ Loaded ${validResults.length} out of ${dataStore.groupedData.length} measurements`)

    // Store the loaded data in sessionStorage to pass to DataTrendPage
    if (validResults.length > 0) {
      sessionStorage.setItem('groupDetailedData', JSON.stringify(validResults))

      // Hide loading dialog before navigation
      showLoadingDialog.value = false

      // Navigate to data trend page
      router.push('/result/data_trend')
    } else {
      console.error('❌ No valid data loaded, cannot proceed to trend analysis')
      loadingMessage.value = 'Failed to load measurements'
      // Keep dialog open to show error state
      setTimeout(() => {
        showLoadingDialog.value = false
      }, 3000)
    }

  } catch (error) {
    if (loadingAbortController.value.signal.aborted) {
      console.log('⚠️ Loading cancelled')
    } else {
      console.error('❌ Error during trend analysis data loading:', error)
      loadingMessage.value = 'An error occurred while loading'
    }
    setTimeout(() => {
      showLoadingDialog.value = false
    }, 3000)
  }
}

// Function to handle loading cancellation
function cancelLoading() {
  isCancelling.value = true
  if (loadingAbortController.value) {
    loadingAbortController.value.abort()
  }
  setTimeout(() => {
    showLoadingDialog.value = false
    isCancelling.value = false
  }, 500)
}


// Loading dialog state
const showLoadingDialog = ref(false)
const loadingMessage = ref('')
const loadingProgress = ref(0)
const loadedCount = ref(0)
const totalCount = ref(0)
const currentFileName = ref('')
const loadingErrors = ref([])
// Removed showErrorDetails - now handled by LoadingDialog component
const isCancelling = ref(false)
const loadingAbortController = ref(null)

// Save group dialog state
const showSaveDialog = ref(false)
const groupName = ref('')
const groupDescription = ref('')

function saveCurrentGroup() {
  // Set default name with current date and time to make it unique
  const now = new Date()
  const dateStr = now.toLocaleDateString()
  const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  groupName.value = `Group ${dateStr} ${timeStr}`
  groupDescription.value = ''
  showSaveDialog.value = true
}

function confirmSaveGroup() {
  if (groupName.value.trim()) {
    dataStore.saveCurrentGroupAsHistory(groupName.value.trim(), groupDescription.value.trim())
    showSaveDialog.value = false
    groupName.value = ''
    groupDescription.value = ''
  }
}

function cancelSaveGroup() {
  showSaveDialog.value = false
  groupName.value = ''
  groupDescription.value = ''
}

function loadSavedGroup(groupId) {
  dataStore.loadGroupFromHistory(groupId)
}

// Tool selection functions
async function selectTool(toolId) {
  // Don't reload if already selected
  if (selectedTool.value === toolId && toolDataCounts.value[toolId]) {
    return
  }

  console.log(`🔧 Tool selected: ${toolId}`)
  
  // Set loading state
  isLoadingToolData.value = true
  pendingTool.value = toolId
  
  // Clear current search results when switching tools
  searchResults.value = []
  
  // Update selected tool
  selectedTool.value = toolId

  // Store selected tool in data store for use by other components
  dataStore.setSelectedTool(toolId)

  // Trigger initial data load for the selected tool
  await loadToolData(toolId)
  
  // Clear loading state
  isLoadingToolData.value = false
  pendingTool.value = ''
}

function getSelectedToolInfo() {
  const tool = availableTools.value.find(t => t.id === selectedTool.value)
  return tool ? `${tool.name} - ${tool.description}` : 'No tool selected'
}

async function loadToolData(toolId) {
  console.log(`📊 Loading data for tool: ${toolId}`)
  
  try {
    // Simulate getting data count from the search composable or API
    // The search composable will automatically reload data when the tool changes
    // via the watch on dataStore.selectedTool
    
    // For now, we'll simulate with a timeout
    await new Promise(resolve => setTimeout(resolve, 800))
    
    // In reality, this would come from the API response
    // You could get this from the search composable's loaded data
    const mockCounts = {
      'MAP608': 15234,
      'MAPC01': 8756
    }
    
    toolDataCounts.value[toolId] = mockCounts[toolId] || 0
    toolLastUpdated.value[toolId] = new Date().toLocaleTimeString([], { 
      hour: '2-digit', 
      minute: '2-digit' 
    })
    
    console.log(`✅ Loaded ${toolDataCounts.value[toolId]} measurements for ${toolId}`)
  } catch (error) {
    console.error(`❌ Error loading tool data for ${toolId}:`, error)
    toolDataCounts.value[toolId] = 0
  }
}

// Initialize component
onMounted(() => {
  console.log('🚀 MainPage: Component mounted and ready for AFM file searches')

  // Initialize with stored tool selection
  const storedTool = dataStore.selectedTool
  if (storedTool && availableTools.value.find(t => t.id === storedTool)) {
    selectedTool.value = storedTool
    console.log(`🔧 MainPage: Restored tool selection: ${storedTool}`)
  } else {
    // Set default tool
    selectTool('MAP608')
  }
})

</script>

<style scoped>
/* Tool selection chips */
.tool-chip {
  transition: all 0.3s ease;
  cursor: pointer;
}

.tool-chip:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.tool-chip.tool-selected {
  box-shadow: 0 4px 12px rgba(var(--v-theme-primary), 0.3);
}

.tool-chip:disabled {
  opacity: 0.7;
  cursor: wait;
}

/* Smooth transitions for expand animations */
.v-expand-transition-enter-active,
.v-expand-transition-leave-active {
  transition: all 0.3s ease;
}
</style>
