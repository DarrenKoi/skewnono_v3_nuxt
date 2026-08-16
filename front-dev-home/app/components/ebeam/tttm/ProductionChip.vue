<template>
  <!-- Folded, and a <details> rather than the hand-rolled toggle this used to
       be: it sits beside the MDC history as one of two reference panels, and
       two panels that fold the same way should fold with the same mechanism. -->
  <details class="group dashboard-surface rounded-[var(--sk-r-card)]">
    <summary
      class="flex cursor-pointer list-none items-center gap-2 px-4 py-3 [&::-webkit-details-marker]:hidden"
    >
      <UIcon
        name="i-lucide-chevron-right"
        class="h-3.5 w-3.5 text-(--sk-ink-muted) transition-transform duration-150 group-open:rotate-90"
      />
      <span class="sk-title">양산 정합도 (참고)</span>
      <span
        class="sk-signal-badge"
        :style="levelStyle"
      >{{ levelLabel }}</span>
      <span class="ml-auto sk-meta">TTTM 미반영</span>
    </summary>

    <div class="space-y-1 border-t border-(--sk-border-soft) px-4 py-3">
      <p class="sk-field-label">
        {{ corroboration.note }}
      </p>
      <div
        v-for="row in corroboration.detail"
        :key="row.pair"
        class="flex items-center gap-2 text-xs"
      >
        <span class="w-28 shrink-0 font-mono text-(--sk-ink-muted)">{{ row.pair }}</span>
        <div class="h-2 flex-1 rounded-[var(--sk-r-sidebar)] bg-(--sk-muted-surface)">
          <div
            class="h-2 rounded-[var(--sk-r-sidebar)]"
            :style="{ width: `${row.overlap * 100}%`, background: 'var(--sk-accent)' }"
          />
        </div>
        <span class="w-10 shrink-0 text-right font-mono tabular-nums text-(--sk-ink)">
          {{ (row.overlap * 100).toFixed(0) }}%
        </span>
      </div>
      <p class="pt-1 sk-field-label leading-relaxed">
        다른 Wafer 분포 중첩이라 Wafer 산포와 엉켜 N배화 판정에는 쓰지 않습니다.
      </p>
    </div>
  </details>
</template>

<script setup lang="ts">
import type { ProductionCorroboration } from '~/composables/useTttmApi'

const props = defineProps<{ corroboration: ProductionCorroboration }>()

const levelLabel = computed(
  () => ({ high: '높음', mid: '중간', low: '낮음' }[props.corroboration.level])
)
const levelStyle = computed(() => {
  const l = props.corroboration.level
  if (l === 'high') return { background: 'var(--sk-ok-soft)', color: 'var(--sk-ok)' }
  if (l === 'low') return { background: 'var(--sk-bad-soft)', color: 'var(--sk-bad)' }
  return { background: 'var(--sk-accent-tint)', color: 'var(--sk-accent)' }
})
</script>
