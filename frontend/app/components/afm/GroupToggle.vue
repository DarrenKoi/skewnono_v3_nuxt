<template>
  <UButton
    size="sm"
    color="neutral"
    :variant="inGroup ? 'subtle' : 'outline'"
    :icon="inGroup ? 'i-lucide-check' : 'i-lucide-plus'"
    :label="inGroup ? '담김' : '그룹'"
    :aria-label="inGroup ? '그룹에서 제거' : '그룹에 추가'"
    :aria-pressed="inGroup"
    class="shrink-0"
    @click.stop="$emit('toggle')"
  />
</template>

<script setup lang="ts">
// Adds a measurement to (or removes it from) the 데이터 그룹 cart. Labelled, not
// icon-only: a bare "+" beside every row did not say what it added to.
defineProps<{
  inGroup: boolean
}>()

defineEmits<{
  toggle: []
}>()
</script>
