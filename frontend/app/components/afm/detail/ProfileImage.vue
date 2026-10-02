<template>
  <AfmCard
    icon="i-lucide-image"
    title="프로파일 이미지"
    :subject="point ? `포인트 ${point}` : undefined"
  >
    <template
      v-if="url"
      #actions
    >
      <UButton
        :to="url"
        external
        :download="`${filename}-point${safeFilePart(point)}.svg`"
        size="sm"
        color="neutral"
        variant="ghost"
        icon="i-lucide-download"
        aria-label="프로파일 이미지 다운로드"
      />
    </template>

    <AppLoadingState
      v-if="loading"
      variant="inline"
      class="h-full min-h-80"
      title="이미지를 불러오는 중입니다."
    />
    <p
      v-else-if="!url"
      class="flex h-full min-h-80 items-center justify-center sk-body"
    >
      프로파일 이미지가 없습니다.
    </p>
    <div
      v-else
      class="flex h-full min-h-80 items-center justify-center overflow-hidden rounded-(--sk-r-chip) bg-(--sk-muted-surface)"
    >
      <img
        :src="url"
        :alt="`포인트 ${point} 프로파일 이미지`"
        class="max-h-full max-w-full object-contain"
      >
    </div>
  </AfmCard>
</template>

<script setup lang="ts">
defineProps<{
  url: string | null
  point: string
  filename: string
  loading?: boolean
}>()
</script>
