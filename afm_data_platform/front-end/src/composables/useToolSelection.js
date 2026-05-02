import { ref, computed, watch } from 'vue'
import { useDataStore } from '@/stores/dataStore'

/**
 * Tool configuration
 */
const TOOL_CONFIG = {
  MAP608: {
    id: 'MAP608',
    name: 'MAP608',
    description: 'PKG - Wafer Level Packaging',
    icon: 'mdi-microscope',
    color: 'primary'
  },
  MAPC01: {
    id: 'MAPC01', 
    name: 'MAPC01',
    description: 'R3 - Research Fab',
    icon: 'mdi-microscope',
    color: 'secondary'
  }
}

/**
 * Composable for managing AFM tool selection
 * @returns {Object} Tool selection state and methods
 */
export function useToolSelection() {
  const dataStore = useDataStore()
  
  // State
  const selectedTool = ref(dataStore.selectedTool || 'MAP608')
  const isLoadingToolData = ref(false)
  const pendingTool = ref('')
  const toolDataCounts = ref({})
  const toolLastUpdated = ref({})
  const toolLoadErrors = ref({})
  
  // Computed
  const availableTools = computed(() => Object.values(TOOL_CONFIG))
  
  const selectedToolInfo = computed(() => {
    return TOOL_CONFIG[selectedTool.value] || TOOL_CONFIG.MAP608
  })
  
  const selectedToolDescription = computed(() => {
    const tool = selectedToolInfo.value
    return `${tool.name} - ${tool.description}`
  })
  
  const hasToolData = computed(() => {
    return toolDataCounts.value[selectedTool.value] > 0
  })
  
  /**
   * Select a tool and load its data
   * @param {string} toolId - Tool ID to select
   * @param {boolean} forceReload - Force reload even if data exists
   * @returns {Promise<void>}
   */
  async function selectTool(toolId, forceReload = false) {
    // Don't reload if already selected and has data (unless forced)
    if (selectedTool.value === toolId && toolDataCounts.value[toolId] && !forceReload) {
      return
    }
    
    console.log(`🔧 Selecting tool: ${toolId}`)
    
    // Set loading state
    isLoadingToolData.value = true
    pendingTool.value = toolId
    toolLoadErrors.value[toolId] = null
    
    try {
      // Update selected tool
      selectedTool.value = toolId
      dataStore.setSelectedTool(toolId)
      
      // Load tool data
      await loadToolData(toolId)
      
    } catch (error) {
      console.error(`❌ Error selecting tool ${toolId}:`, error)
      toolLoadErrors.value[toolId] = error.message || 'Failed to load tool data'
      
    } finally {
      isLoadingToolData.value = false
      pendingTool.value = ''
    }
  }
  
  /**
   * Load data for a specific tool
   * @param {string} toolId - Tool ID to load data for
   * @returns {Promise<void>}
   */
  async function loadToolData(toolId) {
    console.log(`📊 Loading data for tool: ${toolId}`)
    
    try {
      // In a real implementation, this would call the API
      // For now, we'll simulate with a timeout
      await new Promise(resolve => setTimeout(resolve, 800))
      
      // Mock data counts - replace with actual API call
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
      console.error(`❌ Error loading data for ${toolId}:`, error)
      toolDataCounts.value[toolId] = 0
      throw error
    }
  }
  
  /**
   * Refresh data for the current tool
   * @returns {Promise<void>}
   */
  async function refreshCurrentTool() {
    if (selectedTool.value) {
      await selectTool(selectedTool.value, true)
    }
  }
  
  /**
   * Get data count for a specific tool
   * @param {string} toolId - Tool ID
   * @returns {number} Data count
   */
  function getToolDataCount(toolId) {
    return toolDataCounts.value[toolId] || 0
  }
  
  /**
   * Check if a tool is currently loading
   * @param {string} toolId - Tool ID
   * @returns {boolean}
   */
  function isToolLoading(toolId) {
    return isLoadingToolData.value && pendingTool.value === toolId
  }
  
  // Watch for external changes to selected tool
  watch(() => dataStore.selectedTool, (newTool) => {
    if (newTool && newTool !== selectedTool.value) {
      selectTool(newTool)
    }
  })
  
  return {
    // State
    selectedTool,
    isLoadingToolData,
    pendingTool,
    toolDataCounts,
    toolLastUpdated,
    toolLoadErrors,
    
    // Computed
    availableTools,
    selectedToolInfo,
    selectedToolDescription,
    hasToolData,
    
    // Methods
    selectTool,
    loadToolData,
    refreshCurrentTool,
    getToolDataCount,
    isToolLoading,
    
    // Constants
    TOOL_CONFIG
  }
}
</template>