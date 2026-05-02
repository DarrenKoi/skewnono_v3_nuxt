import { ref, computed } from 'vue'

/**
 * Composable for managing loading states with progress tracking
 * @param {Object} options - Configuration options
 * @param {number} options.total - Total items to process
 * @returns {Object} Loading state management functions and reactive variables
 */
export function useLoadingState(options = {}) {
  // Core state
  const isLoading = ref(false)
  const loadedCount = ref(0)
  const totalCount = ref(options.total || 0)
  const currentItem = ref('')
  const message = ref('')
  const errors = ref([])
  
  // Cancellation state
  const isCancelling = ref(false)
  const abortController = ref(null)
  
  // Computed progress percentage
  const progress = computed(() => {
    if (totalCount.value === 0) return 0
    return Math.round((loadedCount.value / totalCount.value) * 100)
  })
  
  // Computed success rate
  const successRate = computed(() => {
    if (loadedCount.value === 0) return 100
    const successCount = loadedCount.value - errors.value.length
    return Math.round((successCount / loadedCount.value) * 100)
  })
  
  /**
   * Start loading with specified total items
   * @param {number} total - Total number of items to load
   * @param {string} initialMessage - Initial loading message
   */
  function startLoading(total, initialMessage = 'Loading...') {
    isLoading.value = true
    loadedCount.value = 0
    totalCount.value = total
    currentItem.value = ''
    message.value = initialMessage
    errors.value = []
    isCancelling.value = false
    abortController.value = new AbortController()
  }
  
  /**
   * Update loading progress
   * @param {string} itemName - Name of current item being processed
   * @param {boolean} success - Whether the item loaded successfully
   */
  function updateProgress(itemName, success = true) {
    loadedCount.value++
    currentItem.value = itemName
    message.value = `Loading item ${loadedCount.value} of ${totalCount.value}`
    
    if (!success) {
      errors.value.push(itemName)
    }
  }
  
  /**
   * Add an error message
   * @param {string} errorMessage - Error message to add
   */
  function addError(errorMessage) {
    errors.value.push(errorMessage)
  }
  
  /**
   * Cancel the loading operation
   */
  function cancelLoading() {
    isCancelling.value = true
    if (abortController.value) {
      abortController.value.abort()
    }
  }
  
  /**
   * Complete the loading operation
   * @param {string} finalMessage - Final message to display
   */
  function completeLoading(finalMessage = 'Complete') {
    message.value = finalMessage
    currentItem.value = ''
    
    // Auto-close after a short delay if successful
    if (errors.value.length === 0) {
      setTimeout(() => {
        isLoading.value = false
      }, 1000)
    }
  }
  
  /**
   * Reset all loading state
   */
  function resetLoading() {
    isLoading.value = false
    loadedCount.value = 0
    totalCount.value = 0
    currentItem.value = ''
    message.value = ''
    errors.value = []
    isCancelling.value = false
    abortController.value = null
  }
  
  /**
   * Check if loading was cancelled
   * @returns {boolean}
   */
  function isCancelled() {
    return abortController.value?.signal.aborted || false
  }
  
  return {
    // State
    isLoading,
    loadedCount,
    totalCount,
    currentItem,
    message,
    errors,
    isCancelling,
    progress,
    successRate,
    
    // Methods
    startLoading,
    updateProgress,
    addError,
    cancelLoading,
    completeLoading,
    resetLoading,
    isCancelled,
    
    // Abort controller for external use
    abortController
  }
}
</template>