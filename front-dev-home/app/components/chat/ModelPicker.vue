<script setup lang="ts">
import type { ChatModel } from '~/composables/useChatApi'

defineProps<{ models: ChatModel[], disabled?: boolean }>()
const model = defineModel<string>()
</script>

<template>
  <USelect
    v-model="model"
    :items="models.map(m => ({ label: m.label, value: m.id }))"
    :disabled="disabled"
    placeholder="모델 선택"
    class="min-w-48"
  />
</template>
