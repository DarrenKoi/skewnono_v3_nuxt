<template>
  <ActivityCountBarList
    :items="rows"
    :empty-text="emptyText"
    :cap="cap"
  />
</template>

<script setup lang="ts">
import type { FeatureCount } from '~/composables/useActivityApi'
import { activityFeatureLabel } from '~/utils/activity'

// ActivityCountBarList for feature slugs: the label is the feature's display
// name and the slug itself is the hover text.
const props = withDefaults(
  defineProps<{
    items: FeatureCount[]
    emptyText?: string
    cap?: number
  }>(),
  { emptyText: '—', cap: 10 }
)

const rows = computed(() =>
  props.items.map(row => ({
    label: activityFeatureLabel(row.feature),
    title: row.feature,
    count: row.count
  }))
)
</script>
