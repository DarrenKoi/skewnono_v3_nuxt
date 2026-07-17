<script setup lang="ts">
const value = defineModel<string>()
const open = ref(false)
</script>

<template>
  <div class="border-b border-default">
    <button
      type="button"
      class="flex items-center gap-1 px-4 py-2 sk-meta w-full text-left"
      @click="open = !open"
    >
      <UIcon :name="open ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'" />
      시스템 프롬프트
    </button>
    <div v-if="open" class="px-4 pb-3">
      <UTextarea
        v-model="value"
        :rows="3"
        class="w-full"
        placeholder="이 대화의 시스템 프롬프트 (선택)"
      />
    </div>
  </div>
</template>
