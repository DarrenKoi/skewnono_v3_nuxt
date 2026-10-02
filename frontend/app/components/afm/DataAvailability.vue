<template>
  <span
    class="inline-flex items-center gap-1.5"
    role="list"
    aria-label="데이터 종류"
  >
    <span
      v-for="dt in DATA_TYPES"
      :key="dt.key"
      role="listitem"
      class="inline-flex"
      :title="`${dt.label} ${measurement[dt.key] ? '있음' : '없음'}`"
    >
      <UIcon
        :name="dt.icon"
        class="size-4"
        :class="measurement[dt.key] ? 'text-(--sk-ink)' : 'text-(--sk-ink-subtle) opacity-40'"
      />
      <span class="sr-only">{{ dt.label }} {{ measurement[dt.key] ? '있음' : '없음' }}</span>
    </span>
  </span>
</template>

<script setup lang="ts">
// Which files a measurement carries, as five icons in fixed slots: present in
// full ink, absent faded. Fixed slots so a column of rows reads as a grid — the
// old list dropped absent icons, and every row's icons then sat somewhere else.
import type { AfmMeasurement } from '~/composables/useAfmCart'

defineProps<{
  measurement: AfmMeasurement
}>()

const DATA_TYPES = [
  { key: 'hasProfile', icon: 'i-lucide-line-chart', label: '프로파일 데이터' },
  { key: 'hasData', icon: 'i-lucide-database', label: '측정 데이터' },
  { key: 'hasImage', icon: 'i-lucide-image', label: '프로파일 이미지' },
  { key: 'hasAlign', icon: 'i-lucide-align-vertical-justify-center', label: 'Align 이미지' },
  { key: 'hasTip', icon: 'i-lucide-pin', label: 'Tip 이미지' }
] as const
</script>
