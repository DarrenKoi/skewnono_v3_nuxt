<template>
  <div class="dashboard-surface flex flex-col rounded-[var(--sk-r-card)] px-5 py-4">
    <p class="sk-eyebrow">
      1차 추천 · 최대 N배화
    </p>

    <template v-if="primary">
      <div class="mt-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <span class="text-4xl font-bold leading-none tracking-[-0.02em] tabular-nums text-(--sk-ink)">
          {{ primary.n }}대
        </span>
        <span class="text-base font-semibold text-(--sk-ink-muted)">
          가 현재 tolerance에서 서로 N배화됩니다
        </span>
      </div>

      <div class="mt-3.5 flex flex-wrap gap-2">
        <span
          v-for="t in primary.tools"
          :key="t"
          class="inline-flex h-[26px] items-center rounded-[var(--sk-r-sidebar)] bg-(--sk-ok-soft) px-2.5 font-mono text-sm font-semibold text-(--sk-ok)"
        >{{ labelFor(t) }}</span>
      </div>

      <div class="mt-4 flex flex-wrap gap-x-6 gap-y-3 border-t border-(--sk-border-soft) pt-3.5">
        <span class="flex flex-col gap-0.5">
          <span class="sk-field-label">최약 장비쌍</span>
          <!-- Index first, nm second: the index is what ordered these groups, so
               leading with the nm would put the number that did NOT decide the
               ranking where the reader trusts it most. -->
          <span class="sk-field-value font-semibold text-(--sk-ink)">
            CD 대비 {{ primary.weakestPairIndex.toFixed(2) }}× · {{ primary.weakestPairSkew.toFixed(3) }} nm
          </span>
        </span>
        <span class="flex flex-col gap-0.5">
          <span class="sk-field-label">신뢰도</span>
          <span
            class="sk-field-value font-semibold"
            :style="{ color: confColor }"
          >
            {{ primary.confidence }}<template v-if="primary.tier === 'predicted'"> · 예측 tier 포함</template>
          </span>
        </span>
        <span class="flex flex-col gap-0.5">
          <span class="sk-field-label">다른 후보</span>
          <span class="sk-field-value">
            <template v-if="others.length">
              {{ otherSummary }}
              <EbeamTttmCaptionMore label="목록">
                <span
                  v-for="(g, i) in others"
                  :key="i"
                  class="block"
                >N={{ g.n }} · {{ g.tools.map(labelFor).join(' · ') }}</span>
              </EbeamTttmCaptionMore>
            </template>
            <template v-else>없음</template>
          </span>
        </span>
      </div>
    </template>

    <p
      v-else
      class="mt-2 sk-body text-(--sk-bad)"
    >
      현재 tolerance에서 모든 점유 셀을 동시에 만족하는 N배화 그룹이 없습니다.
    </p>
  </div>
</template>

<script setup lang="ts">
import { toolLabels } from '~/utils/toolLabels'
import type { NbaGroup } from '~/utils/tttmGrouping'
import type { ToolRef } from '~/composables/useTttmApi'

const props = defineProps<{
  primary: NbaGroup | null
  others: NbaGroup[]
  tools: ToolRef[]
}>()

const labels = computed(() => toolLabels(props.tools))
const labelFor = (eqp: string) => labels.value.labelFor(eqp)

const confColor = computed(() => {
  if (!props.primary) return 'var(--sk-ink)'
  return props.primary.confidence === 'High'
    ? 'var(--sk-ok)'
    : props.primary.confidence === 'Low'
      ? 'var(--sk-bad)'
      : 'var(--sk-accent)'
})

// "N=3 그룹 2개" rather than every runner-up spelled out: this line sits in a
// three-column footer, and a fleet of ten answers with a dozen maximal cliques
// whose names would wrap the card open. The names are one disclosure away.
const otherSummary = computed(() => {
  const counts = new Map<number, number>()
  for (const g of props.others) counts.set(g.n, (counts.get(g.n) ?? 0) + 1)
  return [...counts.entries()]
    .sort((a, b) => b[0] - a[0])
    .map(([n, many]) => `N=${n} 그룹 ${many}개`)
    .join(' · ')
})
</script>
