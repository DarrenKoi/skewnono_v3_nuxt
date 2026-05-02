# AFM Data Platform Web Development Tutorial

## Introduction

This comprehensive tutorial is designed for engineers at SK hynix who want to learn web development through building the AFM (Atomic Force Microscopy) data platform. As a progressive learning guide, it combines practical examples with fundamental concepts to help non-developers understand modern web development.

## Target Audience

- Engineers with minimal web development experience
- Technical professionals interested in data visualization
- Team members working with AFM equipment data
- Anyone wanting to understand the AFM data platform architecture

## Learning Path Overview

This tutorial is structured as a progressive 3-chapter journey:

1. **Chapter 1: Web Development Foundations** - Understanding web basics and setting up your development environment
2. **Chapter 2: Vue.js Fundamentals** - Mastering modern JavaScript framework concepts through AFM examples
3. **Chapter 3: Professional UI with Vuetify** - Creating polished interfaces for data visualization

---

# Chapter 1: Web Development Foundations

## Understanding Web Development

### The Restaurant Analogy

Think of web development like running a restaurant:

- **Frontend (프론트엔드)** = Dining area where customers interact
  - Beautiful interior design (CSS)
  - Menu and table layout (HTML)
  - Interactive service (JavaScript)

- **Backend (백엔드)** = Kitchen where food is prepared
  - Recipes and cooking processes (Business logic)
  - Ingredient storage (Database)
  - Order processing (API endpoints)

In our AFM data platform:
- **Frontend**: Vue.js application displaying measurement data and charts
- **Backend**: Python/Flask server processing AFM files and serving API data

### Web Technology Building Blocks

#### HTML - The Structure
HTML (HyperText Markup Language) provides the basic structure, like building framework:

```html
<!DOCTYPE html>
<html>
<head>
    <title>AFM Data Platform</title>
</head>
<body>
    <h1>Measurement Results</h1>
    <div class="measurement-card">
        <p>Roughness: 2.3 nm</p>
        <p>Date: 2024-06-18</p>
    </div>
</body>
</html>
```

#### CSS - The Styling
CSS (Cascading Style Sheets) makes it look professional:

```css
.measurement-card {
    border: 1px solid #ccc;
    border-radius: 8px;
    padding: 16px;
    margin: 8px;
    background-color: #f9f9f9;
}
```

#### JavaScript - The Interaction
JavaScript adds dynamic behavior:

```javascript
function updateMeasurement(newValue) {
    document.getElementById('roughness').textContent = newValue + ' nm';
}
```

### Why Vue.js for AFM Platform?

Vue.js is a **progressive framework** - you can adopt it gradually:

1. **Easy Learning Curve**: Gentle introduction for beginners
2. **Component-Based**: Build reusable measurement cards, charts, and controls
3. **Reactive**: Automatically updates UI when AFM data changes
4. **Great Ecosystem**: Works well with Vuetify for beautiful interfaces

## Setting Up Development Environment

### Node.js Installation

Node.js is like having a JavaScript engine on your computer (not just in browsers):

1. Download from [nodejs.org](https://nodejs.org)
2. Install the LTS version (Long Term Support)
3. Verify installation:

```bash
node --version
npm --version
```

### Creating Your First Vue Project

Use Vite (next-generation build tool) for fast development:

```bash
# Create new Vue project
npm create vue@latest afm-data-platform

# Navigate to project
cd afm-data-platform

# Install dependencies
npm install

# Start development server
npm run dev
```

### VS Code Setup

Install these essential extensions:
- **Vue - Official**: Vue.js language support
- **Vetur**: Vue tooling (if using older setup)
- **Prettier**: Code formatting
- **Auto Rename Tag**: HTML tag synchronization

### Project Structure Understanding

```
afm-data-platform/
├── src/
│   ├── components/     # Reusable UI components
│   ├── pages/         # Page components
│   ├── stores/        # State management
│   ├── services/      # API communication
│   └── assets/        # Images, logos
├── public/            # Static files
└── package.json       # Project configuration
```

### Development Server

The development server provides:
- **Hot Module Replacement (HMR)**: See changes instantly
- **Live Reload**: Automatic browser refresh
- **Error Overlay**: Clear error messages
- **Fast Compilation**: Optimized build process

---

# Chapter 2: Vue.js Fundamentals

## Introduction to Vue.js

Vue.js is designed to be **approachable** and **progressive**. Unlike other frameworks that require learning everything upfront, Vue allows you to start simple and gradually add complexity.

### Core Concepts Overview

Think of Vue components like **LEGO blocks** for web development:
- Each component is self-contained
- Components can be combined to build complex interfaces
- Reusable across different parts of your application

## Template Syntax and Data Binding

### Basic Template Syntax

Vue uses HTML-based template syntax with special directives:

```vue
<template>
  <div class="afm-measurement">
    <!-- Text Interpolation -->
    <h2>{{ measurementTitle }}</h2>
    
    <!-- Attribute Binding -->
    <img :src="imageUrl" :alt="imageDescription" />
    
    <!-- Event Handling -->
    <button @click="startMeasurement">Start Scan</button>
    
    <!-- Conditional Rendering -->
    <div v-if="isScanning">
      <p>Scanning in progress...</p>
      <progress :value="scanProgress" max="100"></progress>
    </div>
    
    <!-- List Rendering -->
    <ul>
      <li v-for="point in measurementPoints" :key="point.id">
        Point {{ point.id }}: {{ point.roughness }}nm
      </li>
    </ul>
  </div>
</template>
```

### Reactivity System

Vue's reactivity system automatically updates the UI when data changes:

```vue
<script setup>
import { ref, computed } from 'vue'

// Reactive data
const measurements = ref([])
const isScanning = ref(false)
const scanProgress = ref(0)

// Computed properties (automatically calculated)
const averageRoughness = computed(() => {
  if (measurements.value.length === 0) return 0
  const sum = measurements.value.reduce((acc, m) => acc + m.roughness, 0)
  return (sum / measurements.value.length).toFixed(2)
})

const qualityGrade = computed(() => {
  const avg = parseFloat(averageRoughness.value)
  if (avg < 1.0) return 'Excellent'
  if (avg < 2.0) return 'Good'
  if (avg < 3.0) return 'Fair'
  return 'Poor'
})

// Methods
function startMeasurement() {
  isScanning.value = true
  scanProgress.value = 0
  
  // Simulate scanning process
  const interval = setInterval(() => {
    scanProgress.value += 10
    if (scanProgress.value >= 100) {
      clearInterval(interval)
      isScanning.value = false
      addMeasurementPoint()
    }
  }, 500)
}

function addMeasurementPoint() {
  const newPoint = {
    id: Date.now(),
    roughness: (Math.random() * 5).toFixed(2),
    timestamp: new Date().toLocaleString()
  }
  measurements.value.push(newPoint)
}
</script>
```

## Component Architecture

### Creating Reusable Components

Components are the heart of Vue applications. Here's a practical AFM measurement card component:

```vue
<!-- MeasurementCard.vue -->
<template>
  <div class="measurement-card" :class="gradeClass">
    <div class="card-header">
      <h3>{{ title }}</h3>
      <span class="grade-badge">{{ grade }}</span>
    </div>
    
    <div class="card-content">
      <div class="measurement-item">
        <label>Roughness:</label>
        <span class="value">{{ roughness }} nm</span>
      </div>
      
      <div class="measurement-item">
        <label>Date:</label>
        <span class="value">{{ formattedDate }}</span>
      </div>
      
      <div class="measurement-item">
        <label>Recipe:</label>
        <span class="value">{{ recipe }}</span>
      </div>
    </div>
    
    <div class="card-actions">
      <button @click="viewDetails" class="btn-primary">
        View Details
      </button>
      <button @click="exportData" class="btn-secondary">
        Export
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

// Props (data passed from parent)
const props = defineProps({
  title: { type: String, required: true },
  roughness: { type: Number, required: true },
  date: { type: String, required: true },
  recipe: { type: String, required: true }
})

// Emits (events sent to parent)
const emit = defineEmits(['view-details', 'export-data'])

// Computed properties
const grade = computed(() => {
  if (props.roughness < 1.0) return 'Excellent'
  if (props.roughness < 2.0) return 'Good'
  if (props.roughness < 3.0) return 'Fair'
  return 'Poor'
})

const gradeClass = computed(() => ({
  'grade-excellent': grade.value === 'Excellent',
  'grade-good': grade.value === 'Good',
  'grade-fair': grade.value === 'Fair',
  'grade-poor': grade.value === 'Poor'
}))

const formattedDate = computed(() => {
  return new Date(props.date).toLocaleDateString('ko-KR')
})

// Methods
function viewDetails() {
  emit('view-details', {
    title: props.title,
    roughness: props.roughness,
    date: props.date,
    recipe: props.recipe
  })
}

function exportData() {
  emit('export-data', props.title)
}
</script>

<style scoped>
.measurement-card {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 16px;
  margin: 8px;
  background: white;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  transition: box-shadow 0.3s ease;
}

.measurement-card:hover {
  box-shadow: 0 4px 8px rgba(0,0,0,0.15);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.grade-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
}

.grade-excellent .grade-badge { background: #4caf50; color: white; }
.grade-good .grade-badge { background: #8bc34a; color: white; }
.grade-fair .grade-badge { background: #ff9800; color: white; }
.grade-poor .grade-badge { background: #f44336; color: white; }

.measurement-item {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
}

.card-actions {
  margin-top: 16px;
  display: flex;
  gap: 8px;
}

.btn-primary, .btn-secondary {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary {
  background: #1976d2;
  color: white;
}

.btn-secondary {
  background: #f5f5f5;
  color: #333;
}
</style>
```

### Using Components

```vue
<!-- Parent component -->
<template>
  <div class="measurements-dashboard">
    <h1>AFM Measurements Dashboard</h1>
    
    <div class="measurements-grid">
      <MeasurementCard
        v-for="measurement in measurements"
        :key="measurement.id"
        :title="measurement.title"
        :roughness="measurement.roughness"
        :date="measurement.date"
        :recipe="measurement.recipe"
        @view-details="handleViewDetails"
        @export-data="handleExportData"
      />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import MeasurementCard from './components/MeasurementCard.vue'

const measurements = ref([
  {
    id: 1,
    title: 'FSOXCMP_DISHING_9PT',
    roughness: 1.2,
    date: '2024-06-18',
    recipe: 'T7HQR42TA'
  },
  {
    id: 2,
    title: 'OXIDE_ETCH_3PT',
    roughness: 2.8,
    date: '2024-06-17',
    recipe: 'T8HQR43TB'
  }
])

function handleViewDetails(data) {
  console.log('Viewing details for:', data.title)
  // Navigate to details page or open modal
}

function handleExportData(title) {
  console.log('Exporting data for:', title)
  // Trigger data export
}
</script>
```

## Advanced Vue Concepts

### Watchers for Real-time Monitoring

Watchers allow you to react to data changes, perfect for AFM equipment monitoring:

```vue
<script setup>
import { ref, watch } from 'vue'

const scanSpeed = ref(50)
const temperature = ref(25)
const speedWarning = ref('')
const temperatureAlert = ref('')

// Watch single value
watch(scanSpeed, (newSpeed, oldSpeed) => {
  console.log(`Speed changed from ${oldSpeed} to ${newSpeed}`)
  
  if (newSpeed > 100) {
    speedWarning.value = "Warning: Speed too high! Risk of tip damage."
  } else if (newSpeed < 10) {
    speedWarning.value = "Warning: Speed too low! Scan will take too long."
  } else {
    speedWarning.value = ""
  }
})

// Watch multiple values
watch([temperature, scanSpeed], ([newTemp, newSpeed], [oldTemp, oldSpeed]) => {
  // Complex monitoring logic
  if (newTemp > 30 && newSpeed > 80) {
    temperatureAlert.value = "Critical: High temperature + high speed detected!"
  } else {
    temperatureAlert.value = ""
  }
})

// Immediate execution
watch(temperature, (temp) => {
  if (temp > 35) {
    // Emergency stop logic
    console.log('Emergency stop triggered!')
  }
}, { immediate: true })
</script>
```

### Lifecycle Hooks

Understand when components are created, updated, and destroyed:

```vue
<script setup>
import { onMounted, onUnmounted, onUpdated } from 'vue'

let measurementInterval = null

// Called when component is mounted to DOM
onMounted(() => {
  console.log('AFM Component mounted - initializing equipment connection')
  
  // Start real-time data collection
  measurementInterval = setInterval(() => {
    collectMeasurementData()
  }, 1000)
  
  // Initialize WebSocket connection for real-time updates
  initializeWebSocket()
})

// Called when component is updated
onUpdated(() => {
  console.log('Component updated - measurement data refreshed')
})

// Called before component is destroyed
onUnmounted(() => {
  console.log('AFM Component unmounted - cleaning up connections')
  
  // Clear intervals
  if (measurementInterval) {
    clearInterval(measurementInterval)
  }
  
  // Close WebSocket connections
  closeWebSocket()
  
  // Stop equipment operations
  stopMeasurement()
})

function collectMeasurementData() {
  // Simulate real-time data collection
  const newData = {
    timestamp: Date.now(),
    roughness: Math.random() * 5,
    temperature: 25 + Math.random() * 10
  }
  
  measurements.value.push(newData)
}
</script>
```

---

# Chapter 3: Professional UI with Vuetify

## Introduction to Vuetify

Vuetify is a Vue.js component framework that implements Google's Material Design. It provides:

- **Pre-built Components**: Cards, buttons, forms, navigation
- **Responsive Grid System**: Mobile-first design approach
- **Consistent Theming**: Professional appearance out of the box
- **Accessibility**: Built-in accessibility features

### Installation and Setup

```bash
# Install Vuetify
npm install vuetify

# Install Material Design Icons
npm install @mdi/font
```

Configure Vuetify in your main.js:

```javascript
import { createApp } from 'vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import '@mdi/font/css/materialdesignicons.css'
import 'vuetify/styles'

import App from './App.vue'

const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: 'light',
    themes: {
      light: {
        colors: {
          primary: '#1976D2',
          secondary: '#424242',
          accent: '#82B1FF',
          error: '#FF5252',
          info: '#2196F3',
          success: '#4CAF50',
          warning: '#FFC107'
        }
      }
    }
  }
})

createApp(App).use(vuetify).mount('#app')
```

## Grid System and Layout

### Responsive Grid System

Vuetify uses a 12-column grid system:

```vue
<template>
  <v-container fluid>
    <!-- Dashboard Header -->
    <v-row>
      <v-col cols="12">
        <h1 class="text-h4 mb-4">AFM Data Platform Dashboard</h1>
      </v-col>
    </v-row>
    
    <!-- Statistics Cards -->
    <v-row>
      <v-col cols="12" sm="6" md="3" v-for="stat in statistics" :key="stat.title">
        <v-card class="stats-card" elevation="2">
          <v-card-text>
            <div class="d-flex align-center">
              <v-icon :color="stat.color" size="40" class="mr-4">
                {{ stat.icon }}
              </v-icon>
              <div>
                <div class="text-h5 font-weight-bold">{{ stat.value }}</div>
                <div class="text-caption text-grey">{{ stat.title }}</div>
              </div>
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
    
    <!-- Main Content Area -->
    <v-row>
      <!-- Measurement List -->
      <v-col cols="12" lg="8">
        <v-card elevation="2">
          <v-card-title class="d-flex align-center">
            <v-icon class="mr-2">mdi-chart-line</v-icon>
            Recent Measurements
            <v-spacer></v-spacer>
            <v-btn color="primary" @click="refreshData">
              <v-icon left>mdi-refresh</v-icon>
              Refresh
            </v-btn>
          </v-card-title>
          
          <v-card-text>
            <MeasurementDataTable :measurements="measurements" />
          </v-card-text>
        </v-card>
      </v-col>
      
      <!-- Equipment Status -->
      <v-col cols="12" lg="4">
        <v-card elevation="2">
          <v-card-title>
            <v-icon class="mr-2">mdi-cog</v-icon>
            Equipment Status
          </v-card-title>
          
          <v-card-text>
            <EquipmentStatusPanel :equipment="equipmentList" />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref } from 'vue'

const statistics = ref([
  {
    title: 'Total Measurements',
    value: '1,247',
    icon: 'mdi-chart-bar',
    color: 'primary'
  },
  {
    title: 'Active Tools',
    value: '3',
    icon: 'mdi-tools',
    color: 'success'
  },
  {
    title: 'Avg Roughness',
    value: '2.1 nm',
    icon: 'mdi-wave',
    color: 'info'
  },
  {
    title: 'Quality Grade',
    value: 'Good',
    icon: 'mdi-star',
    color: 'warning'
  }
])
</script>
```

## Common UI Components

### Data Tables

Create professional data tables for AFM measurements:

```vue
<template>
  <v-data-table
    :headers="headers"
    :items="measurements"
    :items-per-page="10"
    :loading="loading"
    :search="search"
    class="elevation-1"
  >
    <!-- Top toolbar -->
    <template v-slot:top>
      <v-toolbar flat>
        <v-toolbar-title>AFM Measurements</v-toolbar-title>
        <v-spacer></v-spacer>
        
        <v-text-field
          v-model="search"
          append-icon="mdi-magnify"
          label="Search measurements..."
          single-line
          hide-details
          class="mr-4"
          style="max-width: 300px;"
        ></v-text-field>
        
        <v-btn color="primary" @click="exportToExcel">
          <v-icon left>mdi-download</v-icon>
          Export
        </v-btn>
      </v-toolbar>
    </template>
    
    <!-- Custom column for roughness with color coding -->
    <template v-slot:item.roughness="{ item }">
      <v-chip
        :color="getRoughnessColor(item.roughness)"
        dark
        small
      >
        {{ item.roughness }} nm
      </v-chip>
    </template>
    
    <!-- Custom column for quality grade -->
    <template v-slot:item.quality="{ item }">
      <v-rating
        :value="getQualityRating(item.roughness)"
        color="amber"
        dense
        half-increments
        readonly
        size="small"
      ></v-rating>
    </template>
    
    <!-- Actions column -->
    <template v-slot:item.actions="{ item }">
      <v-icon
        small
        class="mr-2"
        @click="viewItem(item)"
        color="primary"
      >
        mdi-eye
      </v-icon>
      <v-icon
        small
        @click="downloadItem(item)"
        color="success"
      >
        mdi-download
      </v-icon>
    </template>
  </v-data-table>
</template>

<script setup>
import { ref } from 'vue'

const headers = ref([
  { title: 'Date', key: 'date', sortable: true },
  { title: 'Recipe', key: 'recipe', sortable: true },
  { title: 'Lot ID', key: 'lotId', sortable: true },
  { title: 'Slot', key: 'slot', sortable: true },
  { title: 'Roughness', key: 'roughness', sortable: true },
  { title: 'Quality', key: 'quality', sortable: false },
  { title: 'Actions', key: 'actions', sortable: false, align: 'center' }
])

const measurements = ref([
  {
    id: 1,
    date: '2024-06-18',
    recipe: 'FSOXCMP_DISHING_9PT',
    lotId: 'T7HQR42TA',
    slot: '21',
    roughness: 1.2
  },
  {
    id: 2,
    date: '2024-06-17',
    recipe: 'OXIDE_ETCH_3PT',
    lotId: 'T8HQR43TB',
    slot: '15',
    roughness: 2.8
  }
])

const search = ref('')
const loading = ref(false)

function getRoughnessColor(roughness) {
  if (roughness < 1.0) return 'green'
  if (roughness < 2.0) return 'blue'
  if (roughness < 3.0) return 'orange'
  return 'red'
}

function getQualityRating(roughness) {
  if (roughness < 1.0) return 5
  if (roughness < 2.0) return 4
  if (roughness < 3.0) return 3
  if (roughness < 4.0) return 2
  return 1
}

function viewItem(item) {
  console.log('Viewing item:', item)
  // Navigate to detail view
}

function downloadItem(item) {
  console.log('Downloading item:', item)
  // Trigger download
}

function exportToExcel() {
  console.log('Exporting to Excel...')
  // Export functionality
}
</script>
```

### Forms and Input Components

Create sophisticated forms for AFM settings:

```vue
<template>
  <v-card max-width="600" class="mx-auto">
    <v-card-title class="headline">
      <v-icon class="mr-2">mdi-cog</v-icon>
      AFM Measurement Settings
    </v-card-title>
    
    <v-card-text>
      <v-form ref="form" v-model="valid" lazy-validation>
        <!-- Recipe Selection -->
        <v-select
          v-model="settings.recipe"
          :items="recipeOptions"
          label="Recipe Type"
          :rules="[v => !!v || 'Recipe is required']"
          prepend-icon="mdi-format-list-bulleted"
          required
        ></v-select>
        
        <!-- Scan Parameters -->
        <v-row>
          <v-col cols="6">
            <v-text-field
              v-model.number="settings.scanSize"
              label="Scan Size (µm)"
              type="number"
              :rules="scanSizeRules"
              prepend-icon="mdi-resize"
              suffix="µm"
            ></v-text-field>
          </v-col>
          
          <v-col cols="6">
            <v-text-field
              v-model.number="settings.scanSpeed"
              label="Scan Speed"
              type="number"
              :rules="scanSpeedRules"
              prepend-icon="mdi-speedometer"
              suffix="Hz"
            ></v-text-field>
          </v-col>
        </v-row>
        
        <!-- Advanced Settings -->
        <v-expansion-panels class="mb-4">
          <v-expansion-panel>
            <v-expansion-panel-title>
              <v-icon class="mr-2">mdi-tune</v-icon>
              Advanced Settings
            </v-expansion-panel-title>
            
            <v-expansion-panel-text>
              <v-slider
                v-model="settings.setPoint"
                label="Set Point"
                :min="0"
                :max="10"
                :step="0.1"
                thumb-label
                prepend-icon="mdi-target"
              >
                <template v-slot:append>
                  <v-text-field
                    v-model="settings.setPoint"
                    type="number"
                    style="width: 80px"
                    density="compact"
                    hide-details
                  ></v-text-field>
                </template>
              </v-slider>
              
              <v-switch
                v-model="settings.enableFeedback"
                label="Enable Force Feedback"
                color="primary"
                prepend-icon="mdi-feedback"
              ></v-switch>
              
              <v-checkbox
                v-model="settings.autoSave"
                label="Auto-save measurements"
                color="primary"
              ></v-checkbox>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
        
        <!-- Measurement Points -->
        <v-card variant="outlined" class="mb-4">
          <v-card-title class="text-subtitle-1">
            Measurement Points
          </v-card-title>
          
          <v-card-text>
            <v-chip-group
              v-model="settings.selectedPoints"
              multiple
              color="primary"
            >
              <v-chip
                v-for="point in availablePoints"
                :key="point"
                :value="point"
                filter
              >
                Point {{ point }}
              </v-chip>
            </v-chip-group>
          </v-card-text>
        </v-card>
        
        <!-- Alerts and Warnings -->
        <v-alert
          v-if="showSpeedWarning"
          type="warning"
          variant="tonal"
          class="mb-4"
        >
          <v-icon>mdi-alert</v-icon>
          High scan speed may reduce measurement accuracy
        </v-alert>
      </v-form>
    </v-card-text>
    
    <v-card-actions>
      <v-spacer></v-spacer>
      <v-btn @click="resetForm">Reset</v-btn>
      <v-btn
        color="primary"
        :disabled="!valid"
        @click="startMeasurement"
        :loading="measuring"
      >
        <v-icon left>mdi-play</v-icon>
        Start Measurement
      </v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, computed } from 'vue'

const form = ref(null)
const valid = ref(false)
const measuring = ref(false)

const settings = ref({
  recipe: '',
  scanSize: 10,
  scanSpeed: 50,
  setPoint: 2.0,
  enableFeedback: true,
  autoSave: true,
  selectedPoints: [1, 2, 3]
})

const recipeOptions = [
  'FSOXCMP_DISHING_9PT',
  'OXIDE_ETCH_3PT',
  'METAL_CMP_5PT',
  'POLY_ETCH_7PT',
  'NITRIDE_DEP_4PT'
]

const availablePoints = [1, 2, 3, 4, 5, 6, 7, 8, 9]

const scanSizeRules = [
  v => !!v || 'Scan size is required',
  v => v > 0 || 'Scan size must be positive',
  v => v <= 100 || 'Scan size too large'
]

const scanSpeedRules = [
  v => !!v || 'Scan speed is required',
  v => v > 0 || 'Scan speed must be positive',
  v => v <= 200 || 'Scan speed too high'
]

const showSpeedWarning = computed(() => {
  return settings.value.scanSpeed > 100
})

async function startMeasurement() {
  if (form.value.validate()) {
    measuring.value = true
    
    try {
      // Simulate API call
      await new Promise(resolve => setTimeout(resolve, 2000))
      console.log('Measurement started with settings:', settings.value)
    } finally {
      measuring.value = false
    }
  }
}

function resetForm() {
  form.value.reset()
  settings.value = {
    recipe: '',
    scanSize: 10,
    scanSpeed: 50,
    setPoint: 2.0,
    enableFeedback: true,
    autoSave: true,
    selectedPoints: [1, 2, 3]
  }
}
</script>
```

### Charts and Data Visualization

Integrate Chart.js or similar libraries with Vuetify:

```vue
<template>
  <v-card>
    <v-card-title class="d-flex align-center">
      <v-icon class="mr-2">mdi-chart-line</v-icon>
      Roughness Trend Analysis
      
      <v-spacer></v-spacer>
      
      <v-btn-toggle v-model="chartType" mandatory>
        <v-btn value="line" size="small">
          <v-icon>mdi-chart-line</v-icon>
        </v-btn>
        <v-btn value="bar" size="small">
          <v-icon>mdi-chart-bar</v-icon>
        </v-btn>
        <v-btn value="scatter" size="small">
          <v-icon>mdi-chart-scatter-plot</v-icon>
        </v-btn>
      </v-btn-toggle>
    </v-card-title>
    
    <v-card-text>
      <div class="chart-container" style="height: 400px;">
        <!-- Chart component would go here -->
        <canvas ref="chartCanvas"></canvas>
      </div>
    </v-card-text>
    
    <v-card-actions>
      <v-chip-group v-model="selectedMetrics" multiple>
        <v-chip
          v-for="metric in availableMetrics"
          :key="metric.key"
          :value="metric.key"
          filter
          :color="metric.color"
        >
          {{ metric.label }}
        </v-chip>
      </v-chip-group>
    </v-card-actions>
  </v-card>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const chartCanvas = ref(null)
const chartType = ref('line')
const selectedMetrics = ref(['roughness', 'quality'])

const availableMetrics = [
  { key: 'roughness', label: 'Roughness', color: 'blue' },
  { key: 'quality', label: 'Quality Score', color: 'green' },
  { key: 'temperature', label: 'Temperature', color: 'orange' },
  { key: 'humidity', label: 'Humidity', color: 'purple' }
]

onMounted(() => {
  // Initialize chart library
  initializeChart()
})

function initializeChart() {
  // Chart initialization code would go here
  console.log('Chart initialized')
}
</script>
```

## Theming and Customization

### Custom Theme Configuration

```javascript
// plugins/vuetify.js
import { createVuetify } from 'vuetify'

const afmTheme = {
  dark: false,
  colors: {
    primary: '#1976D2',      // SK hynix blue
    secondary: '#424242',    // Dark gray
    accent: '#82B1FF',       // Light blue
    error: '#FF5252',        // Red for alerts
    info: '#2196F3',         // Information blue
    success: '#4CAF50',      // Green for success
    warning: '#FFC107',      // Amber for warnings
    background: '#FAFAFA',   // Light background
    surface: '#FFFFFF',      // Card surfaces
    'on-primary': '#FFFFFF',
    'on-secondary': '#FFFFFF',
    'on-surface': '#000000'
  }
}

export default createVuetify({
  theme: {
    defaultTheme: 'afmTheme',
    themes: {
      afmTheme
    }
  }
})
```

## Conclusion

This tutorial provided a comprehensive foundation for building modern web applications using Vue.js and Vuetify, specifically tailored for the AFM data platform. You've learned:

### Key Takeaways

1. **Web Development Fundamentals**: Understanding the relationship between HTML, CSS, and JavaScript
2. **Vue.js Mastery**: Component architecture, reactivity system, and advanced concepts
3. **Professional UI**: Creating polished interfaces with Vuetify's Material Design components
4. **Real-world Application**: Practical examples using AFM measurement data and equipment controls

### Next Steps

- **Practice**: Build your own AFM data analysis components
- **Explore**: Investigate Vue ecosystem tools (Vue Router, Pinia)
- **Extend**: Add new features like real-time WebSocket connections
- **Optimize**: Learn about performance optimization and deployment strategies

### Additional Resources

- [Vue.js Official Documentation](https://vuejs.org/)
- [Vuetify Component Library](https://vuetifyjs.com/)
- [Vue Router for Navigation](https://router.vuejs.org/)
- [Pinia for State Management](https://pinia.vuejs.org/)

The AFM data platform now serves as both a practical tool for semiconductor engineering and a learning vehicle for modern web development. Continue building upon these foundations to create even more sophisticated data analysis and visualization capabilities.