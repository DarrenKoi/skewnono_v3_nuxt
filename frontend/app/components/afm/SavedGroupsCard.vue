<template>
  <AfmCard
    icon="i-lucide-folder-open"
    title="저장된 그룹"
    :count="groups.length"
    flush
  >
    <template
      v-if="groups.length"
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
      v-if="groups.length"
      class="divide-y divide-(--sk-border-soft)"
    >
      <li
        v-for="group in groups"
        :key="group.id"
        class="group flex items-start gap-2 px-4 py-2.5 transition-colors duration-200 hover:bg-(--sk-muted-surface)"
      >
        <button
          type="button"
          class="min-w-0 flex-1 text-left"
          @click="$emit('load', group.id)"
        >
          <p class="truncate sk-value">
            {{ group.name }}
          </p>
          <p
            v-if="group.description"
            class="truncate sk-meta"
          >
            {{ group.description }}
          </p>
          <p class="mt-1 sk-meta">
            측정 {{ group.items.length }}건 · {{ formatKoreanDateTime(group.createdAt) }}
          </p>
        </button>
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          icon="i-lucide-x"
          aria-label="저장된 그룹 삭제"
          class="opacity-0 focus-visible:opacity-100 group-hover:opacity-100"
          @click="$emit('remove', group.id)"
        />
      </li>
    </ul>
    <p
      v-else
      class="px-4 py-6 text-center sk-body"
    >
      저장된 그룹이 없습니다.
    </p>
  </AfmCard>
</template>

<script setup lang="ts">
import type { AfmSavedGroup } from '~/composables/useAfmCart'

defineProps<{
  groups: AfmSavedGroup[]
}>()

defineEmits<{
  load: [groupId: string]
  remove: [groupId: string]
  clear: []
}>()
</script>
