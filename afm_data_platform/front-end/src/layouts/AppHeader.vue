<template>
  <v-app-bar color="primary" elevation="2">
    <!-- Modern Logo Text - clickable to go to main page -->
    <v-app-bar-title>
      <v-btn variant="text" color="white" class="pa-0 modern-logo-text" @click="goToHome">
        AFM Data Viewer
      </v-btn>
    </v-app-bar-title>

    <v-spacer />

    <!-- Navigation Links -->
    <v-btn v-for="link in internalLinks" :key="link.label" class="mx-1" size="small" variant="text"
      :color="route.path === link.path ? 'white' : 'rgba(255,255,255,0.7)'" @click="navigateTo(link.path)">
      <v-icon class="mr-1" :icon="link.icon" size="small" />
      <span class="text-body-2">{{ link.label }}</span>
    </v-btn>

    <!-- Divider - only show if external links exist -->
    <v-divider v-if="externalLinks.length > 0" vertical class="mx-2" color="rgba(255,255,255,0.3)" />

    <!-- External Links - Desktop optimized -->
    <template v-if="externalLinks.length <= 4">
      <!-- Show all external links directly if 4 or fewer -->
      <v-btn v-for="link in externalLinks" :key="link.label" class="mx-1" :href="link.href" rel="noopener noreferrer"
        size="small" target="_blank" variant="text" color="rgba(255,255,255,0.7)">
        <v-icon class="mr-1" :icon="link.icon" size="small" />
        <span class="text-body-2">{{ link.label }}</span>
        <v-icon class="ml-1" icon="mdi-open-in-new" size="x-small" />
      </v-btn>
    </template>

    <!-- External Links Dropdown - Show when more than 4 links -->
    <v-menu v-else offset-y>
      <template #activator="{ props }">
        <v-btn v-bind="props" class="mx-1" size="small" variant="text" color="rgba(255,255,255,0.7)">
          <v-icon class="mr-1" icon="mdi-link" size="small" />
          <span class="text-body-2">External Links</span>
          <v-icon class="ml-1" icon="mdi-chevron-down" size="x-small" />
        </v-btn>
      </template>
      <v-list>
        <v-list-item v-for="link in externalLinks" :key="link.label" :href="link.href" target="_blank"
          rel="noopener noreferrer">
          <template #prepend>
            <v-icon :icon="link.icon" size="small" />
          </template>
          <v-list-item-title>{{ link.label }}</v-list-item-title>
          <template #append>
            <v-icon icon="mdi-open-in-new" size="x-small" />
          </template>
        </v-list-item>
      </v-list>
    </v-menu>
  </v-app-bar>
</template>

<script setup>
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()

// Internal navigation links
const internalLinks = [
  {
    icon: 'mdi-home',
    path: '/',
    label: 'Home',
  },
  {
    icon: 'mdi-information',
    path: '/about',
    label: 'About',
  },
  {
    icon: 'mdi-email',
    path: '/contact',
    label: 'Contact',
  },
]

// External links to SK Hynix systems
const externalLinks = [
  {
    icon: 'mdi-chart-line',
    href: 'http://skewnono.skhynix.com',
    label: 'Skewnono',
  },
  {
    icon: 'mdi-database',
    href: 'http://rnddmi.skhynix.com',
    label: 'RND DMI',
  },
]

// Navigation functions
function goToHome() {
  router.push('/')
}

function navigateTo(path) {
  router.push(path)
}
</script>

<style scoped>
.modern-logo-text {
  font-size: 1.5rem !important;
  font-weight: 700 !important;
  letter-spacing: 0.5px !important;
  text-transform: none !important;
  position: relative;
  background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 50%, #ffffff 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  transition: all 0.3s ease;
}

.modern-logo-text::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.1) 0%, transparent 50%, rgba(255, 255, 255, 0.1) 100%);
  opacity: 0;
  transition: opacity 0.3s ease;
  pointer-events: none;
}

.modern-logo-text:hover {
  transform: translateY(-1px);
  text-shadow: 0 2px 8px rgba(255, 255, 255, 0.3);
}

.modern-logo-text:hover::before {
  opacity: 1;
}

/* Fallback for browsers that don't support background-clip */
@supports not (-webkit-background-clip: text) {
  .modern-logo-text {
    color: white !important;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.1);
  }
}
</style>
