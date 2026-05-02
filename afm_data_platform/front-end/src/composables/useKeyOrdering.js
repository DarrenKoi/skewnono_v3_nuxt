import { ref, computed } from 'vue'

export function useKeyOrdering() {
  // Default key order for result display
  const defaultKeyOrder = ref([
    'filename',
    'recipe_name', 
    'lot_id',
    'slot_number',
    'measured_info',
    'formatted_date',
    'tool_name'
  ])
  
  // User-customizable key order
  const customKeyOrder = ref([...defaultKeyOrder.value])
  
  // Available keys that can be ordered (will be populated dynamically)
  const availableKeys = ref([])
  
  // Update available keys based on measurement data
  const updateAvailableKeys = (measurementData) => {
    if (!measurementData || measurementData.length === 0) {
      availableKeys.value = []
      return
    }
    
    // Get all unique keys from the measurements
    const keySet = new Set()
    measurementData.forEach(measurement => {
      Object.keys(measurement).forEach(key => {
        // Exclude complex objects and focus on display-friendly keys
        if (typeof measurement[key] !== 'object' || measurement[key] === null) {
          keySet.add(key)
        }
      })
    })
    
    availableKeys.value = Array.from(keySet).sort()
    
    // Update custom order to include any new keys not in the default order
    const newKeys = availableKeys.value.filter(key => 
      !customKeyOrder.value.includes(key)
    )
    customKeyOrder.value = [...customKeyOrder.value, ...newKeys]
    
    console.log('📋 Key ordering: Available keys updated:', availableKeys.value)
    console.log('📋 Key ordering: Custom order updated:', customKeyOrder.value)
  }
  
  // Apply custom ordering to measurement data for display
  const applyKeyOrdering = (measurementData) => {
    if (!measurementData || measurementData.length === 0) return []
    
    return measurementData.map(measurement => {
      const orderedMeasurement = {}
      
      // Add keys in the custom order first
      customKeyOrder.value.forEach(key => {
        if (key in measurement) {
          orderedMeasurement[key] = measurement[key]
        }
      })
      
      // Add any remaining keys that weren't in the custom order
      Object.keys(measurement).forEach(key => {
        if (!(key in orderedMeasurement)) {
          orderedMeasurement[key] = measurement[key]
        }
      })
      
      return orderedMeasurement
    })
  }
  
  // Move a key up in the ordering
  const moveKeyUp = (keyName) => {
    const index = customKeyOrder.value.indexOf(keyName)
    if (index > 0) {
      const newOrder = [...customKeyOrder.value]
      const [removed] = newOrder.splice(index, 1)
      newOrder.splice(index - 1, 0, removed)
      customKeyOrder.value = newOrder
      console.log(`📋 Moved "${keyName}" up in ordering`)
    }
  }
  
  // Move a key down in the ordering
  const moveKeyDown = (keyName) => {
    const index = customKeyOrder.value.indexOf(keyName)
    if (index >= 0 && index < customKeyOrder.value.length - 1) {
      const newOrder = [...customKeyOrder.value]
      const [removed] = newOrder.splice(index, 1)
      newOrder.splice(index + 1, 0, removed)
      customKeyOrder.value = newOrder
      console.log(`📋 Moved "${keyName}" down in ordering`)
    }
  }
  
  // Reset to default ordering
  const resetToDefault = () => {
    customKeyOrder.value = [...defaultKeyOrder.value]
    
    // Add any additional keys that weren't in the default
    const additionalKeys = availableKeys.value.filter(key => 
      !defaultKeyOrder.value.includes(key)
    )
    customKeyOrder.value = [...customKeyOrder.value, ...additionalKeys]
    
    console.log('📋 Reset key ordering to default')
  }
  
  // Set a completely custom order
  const setCustomOrder = (newOrder) => {
    if (Array.isArray(newOrder)) {
      customKeyOrder.value = [...newOrder]
      console.log('📋 Set custom key ordering:', newOrder)
    }
  }
  
  // Get display-friendly name for a key
  const getKeyDisplayName = (keyName) => {
    const displayNames = {
      'filename': 'File Name',
      'recipe_name': 'Recipe',
      'lot_id': 'Lot ID',
      'slot_number': 'Slot',
      'measured_info': 'Measurement',
      'formatted_date': 'Date',
      'tool_name': 'Tool',
      'date': 'Raw Date',
      'id': 'ID',
      'info': 'Info',
      'data_status': 'Status Data',
      'data_detail': 'Detail Data'
    }
    
    return displayNames[keyName] || keyName
  }
  
  // Computed property for ordered keys with display names
  const orderedKeysForDisplay = computed(() => {
    return customKeyOrder.value.map(key => ({
      key,
      displayName: getKeyDisplayName(key),
      isDefault: defaultKeyOrder.value.includes(key)
    }))
  })
  
  return {
    defaultKeyOrder,
    customKeyOrder,
    availableKeys,
    orderedKeysForDisplay,
    updateAvailableKeys,
    applyKeyOrdering,
    moveKeyUp,
    moveKeyDown,
    resetToDefault,
    setCustomOrder,
    getKeyDisplayName
  }
}