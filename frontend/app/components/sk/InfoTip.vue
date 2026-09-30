<template>
  <!-- (i) 설명 아이콘. 라벨 옆에 붙여 두고 hover/focus 로만 설명을 보여 주어
       패널 본문을 어지럽히지 않는다. 툴팁 기본 슬롯은 한 줄(h-6, truncate)이라
       문장 설명이 잘리므로 여기서 높이·줄바꿈을 풀어 준다. -->
  <UTooltip
    :text="text"
    :delay-duration="150"
    :ui="{
      content: 'h-auto max-w-[19rem] items-start px-3 py-2 text-xs leading-5',
      text: 'whitespace-normal break-keep'
    }"
  >
    <button
      type="button"
      class="inline-flex rounded-full p-1 text-(--sk-ink-subtle) transition-colors duration-200 hover:text-(--sk-ink)"
      :aria-label="`${label} 설명`"
    >
      <UIcon
        name="i-lucide-info"
        class="h-3.5 w-3.5"
      />
    </button>
  </UTooltip>
</template>

<script setup lang="ts">
defineProps<{ label: string, text: string }>()
</script>
