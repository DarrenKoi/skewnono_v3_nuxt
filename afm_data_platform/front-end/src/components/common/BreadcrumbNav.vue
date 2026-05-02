<template>
  <v-breadcrumbs class="pa-0 mb-3" :items="computedItems">
    <template v-slot:divider>
      <v-icon size="small">mdi-chevron-right</v-icon>
    </template>
    <template v-slot:item="{ item }">
      <v-breadcrumbs-item
        :disabled="item.disabled"
        @click="!item.disabled && handleClick(item)">
        <v-icon v-if="item.icon" size="small" class="mr-1">{{ item.icon }}</v-icon>
        {{ item.title }}
      </v-breadcrumbs-item>
    </template>
  </v-breadcrumbs>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'

/**
 * @typedef {Object} BreadcrumbItem
 * @property {string} title - Display text
 * @property {string} [icon] - Optional icon
 * @property {string} [to] - Route path
 * @property {boolean} [disabled] - Whether item is clickable
 */

const props = defineProps({
  /**
   * Array of breadcrumb items
   * @type {BreadcrumbItem[]}
   */
  items: {
    type: Array,
    default: () => []
  },
  /**
   * Whether to include home as first item
   */
  includeHome: {
    type: Boolean,
    default: true
  }
})

const router = useRouter()

/**f
 * Computed items with home prepended if needed
 */
const computedItems = computed(() => {
  const items = [...props.items]

  if (props.includeHome) {
    items.unshift({
      title: 'Home',
      icon: 'mdi-home',
      to: '/'
    })
  }

  return items
})

/**
 * Handle breadcrumb click navigation
 * @param {BreadcrumbItem} item
 */
function handleClick(item) {
  if (item.to) {
    router.push(item.to)
  }
}
</script>

<style scoped>
.v-breadcrumbs-item {
  cursor: pointer;
  transition: color 0.2s ease;
}

.v-breadcrumbs-item:not([disabled]):hover {
  color: rgb(var(--v-theme-primary));
}

.v-breadcrumbs-item[disabled] {
  cursor: default;
  opacity: 1;
}
</style>
