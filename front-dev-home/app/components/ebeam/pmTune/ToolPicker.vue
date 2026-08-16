<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] px-4 py-3.5">
    <p class="sk-title">
      튜닝할 장비
    </p>
    <p class="mt-1 sk-field-label leading-relaxed">
      PM 창(직후)의 장비가 기본 선택됩니다 — 하드웨어를 만질 기회는 PM 때뿐이라,
      이 페이지의 질문은 항상 "지금 이 장비를 어디까지 맞출 것인가"입니다.
    </p>

    <ul class="mt-2.5 space-y-0.5">
      <li
        v-for="row in rows"
        :key="row.eqp_id"
      >
        <button
          type="button"
          class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-(--sk-muted-surface)"
          :class="row.eqp_id === picked ? 'bg-(--sk-muted-surface) ring-1 ring-(--sk-accent)' : ''"
          :aria-pressed="row.eqp_id === picked"
          @click="emit('update:picked', row.eqp_id)"
        >
          <!-- The dot restates the Up gate, not group membership — the two are
               different verdicts and the badge beside carries the second. -->
          <span
            class="h-2 w-2 shrink-0 rounded-full"
            :class="row.verdict === 'up' ? 'bg-(--sk-ok)' : 'bg-(--sk-bad)'"
            :title="row.verdict === 'up' ? 'Up gate 통과' : 'Hold'"
          />
          <span class="min-w-0 flex-1 truncate sk-value-num">{{ row.eqp_id }}</span>
          <span
            v-if="row.inGroup"
            class="sk-badge bg-(--sk-ok-soft) text-(--sk-ink)"
          >그룹</span>
          <span class="shrink-0 font-mono text-xs tabular-nums text-(--sk-ink-muted)">
            {{ row.postPmAt ? `PM ${row.postPmAt.slice(0, 10)}` : 'PM 이력 없음' }}
          </span>
        </button>
      </li>
    </ul>

    <p
      v-if="!rows.length"
      class="mt-2 sk-body text-(--sk-ink-muted)"
    >
      {{ pending ? 'Roster를 불러오는 중입니다.' : '이 FAB의 CD-SEM roster가 비어 있습니다.' }}
    </p>
  </div>
</template>

<script setup lang="ts">
export interface PickerRow {
  eqp_id: string
  verdict: 'up' | 'hold'
  /** Most recent completed PM (gate.post_pm_at); null = never recorded. */
  postPmAt: string | null
  /** Member of the current 1차 N배화 group. */
  inGroup: boolean
}

defineProps<{
  rows: PickerRow[]
  picked: string | null
  /** The pm request is still in flight — an empty list is not yet an empty fab. */
  pending?: boolean
}>()

const emit = defineEmits<{
  'update:picked': [eqpId: string]
}>()
</script>
