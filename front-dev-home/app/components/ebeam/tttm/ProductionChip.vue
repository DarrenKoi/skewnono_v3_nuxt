<template>
  <div class="dashboard-surface rounded-2xl p-4">
    <button
      class="flex items-center gap-2 w-full text-left"
      @click="open = !open"
    >
      <span class="text-xs text-(--sk-ink-subtle)">양산 정합도 (참고)</span>
      <span
        class="px-2 py-0.5 rounded text-xs font-medium"
        :style="levelStyle"
      >
        {{ levelLabel }}
      </span>
      <span class="sk-meta">{{ corroboration.note }}</span>
      <UIcon
        :name="open ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
        class="ml-auto text-(--sk-ink-muted)"
      />
    </button>

    <div
      v-if="open"
      class="mt-3 space-y-1"
    >
      <div
        v-for="row in corroboration.detail"
        :key="row.pair"
        class="flex items-center gap-2 text-xs"
      >
        <span class="w-28 text-(--sk-ink-muted)">{{ row.pair }}</span>
        <div
          class="flex-1 h-2 rounded"
          :style="{ background: 'var(--sk-muted-surface)' }"
        >
          <div
            class="h-2 rounded"
            :style="{ width: `${row.overlap * 100}%`, background: 'var(--sk-accent)' }"
          />
        </div>
        <span class="tabular-nums text-(--sk-ink)">{{ (row.overlap * 100).toFixed(0) }}%</span>
      </div>
      <p class="pt-1 text-[11px] text-(--sk-ink-subtle)">
        다른 Wafer 분포 중첩이라 Wafer 산포와 엉켜 N배화 판정에는 쓰지 않습니다.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ProductionCorroboration } from '~/composables/useTttmApi'

const props = defineProps<{ corroboration: ProductionCorroboration }>()
const open = ref(false)

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
