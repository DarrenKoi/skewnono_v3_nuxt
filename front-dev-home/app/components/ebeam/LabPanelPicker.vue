<template>
  <div>
    <p class="sk-label">
      보기
    </p>

    <!-- Chips rather than a dropdown: there are five, they all fit on one row,
         and the point of the control is that you can SEE what the page could be
         showing you. Behind a menu, a panel nobody has opened is a panel nobody
         knows exists — which is the failure mode of every "customise your
         dashboard" control. Same reason nothing here starts unticked by
         default: the presets in utils/labView turn cards ON. -->
    <div
      class="mt-2 flex flex-wrap gap-1.5"
      role="group"
      aria-label="보여 줄 분석"
    >
      <button
        v-for="panel in LAB_PANELS"
        :key="panel.value"
        type="button"
        :aria-pressed="isOn(panel.value)"
        :title="panel.hint"
        class="inline-flex h-[30px] items-center gap-1.5 rounded-full border px-3 text-sm font-semibold transition-colors"
        :class="isOn(panel.value)
          ? 'border-(--sk-brand) bg-(--sk-brand-soft) text-(--sk-brand-ink)'
          : 'border-(--sk-border) bg-(--sk-surface) text-(--sk-ink-muted) hover:text-(--sk-ink)'"
        @click="toggle(panel.value)"
      >
        <UIcon
          :name="isOn(panel.value) ? 'i-lucide-check' : 'i-lucide-plus'"
          class="h-3.5 w-3.5 shrink-0"
        />
        {{ panel.label }}
      </button>
    </div>

    <p class="mt-2 sk-field-label leading-relaxed">
      이 화면에 그릴 분석을 고릅니다 — 데이터는 한 번만 모으므로 켜고 끄는 데
      다시 요청하지 않습니다. 선택은 이 브라우저에 화면별로 저장됩니다.
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
