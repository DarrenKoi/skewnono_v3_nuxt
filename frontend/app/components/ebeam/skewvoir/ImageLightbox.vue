<template>
  <Teleport to="body">
    <div
      v-if="modelValue"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-6"
      role="dialog"
      aria-modal="true"
      @click="close"
    >
      <div
        class="relative h-full w-full max-w-5xl"
        @click.stop
      >
        <EbeamSkewvoirZoomableImage
          :key="modelValue"
          :src="modelValue"
          class="h-full w-full"
        />
      </div>
      <button
        type="button"
        class="absolute top-4 right-4 rounded-(--sk-r-nav) bg-black/50 p-2 text-white transition-colors duration-200 hover:bg-black/70"
        aria-label="닫기"
        @click="close"
      >
        <UIcon
          name="i-lucide-x"
          class="h-5 w-5"
        />
      </button>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
// A single enlarged, pan/zoomable image over a dimmed backdrop. `modelValue` is
// the image URL (null = closed); backdrop / ✕ / Esc all dismiss.
const props = defineProps<{ modelValue: string | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: string | null] }>()

const close = () => emit('update:modelValue', null)
const onKey = (e: KeyboardEvent) => {
  if (e.key === 'Escape') close()
}

watch(() => props.modelValue, (v) => {
  if (!import.meta.client) return
  if (v) window.addEventListener('keydown', onKey)
  else window.removeEventListener('keydown', onKey)
})
onBeforeUnmount(() => {
  if (import.meta.client) window.removeEventListener('keydown', onKey)
})
</script>
