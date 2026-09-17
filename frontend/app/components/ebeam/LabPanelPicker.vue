<template>
  <div>
    <p class="sk-label">
      보기
    </p>

    <div
      class="mt-2 flex flex-wrap gap-1.5"
      role="group"
      aria-label="보여 줄 분석"
    >
      <SkChip
        v-for="panel in LAB_PANELS"
        :key="panel.value"
        :active="isOn(panel.value)"
        :title="panel.hint"
        tone="ink"
        @click="toggle(panel.value)"
      >
        <UIcon
          :name="isOn(panel.value) ? 'i-lucide-check' : 'i-lucide-plus'"
          class="h-3.5 w-3.5 shrink-0"
        />
        {{ panel.label }}
      </SkChip>
    </div>

    <p class="mt-2 sk-field-label leading-relaxed">
      표시할 분석을 선택하며, 데이터를 다시 요청할 필요는 없습니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import { LAB_PANELS, type LabPanel } from '~/utils/labView'

// Deliberately NOT wired to the 분석 조건 bar's `disabled`, though it sits in
// that bar: the lock is about the PARAMETER, which cannot be picked before the
// payload names one. Which analyses to draw is answerable at any time — locking
// it would mean setting up your view had to wait on a request you have not made
// yet, and the chips would grey out on every refetch.
const props = defineProps<{ panels: LabPanel[] }>()

const emit = defineEmits<{ 'update:panels': [value: LabPanel[]] }>()

const isOn = (panel: LabPanel) => props.panels.includes(panel)

// Emits the whole next list rather than a delta: the parent persists it, and
// the canonical order is restored on the way in (see normalizePanels), so
// nothing here has to care where in the row the chip sat.
const toggle = (panel: LabPanel) => {
  emit('update:panels', isOn(panel)
    ? props.panels.filter(p => p !== panel)
    : [...props.panels, panel])
}
</script>
