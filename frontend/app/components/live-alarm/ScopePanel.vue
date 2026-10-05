<script setup lang="ts">
// 사건 범위: the same 20-minute board, read along three axes instead of by
// time. Render-only — every number comes from scopeGroups() in the parent, so
// this adds no request and no state, and nothing here is clickable.
import { formatElapsed } from '~/utils/liveAlarm'
import type { ScopeGroup, ScopeGroups } from '~/utils/liveAlarm'

const props = defineProps<{
  scope: ScopeGroups
  // Server clock in ms (Date.now() + the feed's serverOffsetMs), so "마지막 n분
  // 전" agrees with the rows on the board below.
  serverNow: number
}>()

const MAX_ROWS = 3

// The counts line leads with what the axis reaches ACROSS. A lot row would
// otherwise read "lot 1" every time, so it reports recipes in that slot.
const columns = computed(() => [
  {
    key: 'recipe',
    title: '한 recipe · 여러 장비',
    groups: props.scope.recipeAcrossTools,
    counts: (g: ScopeGroup) => `장비 ${g.toolCount} · lot ${g.lotCount} · ${g.eventCount}건`
  },
  {
    key: 'tool',
    title: '한 장비 · 여러 recipe',
    groups: props.scope.toolAcrossRecipes,
    counts: (g: ScopeGroup) => `recipe ${g.recipeCount} · lot ${g.lotCount} · ${g.eventCount}건`
  },
  {
    key: 'lot',
    title: '한 lot · 여러 장비',
    groups: props.scope.lotAcrossTools,
    counts: (g: ScopeGroup) => `장비 ${g.toolCount} · recipe ${g.recipeCount} · ${g.eventCount}건`
  }
].map(column => ({
  ...column,
  shown: column.groups.slice(0, MAX_ROWS),
  more: Math.max(0, column.groups.length - MAX_ROWS)
})))

const span = (g: ScopeGroup): string =>
  `${Math.floor((g.lastEpoch - g.firstEpoch) / 60)}분 폭 · 마지막 ${formatElapsed(props.serverNow - g.lastEpoch * 1000)}`
</script>

<template>
  <section class="dashboard-surface rounded-[var(--sk-r-card)] px-4 py-3">
    <h3 class="sk-panel-title">
      사건 범위
    </h3>

    <div class="mt-3 grid grid-cols-3 gap-x-6">
      <div
        v-for="column in columns"
        :key="column.key"
        class="min-w-0"
      >
        <p class="sk-title">
          {{ column.title }}
        </p>

        <p
          v-if="!column.groups.length"
          class="mt-2 sk-meta"
        >
          해당 없음
        </p>

        <ul
          v-else
          class="mt-1"
        >
          <li
            v-for="group in column.shown"
            :key="group.key"
            class="border-b border-default py-2 last:border-b-0"
          >
            <p class="truncate font-mono text-sm font-semibold text-(--sk-ink)">
              {{ group.label }}
            </p>
            <p class="mt-0.5 font-mono text-xs tabular-nums text-(--sk-ink)">
              {{ column.counts(group) }}
            </p>
            <p class="mt-0.5 font-mono text-xs tabular-nums text-(--sk-ink-muted)">
              {{ span(group) }}
            </p>
            <div class="mt-1 flex flex-wrap items-center gap-1.5">
              <span class="font-mono text-xs tabular-nums text-(--sk-ink-muted)">
                Align {{ group.kinds.align }} · 측정 {{ group.kinds.meas }}
              </span>
              <UBadge
                v-for="(count, alid) in group.alids"
                :key="alid"
                color="neutral"
                variant="subtle"
                size="sm"
                class="font-mono tabular-nums"
              >
                {{ alid }} × {{ count }}
              </UBadge>
            </div>
          </li>
        </ul>

        <p
          v-if="column.more"
          class="mt-1 sk-meta"
        >
          외 {{ column.more }}
        </p>
      </div>
    </div>

    <p class="mt-3 sk-hint">
      최근 20분 창에서 관측된 범위입니다. 원인이나 해결을 뜻하지 않습니다.
    </p>
  </section>
</template>
