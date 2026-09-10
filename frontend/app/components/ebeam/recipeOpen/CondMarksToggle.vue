<template>
  <!-- `overlay`: an icon button that sits over the image beside ✕ (the
       recipe-open modals). `bar`: a labelled button in a toolbar row (the
       live-alarm modal, which has no overlay chrome). Same state either way. -->
  <button
    type="button"
    :class="variant === 'overlay'
      ? ['rounded-(--sk-r-nav) p-1.5 text-white transition-colors duration-200',
         on ? 'bg-(--sk-ok)/80 hover:bg-(--sk-ok)' : 'bg-black/50 hover:bg-black/70']
      : ['inline-flex items-center gap-1.5 rounded-(--sk-r-sidebar) border px-2 py-1 transition-colors duration-200 sk-meta',
         on ? 'border-(--sk-ink) bg-(--sk-ink) text-(--sk-ink-fg)'
         : 'border-(--sk-border) text-(--sk-ink-muted) hover:text-(--sk-ink)']"
    :aria-pressed="on"
    :aria-label="label"
    :title="`${label} (cond.txt)`"
    @click="on = !on"
  >
    <UIcon
      name="i-lucide-crosshair"
      :class="variant === 'overlay' ? 'h-4 w-4' : 'h-3.5 w-3.5'"
    />
    <template v-if="variant === 'bar'">
      {{ label }}
    </template>
  </button>
</template>

<script setup lang="ts">
/** Show / hide the tool's marks (crosshair, white-box centre + image-centre align point) over recipe images. */
const on = defineModel<boolean>({ required: true })

withDefaults(defineProps<{
  label: string
  variant?: 'overlay' | 'bar'
}>(), { variant: 'overlay' })
</script>
