<template>
  <AfmCard
    icon="i-lucide-layers"
    title="데이터 그룹"
    flush
  >
    <template #actions>
      <span class="sk-meta">{{ toolId.toUpperCase() }} 에서만 유지됩니다</span>
    </template>

    <!-- 그룹 and 저장된 그룹 are one flow — pick, save, load back — so they share
         a card and the load lands on the 그룹 tab. -->
    <div class="px-4 py-3">
      <SkNavPillGroup
        v-model="tab"
        :items="tabItems"
        label="데이터 그룹 보기"
      />
    </div>

    <p
      v-if="flash"
      class="mx-4 mb-3 flex items-center gap-2 rounded-(--sk-r-chip) border border-(--sk-ok-border) bg-(--sk-ok-soft) px-2.5 py-2 text-xs text-(--sk-ink)"
      role="status"
    >
      <UIcon
        name="i-lucide-circle-check"
        class="size-3.5 shrink-0 text-(--sk-ok)"
      />{{ flash }}
    </p>

    <template v-if="tab === 'group'">
      <div
        v-if="!items.length"
        class="space-y-3.5 px-4 pb-6 pt-2"
      >
        <p class="sk-body">
          그룹에 담긴 측정이 없습니다.
        </p>
        <p
          v-for="(step, i) in STEPS"
          :key="i"
          class="flex items-start gap-2.5"
        >
          <span class="flex size-[22px] shrink-0 items-center justify-center rounded-(--sk-r-sidebar) bg-(--sk-chip-bg) sk-value-num font-semibold">{{ i + 1 }}</span>
          <span class="text-[13px] leading-relaxed text-(--sk-ink-muted)">{{ step }}</span>
        </p>
      </div>
      <template v-else>
        <ul class="max-h-[430px] divide-y divide-(--sk-border-soft) overflow-y-auto border-t border-(--sk-border-soft)">
          <li
            v-for="item in sortedItems"
            :key="item.filename"
            class="flex items-start gap-2 px-4 py-2.5"
          >
            <div class="min-w-0 flex-1 space-y-1">
              <p class="flex items-baseline gap-2">
                <span class="shrink-0 font-mono text-xs tabular-nums text-(--sk-ink-muted)">
                  {{ item.formattedDate }}
                </span>
                <span class="truncate text-sm font-semibold text-(--sk-ink)">
                  {{ item.recipeName }}
                </span>
              </p>
              <p class="flex flex-wrap items-center gap-x-2 gap-y-1">
                <AfmLotSlotTags
                  :lot-id="item.lotId"
                  :slot-number="item.slotNumber"
                />
                <UBadge
                  :label="item.measuredInfo"
                  color="neutral"
                  variant="outline"
                />
              </p>
            </div>
            <UButton
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-x"
              aria-label="그룹에서 제거"
              @click="cart.removeFromGroup(item.filename)"
            />
          </li>
        </ul>

        <div class="border-t border-(--sk-border-soft) bg-(--sk-muted-surface) px-4 py-3">
          <form
            v-if="saving"
            class="space-y-2"
            @submit.prevent="confirmSave"
          >
            <p class="sk-label">
              측정 {{ items.length }}건을 그룹으로 저장합니다
            </p>
            <UInput
              v-model="groupName"
              placeholder="그룹 이름"
              aria-label="그룹 이름"
              maxlength="50"
              autofocus
              class="w-full"
            />
            <UInput
              v-model="groupDescription"
              placeholder="설명 (선택 사항)"
              aria-label="설명"
              maxlength="200"
              class="w-full"
            />
            <div class="flex justify-end gap-2">
              <UButton
                type="button"
                size="sm"
                color="neutral"
                variant="ghost"
                label="취소"
                @click="saving = false"
              />
              <UButton
                type="submit"
                size="sm"
                color="primary"
                icon="i-lucide-save"
                label="저장"
                :disabled="!groupName.trim()"
              />
            </div>
          </form>
          <div
            v-else
            class="flex gap-2"
          >
            <UButton
              block
              color="primary"
              icon="i-lucide-line-chart"
              :label="`함께 보기 · ${items.length}건`"
              class="flex-1"
              @click="$emit('see-together')"
            />
            <UButton
              color="neutral"
              variant="outline"
              icon="i-lucide-save"
              label="그룹 저장"
              @click="startSave"
            />
            <UButton
              color="neutral"
              variant="ghost"
              label="비우기"
              @click="cart.clearGroup"
            />
          </div>
        </div>
      </template>
    </template>

    <template v-else>
      <ul
        v-if="groups.length"
        class="divide-y divide-(--sk-border-soft) border-t border-(--sk-border-soft)"
      >
        <li
          v-for="group in groups"
          :key="group.id"
        >
          <div class="flex items-center gap-2.5 px-4 py-2.5">
            <UIcon
              name="i-lucide-folder"
              class="size-4 shrink-0 text-(--sk-ink-muted)"
            />
            <div class="min-w-0 flex-1">
              <p class="truncate sk-title">
                {{ group.name }}
              </p>
              <p class="truncate sk-meta">
                측정 {{ group.items.length }}건 · {{ formatKoreanDateTime(group.createdAt) }}{{ group.description && ` · ${group.description}` }}
              </p>
            </div>
            <UButton
              size="xs"
              color="neutral"
              variant="outline"
              label="불러오기"
              @click="load(group)"
            />
            <UButton
              size="xs"
              color="neutral"
              variant="ghost"
              icon="i-lucide-trash-2"
              aria-label="저장된 그룹 삭제"
              @click="cart.removeSavedGroup(group.id)"
            />
          </div>
          <!-- Loading over a non-empty group would silently drop what is in it. -->
          <div
            v-if="confirmId === group.id"
            class="mx-4 mb-3 space-y-2 rounded-(--sk-r-chip) border border-(--sk-warn-border) bg-(--sk-warn-soft) px-3 py-2.5"
          >
            <p class="text-xs leading-snug text-(--sk-ink)">
              지금 그룹에 측정 {{ items.length }}건이 있습니다. 이 그룹({{ group.items.length }}건)을 어떻게 불러올까요?
            </p>
            <div class="flex gap-1.5">
              <UButton
                size="xs"
                color="primary"
                label="바꾸기"
                @click="load(group, 'replace')"
              />
              <UButton
                size="xs"
                color="neutral"
                variant="outline"
                label="합치기"
                @click="load(group, 'merge')"
              />
              <UButton
                size="xs"
                color="neutral"
                variant="ghost"
                label="취소"
                @click="confirmId = ''"
              />
            </div>
          </div>
        </li>
      </ul>
      <p
        v-else
        class="px-4 pb-6 pt-2 text-center sk-body"
      >
        저장된 그룹이 없습니다.
      </p>
    </template>
  </AfmCard>
</template>

<script setup lang="ts">
import type { AfmSavedGroup } from '~/composables/useAfmCart'

const props = defineProps<{
  toolId: string
}>()

defineEmits<{
  'see-together': []
}>()

const STEPS = [
  '검색 결과 왼쪽의 체크박스로 측정을 담습니다.',
  '함께 보기로 담은 측정을 한 화면에서 비교합니다.',
  '자주 보는 묶음은 이름을 붙여 저장하고, 저장된 그룹 탭에서 다시 불러옵니다.'
]

const cart = useAfmCart(props.toolId)
const items = cart.groupedData
const groups = cart.savedGroups

const sortedItems = computed(() =>
  [...items.value].sort((a, b) => b.addedAt.localeCompare(a.addedAt))
)

const tab = ref<'group' | 'saved'>('group')
const tabItems = computed(() => [
  { value: 'group' as const, label: '그룹', count: items.value.length },
  { value: 'saved' as const, label: '저장된 그룹', count: groups.value.length }
])

// One line confirming the last save or load; it goes when the user moves on.
const flash = ref('')
const confirmId = ref('')
watch(tab, () => {
  flash.value = ''
  confirmId.value = ''
})

const saving = ref(false)
const groupName = ref('')
const groupDescription = ref('')

// An emptied group has nothing to save, so the form goes with it.
watch(() => items.value.length, (count) => {
  if (!count) saving.value = false
})

const startSave = () => {
  groupName.value = `그룹 ${formatDateTimeLocal(new Date().toISOString())}`
  groupDescription.value = ''
  flash.value = ''
  saving.value = true
}

const confirmSave = () => {
  const name = groupName.value.trim()
  if (!name) return
  cart.saveCurrentGroup(name, groupDescription.value.trim())
  saving.value = false
  flash.value = `'${name}' 그룹을 저장했습니다. 저장된 그룹에서 다시 불러올 수 있습니다.`
}

const load = async (group: AfmSavedGroup, mode?: 'replace' | 'merge') => {
  if (!mode && items.value.length) {
    confirmId.value = group.id
    return
  }
  cart.loadSavedGroup(group.id, mode === 'merge')
  tab.value = 'group'
  // The tab watcher clears the flash, so it is set once that has run.
  await nextTick()
  flash.value = mode === 'replace'
    ? `'${group.name}' 그룹으로 바꿨습니다.`
    : `'${group.name}' 그룹을 ${mode === 'merge' ? '합쳤습니다' : '불러왔습니다'}.`
}
</script>
