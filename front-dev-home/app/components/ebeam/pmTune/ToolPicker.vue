<template>
  <div>
    <p class="mb-1.5 sk-label">
      튜닝할 장비
    </p>

    <USelectMenu
      :model-value="picked ?? ''"
      :items="ids"
      :search-input="rows.length > 6 ? { placeholder: 'eqp_id 검색…' } : false"
      :loading="pending"
      :disabled="disabled || !rows.length"
      :ui="{ content: MENU_CONTENT, itemTrailingIcon: 'hidden' }"
      icon="i-lucide-wrench"
      color="neutral"
      variant="outline"
      class="w-full"
      @update:model-value="emit('update:picked', String($event))"
    >
      <template #default>
        <span
          v-if="pickedRow"
          class="flex min-w-0 flex-1 items-center gap-2"
        >
          <span
            class="h-2 w-2 shrink-0 rounded-full"
            :class="pickedRow.verdict === 'up' ? 'bg-(--sk-ok)' : 'bg-(--sk-bad)'"
            :title="pickedRow.verdict === 'up' ? 'Up gate 통과' : 'Hold'"
          />
          <span class="truncate sk-value-num">{{ pickedRow.eqp_id }}</span>
        </span>
        <span
          v-else
          class="sk-field-label"
        >{{ pending ? 'Roster를 불러오는 중입니다' : '장비 없음' }}</span>
      </template>

      <!-- The dot restates the Up gate, not group membership — the two are
           different verdicts and the badge on the trailing side carries the
           second. -->
      <template #item-leading="{ item }">
        <span
          class="h-2 w-2 shrink-0 rounded-full"
          :class="byId[item]?.verdict === 'up' ? 'bg-(--sk-ok)' : 'bg-(--sk-bad)'"
          :title="byId[item]?.verdict === 'up' ? 'Up gate 통과' : 'Hold'"
        />
      </template>

      <template #item-trailing="{ item }">
        <span class="ml-auto flex shrink-0 items-center gap-1.5">
          <span
            v-if="byId[item]?.inGroup"
            class="sk-badge bg-(--sk-ok-soft) text-(--sk-ink)"
          >그룹</span>
          <span class="font-mono text-xs tabular-nums text-(--sk-ink-muted)">
            {{ pmLabel(byId[item]) }}
          </span>
        </span>
      </template>
    </USelectMenu>

    <p class="mt-1.5 sk-field-label leading-relaxed">
      <template v-if="pickedRow">
        {{ pmLabel(pickedRow) }} · {{ pickedRow.inGroup ? '1차 그룹 구성원' : '그룹 밖' }}
      </template>
      <template v-else-if="!pending && !rows.length">
        이 FAB 의 CD-SEM roster 가 비어 있습니다.
      </template>
      <template v-else>
        PM 창(직후)의 장비가 기본 선택됩니다 — 하드웨어를 만질 기회는 PM 때뿐입니다.
      </template>
    </p>
  </div>
</template>

<script setup lang="ts">
// A dropdown rather than the standing list this was as a rail card: the control
// moved into the 분석 조건 bar, where the page's controls occupy one row and an
// 18-row list would be the tallest thing on the screen. Every fact a row carried
// — Up gate, group membership, last PM — is still on the row, now inside the
// menu, and the picked row repeats it in the caption so the collapsed state is
// never a bare id.

export interface PickerRow {
  eqp_id: string
  verdict: 'up' | 'hold'
  /** Most recent completed PM (gate.post_pm_at); null = never recorded. */
  postPmAt: string | null
  /** Member of the current 1차 N배화 group. */
  inGroup: boolean
}

const props = defineProps<{
  rows: PickerRow[]
  picked: string | null
  /** The pm request is still in flight — an empty list is not yet an empty fab. */
  pending?: boolean
  /** No scope to judge against yet — visible so the step reads, but inert. */
  disabled?: boolean
}>()

const emit = defineEmits<{
  'update:picked': [eqpId: string]
}>()

// The menu widens past its trigger: the trigger is one cell of the scope bar,
// and an eqp_id plus its PM date and 그룹 badge does not fit in it. Same rule as
// the recipe picker beside it — the popper floats over the results below, where
// the space already exists.
const MENU_CONTENT = 'w-auto min-w-full max-w-[min(26rem,calc(100vw-2rem))]'

const ids = computed(() => props.rows.map(r => r.eqp_id))
// Keyed lookup rather than a `.find()` inside the slots: the leading and
// trailing slots each render once per visible row, so a linear scan there is
// quadratic in the roster.
const byId = computed<Record<string, PickerRow>>(() =>
  Object.fromEntries(props.rows.map(r => [r.eqp_id, r]))
)
const pickedRow = computed(() => (props.picked ? byId.value[props.picked] ?? null : null))

// "PM 이력 없음" is a different fact from an old PM date and must not render as
// a blank — a tool that has never been PM'd is exactly the one worth noticing.
const pmLabel = (row?: PickerRow) =>
  row?.postPmAt ? `PM ${row.postPmAt.slice(0, 10)}` : 'PM 이력 없음'
</script>
