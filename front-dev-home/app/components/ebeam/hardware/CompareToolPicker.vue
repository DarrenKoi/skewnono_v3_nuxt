<template>
  <div class="flex flex-wrap items-center gap-2 rounded-xl bg-(--sk-surface) px-3 py-2 ring-1 ring-(--sk-border-soft)">
    <span class="inline-flex items-center gap-1.5 sk-eyebrow">
      <UIcon
        name="i-lucide-git-compare"
        class="h-3.5 w-3.5"
      />
      비교 장비
    </span>

    <!-- ◆ = the selected (primary) tool, always shown as the comparison anchor. -->
    <span class="font-mono text-[11px] font-bold text-(--sk-ink)">◆ {{ selectedEqp || '—' }}</span>

    <USelectMenu
      v-model:open="menuOpen"
      :model-value="modelValue"
      multiple
      value-key="value"
      :items="items"
      :search-input="{ placeholder: '장비 ID 검색…' }"
      placeholder="비교할 장비 선택"
      icon="i-lucide-plus"
      size="xs"
      class="min-w-[16rem] flex-1"
      :disabled="siblingIds.length === 0"
      :ui="{ itemTrailingIcon: 'hidden' }"
      @update:model-value="emit('update:modelValue', $event)"
    >
      <!-- Leading checkbox sits right before the tool name (no far-right gap);
           the default trailing check is hidden via :ui above. -->
      <template #item-leading="{ item }">
        <span
          class="flex h-4 w-4 items-center justify-center rounded border"
          :class="modelValue.includes(item.value)
            ? 'border-(--sk-ink) bg-(--sk-ink) text-white dark:text-zinc-900'
            : 'border-(--sk-border)'"
        >
          <UIcon
            v-if="modelValue.includes(item.value)"
            name="i-lucide-check"
            class="h-3 w-3"
          />
        </span>
      </template>
      <!-- Explicit close affordance (click-outside / Esc also close the menu). -->
      <template #content-bottom>
        <div class="border-t border-(--sk-border-soft) p-1">
          <UButton
            block
            size="xs"
            color="neutral"
            variant="soft"
            icon="i-lucide-check"
            @click="menuOpen = false"
          >
            닫기
          </UButton>
        </div>
      </template>
    </USelectMenu>

    <span class="font-mono text-[11px] text-(--sk-ink-muted) tabular-nums">
      동일 fab 장비 {{ siblingIds.length }}대 · 비교 {{ modelValue.length }}대
    </span>

    <div class="ml-auto flex items-center gap-1">
      <UButton
        size="xs"
        color="neutral"
        variant="ghost"
        :disabled="siblingIds.length === 0 || modelValue.length === siblingIds.length"
        @click="emit('update:modelValue', [...siblingIds])"
      >
        전체
      </UButton>
      <UButton
        size="xs"
        color="neutral"
        variant="ghost"
        :disabled="modelValue.length === 0"
        @click="emit('update:modelValue', [])"
      >
        해제
      </UButton>
    </div>
  </div>
</template>

<script setup lang="ts">
// Shared multi-tool selector for the MDC/SCE comparison views. The picked set
// is owned by the parent (page-scoped state), so this component is a controlled
// input: it reads `modelValue` and emits changes, never mutating anything.
const props = defineProps<{
  siblingIds: string[]
  selectedEqp: string
  modelValue: string[]
}>()

const emit = defineEmits<{ 'update:modelValue': [ids: string[]] }>()

// Controlled open state so the 닫기 button can close the menu; outside-click and
// Esc still close it because Reka emits update:open through this binding.
const menuOpen = ref(false)

const items = computed(() => props.siblingIds.map(id => ({ label: id, value: id })))
</script>
