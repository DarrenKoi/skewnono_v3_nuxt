<template>
  <div class="dashboard-surface rounded-[var(--sk-r-card)] p-4">
    <!-- 튜닝할 장비 — PM 튜닝 칩의 주어. 아래 튜닝 목표 · Up gate 가 이 한 대를
         기준으로 계산되지만, 그 계산은 위 비교 대상(recipe)과 장비 모델 그룹이
         정한 집합 안에서만 뜻이 있으므로 그 두 바 다음에 옵니다. 화면의 다른
         바들과 달리 PM 튜닝 칩을 켰을 때만 뜻이 있는 선택이라, 공유 바들과
         섞이지 않는 자기 바를 씁니다 — 칩을 켜는 것이 이 바를 부릅니다. -->
    <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
      <p class="sk-panel-title">
        튜닝할 장비
      </p>
      <p class="sk-hint">
        아래 튜닝 목표 · Up gate 가 이 장비 기준입니다. 기본값은 PM 직후 장비 — 하드웨어를 만질 기회가 지금인 장비입니다. 다만 N이 커질수록 서로 대체 측정할 수 있는 장비가 늘어납니다.
      </p>
    </div>

    <div class="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2">
      <USelectMenu
        :model-value="picked ?? ''"
        :items="ids"
        :search-input="rows.length > 6 ? { placeholder: 'eqp_id 검색…' } : false"
        :loading="pending"
        :disabled="!rows.length"
        :ui="{ content: MENU_CONTENT, itemTrailingIcon: 'hidden' }"
        icon="i-lucide-wrench"
        color="neutral"
        variant="outline"
        size="lg"
        class="w-full sm:w-[300px]"
        @update:model-value="emit('update:picked', String($event))"
      >
        <template #default>
          <span
            v-if="pickedRow"
            class="flex min-w-0 flex-1 items-center gap-2"
          >
            <span
              class="h-2.5 w-2.5 shrink-0 rounded-full"
              :class="pickedRow.verdict === 'up' ? 'bg-(--sk-ok)' : 'bg-(--sk-bad)'"
              :title="pickedRow.verdict === 'up' ? 'Up gate 통과' : 'Hold'"
            />
            <!-- The picked id at card-id size: it is the one value on this bar
                 the reader comes back to, and 12px inside a 264px cell is what
                 made it easy to miss. -->
            <span class="truncate sk-card-id text-[16px]">{{ pickedRow.eqp_id }}</span>
          </span>
          <span
            v-else
            class="sk-field-label"
          >{{ pending ? 'Roster를 불러오는 중입니다' : awaiting ? '데이터 요청 전' : '장비 없음' }}</span>
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

      <!-- The picked row's facts beside the trigger rather than in a caption
           under it: they are the reason this tool is the one being tuned, and
           the collapsed trigger can only carry the id. -->
      <div
        v-if="pickedRow"
        class="flex flex-wrap items-center gap-1.5"
      >
        <span
          class="sk-badge"
          :class="pickedRow.verdict === 'up' ? 'bg-(--sk-ok-soft) text-(--sk-ink)' : 'bg-(--sk-bad-soft) text-(--sk-bad)'"
        >{{ pickedRow.verdict === 'up' ? 'Up 가능' : 'Hold' }}</span>
        <span
          v-if="pickedRow.inGroup"
          class="sk-badge bg-(--sk-ok-soft) text-(--sk-ink)"
        >1차 그룹</span>
        <span class="sk-field-label">{{ pmLabel(pickedRow) }}</span>
      </div>
    </div>

    <!-- An empty list is three different facts, and only one of them is an
         empty fab. Since the pm payload waits for 데이터 요청 (2026-08-30), the
         commonest one is simply that nobody has asked yet — captioning that as
         "roster 가 비어 있습니다" told the user their fab had no tools. -->
    <p
      v-if="!pending && !rows.length"
      class="mt-2 sk-field-label leading-relaxed"
    >
      {{ awaiting ? '위 데이터 요청을 누르면 이 FAB 의 장비가 채워집니다.' : '이 FAB 의 CD-SEM roster 가 비어 있습니다.' }}
    </p>
  </div>
</template>

<script setup lang="ts">
// Its own bar since 2026-08-27, and a dropdown rather than the standing list
// this was as a rail card. It sat in the 분석 조건 bar's trailing cell, which
// put the page's SUBJECT in a 264px column at the far right under a title that
// did not name it. It then spent a day at the very top of the page, which fixed
// the visibility and broke the order: the tool is picked out of the group the
// 장비 모델 그룹 bar defines, so it now sits directly under that bar
// (2026-08-28). Every fact a row carried — Up gate, group membership, last PM —
// is still on the row inside the menu, and the picked row repeats them beside
// the trigger so the collapsed state is never a bare id.

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
  /** No request has been made yet — an empty list is not an empty fab either. */
  awaiting?: boolean
}>()

const emit = defineEmits<{
  'update:picked': [eqpId: string]
}>()

// The menu widens past its trigger: NuxtUI pins a popper to the trigger width,
// and an eqp_id plus its PM date and 그룹 badge does not fit in it. Same rule as
// the recipe picker below — the popper floats over the results, where the space
// already exists.
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
