<template>
  <v-card elevation="3" min-height="450">
    <v-card-title class="py-2">
      <v-icon start size="small">mdi-image-multiple</v-icon>
      <span class="text-subtitle-1">Additional Images</span>
      <v-spacer />
    </v-card-title>
    <v-card-text class="pa-0">
      <v-tabs v-model="selectedTab" align-tabs="start" color="primary" show-arrows>
        <v-tab v-for="tab in imageTabs" :key="tab.value" :value="tab.value">
          <v-icon start size="small">{{ tab.icon }}</v-icon>
          {{ tab.title }}
          <v-chip v-if="getImagesForTab(tab.value).length > 0" size="x-small" class="ml-2" color="primary">
            {{ getImagesForTab(tab.value).length }}
          </v-chip>
        </v-tab>
        
        <!-- Download All Button for Active Tab -->
        <template v-slot:extension>
          <div class="d-flex justify-end align-center pa-2">
            <v-btn
              v-if="getImagesForTab(selectedTab).length > 0"
              @click="downloadAllImagesForTab(selectedTab)"
              :loading="isDownloadingTab[selectedTab]"
              size="small"
              variant="outlined"
              color="success"
              class="download-tab-btn"
            >
              <v-icon start size="small">mdi-download</v-icon>
              Download All ({{ getImagesForTab(selectedTab).length }})
            </v-btn>
          </div>
        </template>
      </v-tabs>

      <v-tabs-window v-model="selectedTab">
        <v-tabs-window-item v-for="tab in imageTabs" :key="tab.value" :value="tab.value">
          <v-container>
            <div v-if="isLoading" class="text-center pa-8">
              <v-progress-circular indeterminate color="primary" />
              <p class="mt-4">Loading {{ tab.title }} images...</p>
            </div>

            <div v-else-if="loadError" class="text-center pa-8">
              <v-icon size="64" color="error">mdi-alert-circle</v-icon>
              <p class="mt-4 text-h6">Error loading images</p>
              <p class="text-body-2 text-grey">{{ loadError }}</p>
              <v-btn @click="loadImages" variant="text" color="primary" class="mt-4">
                <v-icon start>mdi-refresh</v-icon>
                Retry
              </v-btn>
            </div>

            <div v-else-if="getImagesForTab(tab.value).length === 0" class="text-center pa-8">
              <v-icon size="64" color="grey-lighten-1">{{ tab.emptyIcon }}</v-icon>
              <p class="mt-4 text-h6 text-grey">No {{ tab.title }} images available</p>
              <p class="text-body-2 text-grey">{{ tab.description }}</p>
            </div>

            <div v-else class="image-gallery">
              <div class="image-container" v-for="(image, index) in getImagesForTab(tab.value)" :key="index">
                <div class="image-wrapper">
                  <v-card class="image-card" @mouseenter="hoveredImage[index] = true"
                    @mouseleave="hoveredImage[index] = false">
                    <v-img :src="image.url" :alt="image.name" height="220" width="320" cover class="image-hover">
                      <template v-slot:placeholder>
                        <v-row class="fill-height ma-0" align="center" justify="center">
                          <v-progress-circular indeterminate color="grey-lighten-5" />
                        </v-row>
                      </template>
                    </v-img>
                    <v-overlay v-model="hoveredImage[index]" :scrim="false" contained
                      class="align-center justify-center" @click="openImageDialog(image)">
                      <v-btn icon="mdi-magnify-plus-outline" color="white" size="large" variant="flat"
                        class="expand-button" />
                    </v-overlay>
                  </v-card>
                  <div class="image-info">
                    <p class="text-caption text-truncate mb-0">{{ image.name }}</p>
                    <v-btn size="x-small" variant="text" color="primary" @click="openImageDialog(image)" class="mt-1">
                      <v-icon start size="x-small">mdi-arrow-expand</v-icon>
                      View Original
                    </v-btn>
                  </div>
                </div>
              </div>
            </div>
          </v-container>
        </v-tabs-window-item>
      </v-tabs-window>
    </v-card-text>

    <!-- Image Dialog for Full View -->
    <v-dialog v-model="imageDialog" max-width="90%" max-height="90vh">
      <v-card>
        <v-card-title class="d-flex align-center">
          {{ selectedImage?.name }}
          <v-spacer />
          <v-btn icon variant="plain" @click="imageDialog = false">
            <v-icon>mdi-close</v-icon>
          </v-btn>
        </v-card-title>
        <v-card-text class="pa-0">
          <v-img v-if="selectedImage" :src="selectedImage.url" :alt="selectedImage.name" max-height="80vh" contain />
        </v-card-text>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import { useDataStore } from '@/stores/dataStore'
import { imageService } from '@/services/imageService'
import { downloadSingleImage } from '@/utils/imageDownloadUtils'

// Props
const props = defineProps({
  filename: {
    type: String,
    required: true
  }
})

// Store
const dataStore = useDataStore()

// State
const selectedTab = ref('align')
const isLoading = ref(false)
const loadError = ref('')
const imageDialog = ref(false)
const selectedImage = ref(null)
const hoveredImage = ref({})
const isDownloadingTab = ref({
  align: false,
  tip: false,
  capture: false
})

// Images data structure - start with empty arrays to avoid network errors
const imagesData = ref({
  align: [],
  tip: [],
  capture: [],
})

// Tab configuration
const imageTabs = [
  {
    value: 'align',
    title: 'Alignment Images',
    icon: 'mdi-axis-arrow',
    emptyIcon: 'mdi-axis-arrow',
    description: 'Alignment images from the wafer'
  },
  {
    value: 'tip',
    title: 'Tip Condition',
    icon: 'mdi-needle',
    emptyIcon: 'mdi-needle',
    description: 'AFM tip condition images'
  },
  {
    value: 'capture',
    title: 'Result Analysis',
    icon: 'mdi-chart-box-outline',
    emptyIcon: 'mdi-chart-box-outline',
    description: 'Result analysis images'
  }
]

// Computed
const getImagesForTab = computed(() => {
  return (tabValue) => imagesData.value[tabValue] || []
})

// Methods
async function loadImages() {
  isLoading.value = true
  loadError.value = ''

  try {
    const tool = dataStore.selectedTool
    
    // Get the selected AFM file data to access directory lists
    const selectedFile = dataStore.selectedAfmFile

    if (!selectedFile) {
      console.warn('No selected AFM file found')
      return
    }

    // Map the directory lists to image types
    const dirListMappings = {
      'align': selectedFile.align_dir_list || ["no files"],
      'tip': selectedFile.tip_dir_list || ["no files"],
      'capture': selectedFile.capture_dir_list || ["no files"]
    }

    // Process each image type
    for (const [type, fileList] of Object.entries(dirListMappings)) {
      if (fileList && fileList.length > 0 && fileList[0] !== "no files") {
        // Files are available - transform to include full URLs
        imagesData.value[type] = fileList.map(imageName => ({
          name: imageName,
          url: imageService.getImageUrlByType(props.filename, 'default', type, imageName, tool)
        }))
      } else {
        // No files available
        imagesData.value[type] = []
      }
    }

  } catch (error) {
    console.error('Error loading images:', error)
    loadError.value = error.message || 'Failed to load images'
  } finally {
    isLoading.value = false
  }
}

function openImageDialog(image) {
  selectedImage.value = image
  imageDialog.value = true
}

// Download all images for a specific tab individually
async function downloadAllImagesForTab(tabValue) {
  const images = getImagesForTab.value(tabValue)
  
  if (!images || images.length === 0) {
    console.warn(`No images available for tab: ${tabValue}`)
    return
  }

  // Set loading state for this tab
  isDownloadingTab.value[tabValue] = true

  try {
    let successCount = 0
    let failCount = 0
    
    // Download each image individually with a small delay to avoid overwhelming the browser
    for (let i = 0; i < images.length; i++) {
      const image = images[i]
      
      try {
        // Create a prefixed filename to keep downloads organized
        const prefixedFilename = `${props.filename.replace(/\.(pkl|pickle)$/i, '')}_${tabValue}_${image.name}`
        
        await downloadSingleImage(image.url, prefixedFilename)
        successCount++
        
        // Add small delay between downloads to prevent browser issues
        if (i < images.length - 1) {
          await new Promise(resolve => setTimeout(resolve, 200))
        }
        
      } catch (error) {
        console.error(`Failed to download image ${image.name}:`, error)
        failCount++
      }
    }
    
    // Log results
    if (failCount > 0) {
      console.warn(`Downloaded ${successCount}/${images.length} images. ${failCount} images failed.`)
      alert(`Downloaded ${successCount} images successfully. ${failCount} images failed to download.`)
    } else {
      console.log(`Successfully downloaded all ${successCount} images from ${tabValue} tab`)
    }
    
  } catch (error) {
    console.error(`Error downloading images for ${tabValue} tab:`, error)
    alert(`Failed to download images: ${error.message}`)
  } finally {
    // Clear loading state
    isDownloadingTab.value[tabValue] = false
  }
}

// Watchers
watch(() => props.filename, (newFilename) => {
  if (newFilename) {
    loadImages()
  }
})

// Also watch for changes in selectedAfmFile from store
watch(() => dataStore.selectedAfmFile, (newFile) => {
  if (newFile) {
    loadImages()
  }
})

// Lifecycle
onMounted(() => {
  loadImages()
})
</script>

<style scoped>
.image-gallery {
  display: flex;
  overflow-x: auto;
  gap: 16px;
  padding: 16px;
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 0, 0, 0.2) transparent;
}

.image-gallery::-webkit-scrollbar {
  height: 8px;
}

.image-gallery::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.05);
  border-radius: 4px;
}

.image-gallery::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.2);
  border-radius: 4px;
}

.image-gallery::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}

.image-container {
  flex: 0 0 auto;
}

.image-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.image-card {
  position: relative;
  cursor: pointer;
  transition: all 0.3s ease;
  overflow: hidden;
}

.image-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.image-hover {
  transition: transform 0.3s ease;
}

.image-card:hover .image-hover {
  transform: scale(1.05);
}

.image-info {
  text-align: center;
  padding: 0 8px;
}

.expand-button {
  background: rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(4px);
}

.expand-button:hover {
  background: rgba(0, 0, 0, 0.85);
  transform: scale(1.1);
}

:deep(.v-overlay__content) {
  pointer-events: all;
}

:deep(.v-tabs) {
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.12);
}

:deep(.v-tab) {
  text-transform: none;
  font-weight: 500;
}

:deep(.v-tabs-window) {
  min-height: 380px;
}

.download-tab-btn {
  margin-left: auto;
}

:deep(.v-tabs-extension) {
  background-color: rgba(var(--v-theme-surface), 0.8);
  border-bottom: 1px solid rgba(var(--v-theme-outline), 0.12);
}
</style>
