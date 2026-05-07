<template>
  <UModal v-model:open="open">
    <template #content>
      <div class="space-y-4 p-6">
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-bookmark-plus"
            class="h-5 w-5 text-(--sk-accent)"
          />
          <h3 class="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            프리셋으로 저장
          </h3>
        </div>

        <UFormField
          label="프리셋 이름"
          required
        >
          <UInput
            v-model="name"
            placeholder="예: M14 양산 디바이스 비교"
            maxlength="50"
            autofocus
            class="w-full"
            @keydown.enter="onConfirm"
          />
        </UFormField>

        <UFormField label="메모">
          <UTextarea
            v-model="comments"
            placeholder="이 프리셋의 용도나 맥락을 적어 주세요 (선택)"
            :rows="3"
            maxlength="200"
            class="w-full"
          />
        </UFormField>

        <div class="rounded-lg bg-zinc-100 px-3 py-2 text-xs text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400">
          <strong>저장될 디바이스:</strong> {{ selectedLots.length }}개{{ fab ? ` · ${fab}` : '' }}
        </div>

        <div class="flex justify-end gap-2">
          <UButton
            color="neutral"
            variant="ghost"
            @click="onCancel"
          >
            취소
          </UButton>
          <UButton
            color="primary"
            variant="solid"
            icon="i-lucide-bookmark-plus"
            :disabled="!canSave"
            class="bg-(--sk-accent) text-white ring-1 ring-(--sk-accent) hover:bg-(--sk-accent)/90 disabled:opacity-50"
            @click="onConfirm"
          >
            저장
          </UButton>
        </div>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
const props = defineProps<{
  selectedLots: string[]
  fab?: string
}>()

const open = defineModel<boolean>('open', { default: false })
const emit = defineEmits<{
  saved: [preset: { name: string, comments: string }]
}>()

const { addPreset } = useDevicePresets()

const name = ref('')
const comments = ref('')

const canSave = computed(() => name.value.trim().length > 0 && props.selectedLots.length > 0)

// Default name like "프리셋-05/08 14:30" — gives users a sensible name without typing,
// and the timestamp keeps later browsing chronologically meaningful.
const buildDefaultName = (): string => {
  const now = new Date()
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  const dd = String(now.getDate()).padStart(2, '0')
  const hh = String(now.getHours()).padStart(2, '0')
  const mi = String(now.getMinutes()).padStart(2, '0')
  return `프리셋-${mm}/${dd} ${hh}:${mi}`
}

const onCancel = () => {
  open.value = false
}

const onConfirm = () => {
  if (!canSave.value) return
  addPreset({
    name: name.value,
    comments: comments.value,
    lots: props.selectedLots,
    fab: props.fab
  })
  emit('saved', { name: name.value.trim(), comments: comments.value.trim() })
  open.value = false
}

watch(open, (next) => {
  if (!next) return
  name.value = buildDefaultName()
  comments.value = ''
})
</script>
