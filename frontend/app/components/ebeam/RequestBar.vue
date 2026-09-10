<template>
  <!-- At the shared `ebeam/` level beside ScopeBar · ToolGroupBar · AnalysisBar,
       not in `ebeam/tttm/` where it started: that folder holds the cards of the
       장비간 스큐 PANEL, and this is a control every panel is fed by. It sat
       there while TTTM was a page of its own (2026-08-28) and stayed through
       the merge, which left the folder meaning two things. -->
  <div class="dashboard-surface rounded-[var(--sk-r-card)] p-4">
    <!-- 수집 기간 · 데이터 요청 — 세 번째 단계. 비교 대상(recipe)과 장비를 정한 뒤
         얼마나 모을지 고르고, 그때서야 서버에 묻습니다. 사무실에서는 이 요청 한 번이
         장비마다 run 수만큼의 MinIO GET 이라, 드롭다운을 누를 때마다 자동으로 다시
         묻던 방식은 아무도 보지 않는 장비의 데이터까지 매번 모았습니다. -->
    <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
      <p class="sk-panel-title">
        수집 기간 · 데이터 요청
      </p>
      <p class="sk-hint">
        고른 recipe · 장비 · 기간으로 서버에서 run 을 모읍니다. recipe · 장비 · 기간을 바꾸면 다시 요청해야 반영되고, parameter 는 바로 다시 계산합니다.
      </p>
    </div>

    <div class="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
      <EbeamScopeWindow
        :window-weeks="windowWeeks"
        @update:window-weeks="emit('update:windowWeeks', $event)"
      />

      <div class="flex shrink-0 flex-col items-start gap-1.5 lg:items-end">
        <!-- `button-default` (DESIGN.md §Buttons): a plain action with no
             selected state. Disabled with the reason spelled out below it
             rather than hidden — the procedure has to read as three steps. -->
        <UButton
          color="neutral"
          variant="solid"
          icon="i-lucide-database"
          :loading="pending"
          :disabled="!canRequest"
          :class="{ 'cursor-not-allowed': !canRequest }"
          @click="emit('request')"
        >
          데이터 요청
        </UButton>
        <p
          class="sk-field-label leading-relaxed"
          :class="{ 'text-(--sk-warn)': stale && fetchedAt }"
        >
          {{ status }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { WindowWeeks } from '~/utils/analysisWindow'

const props = defineProps<{
  windowWeeks: WindowWeeks
  /** The tools the request would name — the picker's resolved selection. */
  toolCount: number
  hasRecipe: boolean
  pending: boolean
  /** No payload, or one for another scope — see utils/tttmRequest. */
  stale: boolean
  /** The payload's `fetched_at`, or null before the first answer. */
  fetchedAt: string | null
}>()

const emit = defineEmits<{
  (e: 'update:windowWeeks', value: WindowWeeks): void
  (e: 'request'): void
}>()

const canRequest = computed(() => props.hasRecipe && props.toolCount >= 2 && !props.pending)

// One sentence for the state the button is in, in the reader's terms. The
// disabled reasons name the step that is missing; the stale line is the one
// that keeps an old answer from being read as the current one.
const status = computed(() => {
  if (!props.hasRecipe) return '먼저 위에서 recipe 를 고르십시오.'
  if (props.toolCount < 2) return '장비를 2대 이상 고르십시오.'
  const scope = `장비 ${props.toolCount}대 · 최근 ${props.windowWeeks}주`
  if (props.pending) return `${scope}의 run 을 모으는 중입니다.`
  if (props.stale) {
    return props.fetchedAt
      ? '조건이 바뀌었습니다 — 다시 요청하면 반영됩니다.'
      : `${scope}의 run 을 서버에서 모읍니다.`
  }
  return `마지막 요청 ${props.fetchedAt?.replace('T', ' ').slice(0, 16)} · ${scope}`
})
</script>
