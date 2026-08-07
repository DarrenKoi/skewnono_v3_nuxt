<script setup lang="ts">
const props = defineProps<{
  fabs: string[]
  primaryFab: string
}>()

const visible = computed(() => props.fabs.length > 1)
</script>

<template>
  <div
    v-if="visible"
    class="flex items-center gap-1.5 px-3 py-1.5 mb-2 rounded-lg text-xs text-(--sk-ink-muted) bg-(--sk-border-soft)"
  >
    <UIcon
      name="i-lucide-info"
      class="w-3.5 h-3.5 shrink-0"
    />
    <span>{{ primaryFab }} 기준 표시 — 이 화면의 다중 FAB 지원은 추후 제공됩니다.</span>
  </div>
</template>
