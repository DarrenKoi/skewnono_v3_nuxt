<template>
  <AfmCard
    v-if="!pending"
    icon="i-lucide-history"
    title="같은 Lot·Slot 측정"
    :count="history ? listed.length - 1 : undefined"
    flush
  >
    <template
      v-if="history && listed.length > 1"
      #actions
    >
      <div class="flex flex-wrap items-center gap-2">
        <span
          v-if="lotPick.otherRecipe"
          class="sk-meta"
        >
          다른 Recipe {{ lotPick.otherRecipe }}건
        </span>
        <SkChip
          size="sm"
          label="같은 Recipe만"
          :active="sameRecipeOnly"
          @click="sameRecipeOnly = !sameRecipeOnly"
        />
        <UButton
          size="sm"
          color="neutral"
          variant="outline"
          icon="i-lucide-plus"
          :label="`이 Slot 담기 · ${waferPick.add.length}건`"
          :disabled="!waferPick.add.length"
          @click="add(waferPick)"
        />
        <UButton
          v-if="history.otherSlots.length"
          size="sm"
          color="neutral"
          variant="outline"
          icon="i-lucide-plus"
          :label="`Lot 전체 담기 · ${lotPick.add.length}건`"
          :disabled="!lotPick.add.length"
          @click="add(lotPick)"
        />
        <UButton
          v-if="cart.groupedData.value.length"
          size="sm"
          color="primary"
          icon="i-lucide-line-chart"
          :label="`함께 보기 · ${cart.groupedData.value.length}건`"
          :to="`/afm/${toolId}/see-together`"
        />
      </div>
    </template>

    <p
      v-if="!history"
      class="px-4 py-4 sk-body"
    >
      {{ error
        ? '측정 목록을 불러오지 못해 같은 Lot·Slot 측정을 찾지 못했습니다.'
        : '이 측정의 Lot·Slot 을 목록에서 확인할 수 없어 자동으로 연결하지 않았습니다. 측정 검색에서 Lot 으로 찾아 주십시오.' }}
    </p>
    <p
      v-else-if="listed.length === 1"
      class="px-4 py-4 sk-body"
    >
      목록(최근 3개월)에 같은 Lot 의 다른 측정이 없습니다.
    </p>
    <div
      v-else
      class="max-h-[296px] overflow-y-auto"
    >
      <template
        v-for="section in sections"
        :key="section.label"
      >
        <p class="border-b border-(--sk-border-soft) bg-(--sk-muted-surface) px-4 py-1.5 sk-label">
          {{ section.label }} · {{ section.rows.length }}건
        </p>
        <ul class="divide-y divide-(--sk-border-soft) border-b border-(--sk-border-soft)">
          <li
            v-for="item in section.rows"
            :key="item.filename"
            class="flex items-center gap-2.5 px-4 py-2.5 transition-colors duration-200 hover:bg-(--sk-muted-surface)"
          >
            <AfmGroupCheck
              :checked="cart.isInGroup(item.filename)"
              label="그룹에 담기"
              :disabled="!cart.groupRoom.value && !cart.isInGroup(item.filename)"
              @toggle="cart.toggleGroup(item)"
            />
            <AfmMeasurementLine :item="item">
              <span
                v-if="item.recipeName !== history.current.recipeName"
                class="sk-meta"
              >
                다른 Recipe
              </span>
            </AfmMeasurementLine>
            <UBadge
              v-if="item.filename === filename"
              label="현재 측정"
              color="neutral"
              variant="subtle"
              class="shrink-0"
            />
            <UButton
              v-else
              size="sm"
              color="neutral"
              variant="outline"
              trailing-icon="i-lucide-arrow-up-right"
              label="상세"
              class="shrink-0"
              :to="`/afm/${toolId}/${encodeURIComponent(item.filename)}`"
              @click="cart.addToHistory(item)"
            />
          </li>
        </ul>
      </template>
    </div>

    <template
      v-if="history"
      #footer
    >
      <div class="space-y-1 sk-meta">
        <p
          v-for="note in roomNotes"
          :key="note"
          class="text-(--sk-warn)"
        >
          {{ note }}
        </p>
        <p v-if="history.noSlot">
          Slot 이 기록되지 않은 같은 Lot 측정 {{ history.noSlot }}건은 포함하지 않았습니다.
        </p>
        <p>
          이 장비의 목록(최근 3개월)에서 Lot·Slot 이 같은 측정 후보입니다. 같은 웨이퍼인지는 각 측정의 Sample ID 로 확인해 주십시오.
        </p>
      </div>
    </template>
  </AfmCard>
</template>

<script setup lang="ts">
import type { AfmHistoryPick } from '~/utils/afmLotHistory'

// 측정 상세's link to the opened measurement's neighbours: the tool's list
// (the search page's own fetch, by its shared key) narrowed to the same lot,
// split by slot. Candidates, not a confirmed wafer history — the list has no
// Sample ID. All matching and picking is utils/afmLotHistory.ts.
const props = defineProps<{
  toolId: string
  filename: string
}>()

const cart = useAfmCart(props.toolId)
const { data: files, pending, error } = useAfmDetailApi().useAfmFiles(props.toolId.toUpperCase())

const history = computed(() => lotHistory(files.value ?? [], props.filename))
const listed = computed(() => history.value ? [...history.value.wafer, ...history.value.otherSlots] : [])
const sections = computed(() => [
  { label: '같은 Slot', rows: history.value?.wafer ?? [] },
  { label: '같은 Lot · 다른 Slot', rows: history.value?.otherSlots ?? [] }
].filter(section => section.rows.length))

const sameRecipeOnly = ref(true)
const pick = (rows: typeof listed.value): AfmHistoryPick => history.value
  ? pickForGroup(rows, history.value.current, cart.groupRoom.value, cart.isInGroup, sameRecipeOnly.value)
  : { add: [], leftOut: 0, otherRecipe: 0 }
const waferPick = computed(() => pick(history.value?.wafer ?? []))
const lotPick = computed(() => pick(listed.value))

// Said before the click, not after: an add that leaves rows out names how many.
const roomNote = (label: string, { add, leftOut }: AfmHistoryPick) => leftOut
  ? `${label}: 그룹에 남은 자리가 ${cart.groupRoom.value}건이라 현재 측정에 가까운 ${add.length}건만 담기고 ${leftOut}건은 남습니다 · 그룹 최대 ${AFM_GROUP_MAX}건`
  : ''
const roomNotes = computed(() => [
  roomNote('이 Slot 담기', waferPick.value),
  history.value?.otherSlots.length ? roomNote('Lot 전체 담기', lotPick.value) : ''
].filter(Boolean))

const toast = useToast()
const add = ({ add: rows, leftOut }: AfmHistoryPick) => {
  cart.addToGroup(...rows)
  toast.add({
    title: `${rows.length}건을 그룹에 담았습니다`,
    description: leftOut ? `그룹 최대 ${AFM_GROUP_MAX}건이라 ${leftOut}건은 담지 못했습니다.` : undefined,
    icon: leftOut ? 'i-lucide-triangle-alert' : 'i-lucide-check',
    color: leftOut ? 'warning' : 'success'
  })
}
</script>
