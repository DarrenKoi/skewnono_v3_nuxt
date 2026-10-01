<template>
  <AfmCard
    icon="i-lucide-layers"
    title="데이터 그룹"
    :count="items.length"
    flush
  >
    <template
      v-if="items.length"
      #actions
    >
      <UButton
        size="xs"
        color="neutral"
        variant="ghost"
        label="전체 삭제"
        @click="$emit('clear')"
      />
    </template>

    <ul
      v-if="items.length"
      class="divide-y divide-(--sk-border-soft)"
    >
      <li
        v-for="item in sortedItems"
        :key="item.filename"
        class="group flex items-start gap-2 px-4 py-2.5"
      >
        <div class="min-w-0 flex-1">
          <p class="truncate sk-value">
            {{ item.formattedDate }} · {{ item.recipeName }} · {{ item.lotId }}
          </p>
          <p class="truncate sk-meta">
            Slot {{ item.slotNumber }} · {{ item.measuredInfo }}
          </p>
        </div>
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-x"
          aria-label="그룹에서 제거"
          class="opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
          @click="$emit('remove', item.filename)"
        />
      </li>
    </ul>
    <p
      v-else
      class="px-4 py-6 text-center sk-body"
    >
      그룹에 담긴 측정이 없습니다.
    </p>

    <template
      v-if="items.length"
      #footer
    >
      <div class="flex flex-wrap items-center gap-2">
        <UButton
          size="xs"
          color="primary"
          icon="i-lucide-line-chart"
          label="함께 보기"
          @click="$emit('see-together')"
        />
        <UButton
          v-if="items.length > 1"
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-save"
          label="그룹 저장"
          @click="openSaveDialog"
        />
      </div>
    </template>

    <UModal
      v-model:open="showSaveDialog"
      title="그룹 저장"
      :description="`측정 ${items.length}건을 그룹으로 저장합니다.`"
      :ui="{ footer: 'justify-end' }"
    >
      <template #body>
        <div class="space-y-4">
          <UFormField
            label="그룹 이름"
            required
          >
            <UInput
              v-model="groupName"
              maxlength="50"
              autofocus
              class="w-full"
            />
          </UFormField>
          <UFormField label="설명">
            <UTextarea
              v-model="groupDescription"
              placeholder="선택 사항입니다."
              :rows="3"
              maxlength="200"
              class="w-full"
            />
          </UFormField>
        </div>
      </template>
      <template #footer>
        <UButton
          color="neutral"
          variant="ghost"
          label="취소"
          @click="showSaveDialog = false"
        />
        <UButton
          color="primary"
          icon="i-lucide-save"
          label="그룹 저장"
          :disabled="!groupName.trim()"
          @click="confirmSave"
        />
      </template>
    </UModal>
  </AfmCard>
</template>

<script setup lang="ts">
import type { AfmGroupedEntry } from '~/composables/useAfmCart'

const props = defineProps<{
  items: AfmGroupedEntry[]
}>()

const emit = defineEmits<{
  'remove': [filename: string]
  'clear': []
  'see-together': []
  'save': [payload: { name: string, description: string }]
}>()

const sortedItems = computed(() =>
  [...props.items].sort((a, b) => b.addedAt.localeCompare(a.addedAt))
)

const showSaveDialog = ref(false)
const groupName = ref('')
const groupDescription = ref('')

const openSaveDialog = () => {
  groupName.value = `그룹 ${formatDateTimeLocal(new Date().toISOString())}`
  groupDescription.value = ''
  showSaveDialog.value = true
}

const confirmSave = () => {
  const name = groupName.value.trim()
  if (!name) return
  emit('save', { name, description: groupDescription.value.trim() })
  showSaveDialog.value = false
}
</script>
