<script setup lang="ts">
const props = defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{ send: [text: string] }>()
const text = ref('')

const submit = () => {
  const value = text.value.trim()
  if (!value || props.disabled) return
  emit('send', value)
  text.value = ''
}

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="flex items-end gap-2 border-t border-default p-3">
    <UTextarea
      v-model="text"
      :rows="1"
      autoresize
      :disabled="disabled"
      placeholder="메시지를 입력하세요 (Enter 전송, Shift+Enter 줄바꿈)"
      class="flex-1"
      @keydown="onKeydown"
    />
    <UButton
      icon="i-lucide-send"
      :disabled="disabled || !text.trim()"
      @click="submit"
    />
  </div>
</template>
