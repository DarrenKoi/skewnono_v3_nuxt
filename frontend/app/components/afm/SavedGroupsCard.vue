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
        size="sm"
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
        class="group flex items-start gap-2 px-4 py-3 transition-colors duration-200 hover:bg-(--sk-muted-surface)"
      >
        <button
          type="button"
          class="min-w-0 flex-1 text-left"
          @click="$emit('load', group.id)"
        >
          <p class="truncate text-sm font-semibold text-(--sk-ink)">
            {{ group.name }}
          </p>
          <p
            v-if="group.description"
            class="truncate sk-meta"
          >
            {{ group.description }}
          </p>
          <p class="mt-1 flex items-center gap-2 sk-meta">
            <span class="sk-badge border border-(--sk-border-soft) bg-(--sk-muted-surface) px-2 font-sans text-xs text-(--sk-ink)">
              측정 {{ group.items.length }}건
            </span>
            {{ formatKoreanDateTime(group.createdAt) }}
          </p>
        </button>
        <UButton
          size="sm"
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
      class="px-4 py-5 text-center sk-body"
    >
      저장된 그룹이 없습니다.
      <span class="mt-1 block sk-meta">2건 이상 담은 그룹을 저장하면 다시 불러올 수 있습니다.</span>
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
