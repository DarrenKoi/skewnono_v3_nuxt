<template>
  <div class="px-2">
    <!-- Search Card -->
    <v-card class="pa-6 mb-4" elevation="3">
      <v-card-text>
        <v-text-field v-model="realtimeSearch.searchQuery.value" clearable label="Search AFM files..."
          placeholder="Search by Lot ID, Recipe, Date... (e.g., CMP, T7HQR42TA, ETCH, 250609)"
          prepend-inner-icon="mdi-magnify" variant="outlined" 
          aria-label="Search AFM files"
          @keyup.enter="triggerInstantSearch">
          <!-- Recent search terms dropdown (instead of suggestions) -->
          <template v-if="recentSearchTerms.length > 0 && !realtimeSearch.searchQuery.value" #append>
            <v-menu v-model="showRecent" offset-y>
              <template #activator="{ props }">
                <v-btn v-bind="props" icon="mdi-history" variant="text" size="small"
                  aria-label="Show recent searches"
                  @click="showRecent = !showRecent" />
              </template>
              <v-list max-height="250">
                <v-list-subheader>Recent Searches</v-list-subheader>
                <v-list-item v-for="term in recentSearchTerms" :key="term" @click="selectRecentTerm(term)">
                  <template v-slot:prepend>
                    <v-icon size="small">mdi-history</v-icon>
                  </template>
                  <v-list-item-title>{{ term }}</v-list-item-title>
                </v-list-item>

                <v-divider v-if="recentSearchTerms.length > 0" />

                <v-list-item @click="clearRecentTerms" class="text-caption">
                  <template v-slot:prepend>
                    <v-icon size="small" color="error">mdi-delete</v-icon>
                  </template>
                  <v-list-item-title class="text-error">Clear Recent Searches</v-list-item-title>
                </v-list-item>
              </v-list>
            </v-menu>
          </template>
        </v-text-field>

        <!-- Real-time search indicator -->
        <div v-if="realtimeSearch.isSearching.value" class="text-center mt-2">
          <v-progress-linear indeterminate color="primary" height="2" />
          <p class="text-caption text-medium-emphasis mt-1">Searching...</p>
        </div>

        <!-- Search helper text -->
        <div v-if="realtimeSearch.searchQuery.value && realtimeSearch.searchQuery.value.length === 1"
          class="text-center mt-2">
          <p class="text-caption text-medium-emphasis">
            Type one more character to start searching...
          </p>
        </div>

        <!-- Search stats -->
        <div
          v-if="realtimeSearch.searchResults.value.length > 0 && realtimeSearch.searchQuery.value && realtimeSearch.searchQuery.value.length >= 2"
          class="text-center mt-2">
          <p class="text-caption text-medium-emphasis">
            Found {{ realtimeSearch.searchResults.value.length }} results
            <v-icon size="x-small" color="success">mdi-check-circle</v-icon>
          </p>
        </div>

        <!-- No results message -->
        <div
          v-if="realtimeSearch.searchResults.value.length === 0 && realtimeSearch.searchQuery.value && realtimeSearch.searchQuery.value.length >= 2 && !realtimeSearch.isSearching.value"
          class="text-center mt-2">
          <p class="text-caption text-medium-emphasis">
            No results found for "{{ realtimeSearch.searchQuery.value }}"
            <v-icon size="x-small" color="warning">mdi-alert-circle</v-icon>
          </p>
        </div>
      </v-card-text>
    </v-card>

    <!-- Search Results -->
    <v-card v-if="realtimeSearch.searchResults.value.length > 0" elevation="3">
      <v-card-title class="d-flex align-center">
        <v-icon start>mdi-database-search</v-icon>
        {{ realtimeSearch.searchQuery.value ? 'Search Results' : 'Recent Measurements' }}
        ({{ filteredResults.length }}{{ filteredResults.length !== realtimeSearch.searchResults.value.length ?
          `/${realtimeSearch.searchResults.value.length}` : '' }})

        <v-spacer />

        <!-- Inner filter input -->
        <v-text-field v-model="innerFilter" density="compact" variant="outlined" placeholder="Filter results..."
          prepend-inner-icon="mdi-filter" clearable hide-details 
          aria-label="Filter search results"
          style="max-width: 300px;" class="ml-4" />
      </v-card-title>
      <v-divider />

      <!-- Results list with scrollable container -->
      <div class="results-container" :class="{ 'scrollable': filteredResults.length > maxVisibleItems }">
        <v-list>
          <v-list-item v-for="(result, index) in displayedResults" :key="index" class="border-b py-3">
            <v-row class="align-center" no-gutters>
              <!-- Left Column: Main Information -->
              <v-col cols="5" class="pr-2">
                <div class="d-flex flex-column">
                  <div class="font-weight-bold text-body-1 mb-1">
                    📅 {{ result.formatted_date }}
                  </div>
                  <div class="font-weight-bold text-body-1 mb-1">
                    🔬 {{ result.recipe_name }}
                  </div>
                  <div class="font-weight-bold text-body-1 mb-2">
                    📦 {{ result.lot_id }}
                    <v-chip v-if="isInGroup(result.filename)" size="x-small" color="success" class="ml-2">
                      GROUPED
                    </v-chip>
                  </div>
                </div>
                <v-list-item-subtitle class="mt-2">
                  <v-chip size="small" color="primary" variant="outlined" class="mr-2 font-weight-medium">Slot: {{
                    result.slot_number }}</v-chip>
                  <v-chip size="small" color="secondary" variant="outlined" class="mr-2 font-weight-medium">{{
                    result.measured_info }}</v-chip>
                </v-list-item-subtitle>
              </v-col>

              <!-- Middle Column: Data Availability -->
              <v-col cols="2" class="text-center">
                <div class="d-flex flex-column align-center justify-center">
                  <!-- Available data row -->
                  <div class="d-flex flex-column align-center mb-2">
                    <div class="d-flex align-center mb-1">
                      <v-icon size="small" color="success" class="availability-indicator">mdi-check-circle</v-icon>
                      <span class="text-caption text-success ml-1 font-weight-medium">Available</span>
                    </div>
                    <div class="d-flex flex-row align-center justify-center gap-1">
                      <v-tooltip v-for="dt in dataTypes" :key="dt.key" 
                        :text="dt.tooltip" location="top"
                        v-if="dt && dt.key && hasData(result[dt.key])">
                        <template v-slot:activator="{ props }">
                          <v-icon v-bind="props" size="small" color="success">{{ dt.icon }}</v-icon>
                        </template>
                      </v-tooltip>
                    </div>
                  </div>

                  <!-- Divider -->
                  <v-divider class="my-1" style="width: 80%;"></v-divider>

                  <!-- Unavailable data row -->
                  <div class="d-flex flex-column align-center mt-2">
                    <div class="d-flex align-center mb-1">
                      <v-icon size="small" color="grey-darken-1"
                        class="availability-indicator">mdi-close-circle</v-icon>
                      <span class="text-caption text-grey-darken-1 ml-1 font-weight-medium">Not Available</span>
                    </div>
                    <div class="d-flex flex-row align-center justify-center gap-1">
                      <v-tooltip v-for="dt in dataTypes" :key="dt.key"
                        :text="dt.tooltip" location="bottom"
                        v-if="dt && dt.key && !hasData(result[dt.key])">
                        <template v-slot:activator="{ props }">
                          <v-icon v-bind="props" size="small" color="grey">{{ dt.icon }}</v-icon>
                        </template>
                      </v-tooltip>
                    </div>
                  </div>
                </div>
              </v-col>

              <!-- Right Column: Action Buttons -->
              <v-col cols="5" class="text-right">
                <div class="d-flex flex-column align-end gap-1">
                  <v-btn class='my-2' variant="outlined" size="small" color="success"
                    :disabled="isInGroup(result.filename)" 
                    :aria-label="`Add ${result.filename} to group`"
                    @click="addToGroup(result)" style="width: 140px;" dense>
                    <v-icon size="small">mdi-plus</v-icon>
                    <span class="ml-1">Add to Group</span>
                  </v-btn>
                  <v-btn variant="outlined" size="small" 
                    :aria-label="`View details for ${result.filename}`"
                    @click="viewDetails(result)" style="width: 140px;" dense>
                    View Details
                  </v-btn>
                </div>
              </v-col>
            </v-row>
          </v-list-item>
        </v-list>
      </div>

      <!-- Results counter (only show when there are many results) -->
      <div v-if="filteredResults.length > maxVisibleItems" class="text-center pa-3 border-t">
        <div class="text-caption text-medium-emphasis">
          Showing {{ displayedResults.length }} results - scroll to see more
        </div>
      </div>
    </v-card>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted, computed } from 'vue'
import { useRealtimeSearch } from '@/composables/useSearch.js'

// Props
defineProps({
  searchResults: {
    type: Array,
    default: () => []
  },
  isSearching: {
    type: Boolean,
    default: false
  },
  isInGroup: {
    type: Function,
    default: () => false
  }
})

// Emits
const emit = defineEmits(['search-performed', 'add-to-group', 'view-details'])

// Real-time search functionality
const realtimeSearch = useRealtimeSearch()
const showRecent = ref(false)

// Recent search terms functionality
const recentSearchTerms = ref([])

// Inner filter functionality
const innerFilter = ref('')

// Configuration constants
const MAX_VISIBLE_ITEMS = 10 // Show 10 items initially, then scroll for more
const MAX_RECENT_TERMS = 5 // Maximum number of recent search terms to store

// Results display configuration
const maxVisibleItems = ref(MAX_VISIBLE_ITEMS)

// Computed property to filter search results
const filteredResults = computed(() => {
  if (!innerFilter.value || innerFilter.value.trim() === '') {
    return realtimeSearch.searchResults.value
  }

  const filterQuery = innerFilter.value.toLowerCase().trim()

  return realtimeSearch.searchResults.value.filter(result => {
    // Search across multiple fields
    const searchFields = [
      result.lot_id,
      result.recipe_name,
      result.formatted_date,
      result.date,
      result.slot_number?.toString(),
      result.measured_info?.toString(),
      result.filename
    ]

    return searchFields.some(field =>
      field && field.toString().toLowerCase().includes(filterQuery)
    )
  })
})

// Computed property for displayed results (all results with scrolling)
const displayedResults = computed(() => {
  return filteredResults.value
})

// Watch for search results changes and emit to parent
const stopWatchResults = watch(realtimeSearch.searchResults, (newResults) => {
  // Clear inner filter when main search changes
  innerFilter.value = ''

  console.log(`🔍 SearchSection: Search results changed, emitting ${newResults.length} results`)
  console.log('📊 SearchSection: Sample result:', newResults[0])
  emit('search-performed', realtimeSearch.searchQuery.value, newResults)
}, { deep: true })

// Watch for filtered results changes and emit to parent
const stopWatchFiltered = watch(filteredResults, (newFilteredResults) => {
  if (innerFilter.value) {
    console.log(`🔍 SearchSection: Filtered results changed, emitting ${newFilteredResults.length} results`)
    emit('search-performed', realtimeSearch.searchQuery.value, newFilteredResults)
  }
}, { deep: true })

// Watch for search query changes to add to recent terms
const stopWatchQuery = watch(() => realtimeSearch.searchQuery.value, (newQuery, oldQuery) => {
  // Only add to recent terms if user has performed a meaningful search (not just typing)
  if (oldQuery && oldQuery.trim().length >= 2 && newQuery !== oldQuery) {
    // This will capture when user clears search or significantly changes it
    if (!newQuery || newQuery.trim().length < 2) {
      addToRecentTerms(oldQuery)
    }
  }
})

onMounted(() => {
  console.log('🚀 SearchSection: Component mounted and ready for AFM file searches')
  loadRecentTerms()

  // If there's a saved search query, it will be automatically loaded by useRealtimeSearch
  // and will trigger the search through the watcher
  if (realtimeSearch.searchQuery.value) {
    console.log(`🔄 SearchSection: Restored search query: "${realtimeSearch.searchQuery.value}"`)
  }
})

onUnmounted(() => {
  // Clean up watchers to prevent memory leaks
  stopWatchResults()
  stopWatchFiltered()
  stopWatchQuery()
})

// Helper function to check data availability
function hasData(dirList) {
  return dirList && dirList[0] !== 'no files'
}

// Data type configurations for availability display
const dataTypes = [
  { key: 'profile_dir_list', icon: 'mdi-chart-line', tooltip: 'Profile Data' },
  { key: 'data_dir_list', icon: 'mdi-database', tooltip: 'Measurement Data' },
  { key: 'tiff_dir_list', icon: 'mdi-image', tooltip: 'Profile Images' },
  { key: 'align_dir_list', icon: 'mdi-axis-arrow', tooltip: 'Alignment Images' },
  { key: 'tip_dir_list', icon: 'mdi-needle', tooltip: 'Tip Images' },
  { key: 'capture_dir_list', icon: 'mdi-chart-box-outline', tooltip: 'Analysis Images' }
]

// Functions
function triggerInstantSearch() {
  console.log(`⚡ SearchSection: Triggering instant search for "${realtimeSearch.searchQuery.value}"`)
  if (!realtimeSearch.searchQuery.value) return

  // Add to recent terms when user performs a search
  addToRecentTerms(realtimeSearch.searchQuery.value)

  realtimeSearch.triggerSearch(realtimeSearch.searchQuery.value)
}

function selectRecentTerm(term) {
  console.log(`🕒 SearchSection: Selected recent term "${term}"`)
  realtimeSearch.searchQuery.value = term
  showRecent.value = false
  triggerInstantSearch()
}

function addToRecentTerms(term) {
  if (!term || term.trim().length < 2) return

  const trimmedTerm = term.trim()

  // Remove if already exists
  const existingIndex = recentSearchTerms.value.indexOf(trimmedTerm)
  if (existingIndex > -1) {
    recentSearchTerms.value.splice(existingIndex, 1)
  }

  // Add to beginning
  recentSearchTerms.value.unshift(trimmedTerm)

  // Keep only max recent terms
  if (recentSearchTerms.value.length > MAX_RECENT_TERMS) {
    recentSearchTerms.value = recentSearchTerms.value.slice(0, MAX_RECENT_TERMS)
  }

  // Save to localStorage
  try {
    localStorage.setItem('afm_recent_searches', JSON.stringify(recentSearchTerms.value))
  } catch (error) {
    console.warn('Could not save recent searches to localStorage:', error)
  }

  console.log(`🕒 SearchSection: Added "${trimmedTerm}" to recent searches`)
}

function loadRecentTerms() {
  try {
    const saved = localStorage.getItem('afm_recent_searches')
    if (saved) {
      recentSearchTerms.value = JSON.parse(saved)
      console.log(`🕒 SearchSection: Loaded ${recentSearchTerms.value.length} recent search terms`)
    }
  } catch (error) {
    console.warn('Could not load recent searches from localStorage:', error)
    recentSearchTerms.value = []
  }
}

function clearRecentTerms() {
  recentSearchTerms.value = []
  showRecent.value = false

  try {
    localStorage.removeItem('afm_recent_searches')
    console.log('🗑️ SearchSection: Cleared all recent search terms')
  } catch (error) {
    console.warn('Could not clear recent searches from localStorage:', error)
  }
}

function addToGroup(result) {
  console.log(`➕ SearchSection: Adding to group:`, result)
  emit('add-to-group', result)
}

function viewDetails(result) {
  console.log(`👁️ SearchSection: Viewing details for:`, result)
  emit('view-details', result)
}

</script>

<style scoped>
.results-container {
  transition: max-height 0.3s ease-in-out;
}

.results-container.scrollable {
  max-height: 600px;
  overflow-y: auto;
  border-radius: 4px;
}

/* Custom scrollbar styling */
.results-container.scrollable::-webkit-scrollbar {
  width: 8px;
}

.results-container.scrollable::-webkit-scrollbar-track {
  background: #f1f1f1;
  border-radius: 4px;
}

.results-container.scrollable::-webkit-scrollbar-thumb {
  background: #c1c1c1;
  border-radius: 4px;
}

.results-container.scrollable::-webkit-scrollbar-thumb:hover {
  background: #a8a8a8;
}

/* Availability indicator styling */
.availability-indicator {
  opacity: 0.9;
  transition: all 0.2s ease;
}

.availability-indicator:hover {
  transform: scale(1.1);
  opacity: 1;
}
</style>
