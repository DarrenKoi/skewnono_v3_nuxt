<template>
  <AfmCard
    icon="i-lucide-image"
    title="프로파일 이미지"
  >
    <template #actions>
      <div class="flex items-center gap-2">
        <UBadge
          v-if="point"
          :label="`포인트 ${point}`"
          color="neutral"
          variant="subtle"
        />
        <UDropdownMenu
          v-if="url"
          :items="downloadItems"
          :content="{ align: 'end' }"
        >
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-download"
            trailing-icon="i-lucide-chevron-down"
            :loading="downloading"
            aria-label="프로파일 이미지 다운로드"
          />
        </UDropdownMenu>
      </div>
    </template>

    <AppLoadingState
      v-if="loading"
      variant="inline"
      class="h-72"
      title="이미지를 불러오는 중입니다."
    />
    <p
      v-else-if="!url"
      class="flex h-72 items-center justify-center sk-body"
    >
      프로파일 이미지가 없습니다.
    </p>
    <div
      v-else
      class="flex h-72 items-center justify-center overflow-hidden rounded-(--sk-r-chip) bg-(--sk-muted-surface)"
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
import type { DropdownMenuItem } from '@nuxt/ui'

const props = defineProps<{
  url: string | null
  point: string
  filename: string
  loading?: boolean
}>()

const toast = useToast()
const downloading = ref(false)

// PNG / JPG are drawn from the served image in the browser; 원본 is the bytes
// as served, named after their own type (SVG from the mock, webp at the office).
type Format = 'original' | 'image/png' | 'image/jpeg'

const redraw = async (source: Blob, type: string): Promise<Blob> => {
  const src = URL.createObjectURL(source)
  try {
    const img = new Image()
    img.src = src
    await img.decode()
    const canvas = document.createElement('canvas')
    canvas.width = img.naturalWidth
    canvas.height = img.naturalHeight
    const ctx = canvas.getContext('2d')!
    // JPG has no transparency; without a ground it comes out black.
    if (type === 'image/jpeg') {
      ctx.fillStyle = 'white'
      ctx.fillRect(0, 0, canvas.width, canvas.height)
    }
    ctx.drawImage(img, 0, 0)
    return await new Promise<Blob>((resolve, reject) =>
      canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('toBlob')), type, 0.95))
  } finally {
    URL.revokeObjectURL(src)
  }
}

const download = async (format: Format) => {
  if (!props.url) return
  downloading.value = true
  try {
    const served = await (await fetch(props.url)).blob()
    const blob = format === 'original' ? served : await redraw(served, format)
    downloadBlob(`${props.filename}-point${safeFilePart(props.point)}.${imageExtension(blob.type)}`, blob)
  } catch {
    toast.add({ title: '이미지를 내려받지 못했습니다', icon: 'i-lucide-triangle-alert', color: 'warning' })
  } finally {
    downloading.value = false
  }
}

const downloadItems: DropdownMenuItem[] = [
  { label: '원본', icon: 'i-lucide-file-image', onSelect: () => download('original') },
  { label: 'PNG', icon: 'i-lucide-image', onSelect: () => download('image/png') },
  { label: 'JPG', icon: 'i-lucide-image', onSelect: () => download('image/jpeg') }
]
</script>
