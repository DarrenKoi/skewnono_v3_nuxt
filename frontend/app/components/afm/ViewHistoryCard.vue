<template>
  <AfmCard
    icon="i-lucide-eye"
    title="조회 기록"
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
        @click="cart.clearHistory"
      />
    </template>

    <ul
      v-if="items.length"
      class="max-h-[296px] divide-y divide-(--sk-border-soft) overflow-y-auto"
    >
      <li
        v-for="item in items"
        :key="item.filename"
        class="flex items-center gap-2.5 px-4 py-2.5 transition-colors duration-200 hover:bg-(--sk-muted-surface)"
      >
        <AfmGroupCheck
          :checked="cart.isInGroup(item.filename)"
          label="그룹에 담기"
          :disabled="!groupRoom && !cart.isInGroup(item.filename)"
          @toggle="cart.toggleGroup(item)"
        />
        <AfmMeasurementLine :item="item">
          <span class="sk-meta">
            {{ formatKoreanDateTime(item.viewedAt) }} 조회
          </span>
        </AfmMeasurementLine>
        <UButton
          size="sm"
          color="neutral"
          variant="outline"
          trailing-icon="i-lucide-arrow-up-right"
          label="상세"
          class="shrink-0"
          @click="$emit('view-details', item)"
        />
      </li>
    </ul>
    <p
      v-else
      class="px-4 py-6 text-center sk-body"
    >
      조회 기록이 없습니다.
    </p>
  </AfmCard>
</template>

<script setup lang="ts">
import type { AfmHistoryEntry } from '~/composables/useAfmCart'

const props = defineProps<{
  toolId: string
}>()

defineEmits<{
  'view-details': [item: AfmHistoryEntry]
}>()

const cart = useAfmCart(props.toolId)
const items = cart.viewHistory
const groupRoom = cart.groupRoom
</script>
