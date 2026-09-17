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
        수집 기간을 정한 뒤 데이터를 요청합니다.
      </p>
    </div>

    <div class="mt-3 flex flex-col items-start gap-3">
      <EbeamScopeWindow
        :window-weeks="windowWeeks"
        @update:window-weeks="emit('update:windowWeeks', $event)"
      />

      <div class="flex flex-wrap items-center gap-x-3 gap-y-1.5">
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
  if (!props.hasRecipe) return '레시피 선택이 필요합니다.'
  if (props.toolCount < 2) return '장비를 2대 이상 선택해야 합니다.'
  const scope = `장비 ${props.toolCount}대 · 최근 ${props.windowWeeks}주`
  if (props.pending) return `${scope}의 측정 데이터를 모으는 중입니다.`
  if (props.stale) {
    return props.fetchedAt
      ? '조건이 바뀌었습니다 — 다시 요청하면 반영됩니다.'
      : `${scope}의 측정 데이터를 서버에서 모읍니다.`
  }
  return `마지막 요청 ${props.fetchedAt?.replace('T', ' ').slice(0, 16)} · ${scope}`
})
</script>
