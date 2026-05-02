<template>
  <v-dialog 
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    :max-width="maxWidth" 
    :persistent="persistent">
    <v-card>
      <v-card-text class="text-center pa-6">
        <!-- Progress Circle -->
        <v-progress-circular 
          :model-value="progress" 
          :indeterminate="progress === 0"
          :color="color" 
          :size="size" 
          :width="width"
          class="mb-4">
          <span v-if="progress > 0" class="text-h6 font-weight-bold">
            {{ Math.round(progress) }}%
          </span>
        </v-progress-circular>
        
        <!-- Title -->
        <h3 class="text-h5 mb-3">{{ title }}</h3>
        
        <!-- Progress Chip -->
        <v-chip 
          v-if="showCounter && total > 0" 
          :color="color" 
          variant="tonal" 
          size="small" 
          class="mb-3">
          <v-icon start size="small">{{ counterIcon }}</v-icon>
          {{ current }} of {{ total }} {{ itemLabel }}
        </v-chip>
        
        <!-- Messages -->
        <p v-if="message" class="text-body-1 mb-1">
          {{ message }}
        </p>
        
        <p v-if="detail" class="text-caption text-medium-emphasis mb-4">
          {{ detail }}
        </p>
        
        <!-- Progress Bar -->
        <v-progress-linear 
          v-if="showProgressBar"
          :model-value="progress" 
          :color="color" 
          height="6" 
          rounded
          class="mb-4" />
        
        <!-- Error Alert -->
        <v-alert 
          v-if="errors.length > 0" 
          type="warning" 
          variant="tonal" 
          density="compact"
          class="mb-4 text-left">
          <div class="text-caption">
            <strong>{{ errors.length }} {{ errorLabel }}</strong>
            <div v-if="showErrorDetails" class="mt-2">
              <div v-for="(error, idx) in errors.slice(0, maxErrorsShown)" :key="idx" class="text-truncate">
                • {{ error }}
              </div>
              <div v-if="errors.length > maxErrorsShown" class="text-medium-emphasis">
                ... and {{ errors.length - maxErrorsShown }} more
              </div>
            </div>
            <v-btn 
              v-if="errors.length > 0"
              @click="showErrorDetails = !showErrorDetails"
              variant="text" 
              size="x-small" 
              class="mt-1">
              {{ showErrorDetails ? 'Hide' : 'Show' }} Details
            </v-btn>
          </div>
        </v-alert>
      </v-card-text>
      
      <!-- Actions -->
      <v-card-actions v-if="showCancel">
        <v-spacer />
        <v-btn 
          :color="cancelColor" 
          variant="text" 
          @click="handleCancel"
          :disabled="cancelling">
          <v-icon start>mdi-close</v-icon>
          {{ cancelling ? cancellingText : cancelText }}
        </v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  /**
   * v-model binding
   */
  modelValue: {
    type: Boolean,
    required: true
  },
  /**
   * Dialog title
   */
  title: {
    type: String,
    default: 'Loading'
  },
  /**
   * Progress percentage (0-100)
   */
  progress: {
    type: Number,
    default: 0
  },
  /**
   * Current item being processed
   */
  current: {
    type: Number,
    default: 0
  },
  /**
   * Total items to process
   */
  total: {
    type: Number,
    default: 0
  },
  /**
   * Primary message
   */
  message: {
    type: String,
    default: ''
  },
  /**
   * Detail/secondary message
   */
  detail: {
    type: String,
    default: ''
  },
  /**
   * Array of error messages
   */
  errors: {
    type: Array,
    default: () => []
  },
  /**
   * Whether dialog can be closed by clicking outside
   */
  persistent: {
    type: Boolean,
    default: true
  },
  /**
   * Show cancel button
   */
  showCancel: {
    type: Boolean,
    default: true
  },
  /**
   * Whether cancellation is in progress
   */
  cancelling: {
    type: Boolean,
    default: false
  },
  /**
   * Dialog max width
   */
  maxWidth: {
    type: [String, Number],
    default: 500
  },
  /**
   * Progress circle size
   */
  size: {
    type: Number,
    default: 80
  },
  /**
   * Progress circle width
   */
  width: {
    type: Number,
    default: 8
  },
  /**
   * Color theme
   */
  color: {
    type: String,
    default: 'primary'
  },
  /**
   * Cancel button color
   */
  cancelColor: {
    type: String,
    default: 'error'
  },
  /**
   * Cancel button text
   */
  cancelText: {
    type: String,
    default: 'Cancel'
  },
  /**
   * Cancelling state text
   */
  cancellingText: {
    type: String,
    default: 'Cancelling...'
  },
  /**
   * Label for items being processed
   */
  itemLabel: {
    type: String,
    default: 'items'
  },
  /**
   * Label for errors
   */
  errorLabel: {
    type: String,
    default: 'error(s) occurred'
  },
  /**
   * Icon for counter chip
   */
  counterIcon: {
    type: String,
    default: 'mdi-file-document-multiple'
  },
  /**
   * Show progress bar
   */
  showProgressBar: {
    type: Boolean,
    default: true
  },
  /**
   * Show counter chip
   */
  showCounter: {
    type: Boolean,
    default: true
  },
  /**
   * Maximum errors to show in details
   */
  maxErrorsShown: {
    type: Number,
    default: 3
  }
})

const emit = defineEmits(['update:modelValue', 'cancel'])

const showErrorDetails = ref(false)

/**
 * Handle cancel button click
 */
function handleCancel() {
  emit('cancel')
}
</script>