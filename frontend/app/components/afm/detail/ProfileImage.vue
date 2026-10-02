<template>
  <AfmCard
    icon="i-lucide-image"
    title="프로파일 이미지"
    :subject="point ? `포인트 ${point}` : undefined"
  >
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
      class="relative flex h-full min-h-80 items-center justify-center overflow-hidden rounded-(--sk-r-chip) bg-(--sk-muted-surface)"
    >
      <!-- In the image area, not the header: a long point name in the header
           badge would otherwise push the button onto a line of its own. -->
      <UButton
        :to="url"
        external
        :download="`${filename}-point${safeFilePart(point)}.svg`"
        size="sm"
        color="neutral"
        variant="outline"
        icon="i-lucide-download"
        aria-label="프로파일 이미지 다운로드"
        class="absolute top-2 right-2 bg-(--sk-surface)"
      />
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
