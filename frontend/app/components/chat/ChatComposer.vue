<script setup lang="ts">
const props = defineProps<{ disabled?: boolean }>()
const emit = defineEmits<{ send: [text: string] }>()

// Two-way draft so the empty-state example chips can prefill the composer.
const draft = defineModel<string>({ default: '' })

const submit = () => {
  const value = draft.value.trim()
  if (!value || props.disabled) return
  emit('send', value)
  draft.value = ''
}

const onKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}
</script>

<template>
  <div class="sk-composer-wrap">
    <div class="sk-composer-inner">
      <div class="sk-composer-card">
        <UTextarea
          v-model="draft"
          :rows="1"
          :maxrows="8"
          autoresize
          :disabled="disabled"
          placeholder="메시지를 입력하세요…"
          variant="none"
          class="sk-composer-input"
          @keydown="onKeydown"
        />
        <UButton
          icon="i-lucide-arrow-up"
          size="sm"
          :disabled="disabled || !draft.trim()"
          class="sk-composer-send"
          aria-label="보내기"
          @click="submit"
        />
      </div>
      <p class="sk-composer-hint">
        <kbd>Enter</kbd> 전송 · <kbd>Shift</kbd>+<kbd>Enter</kbd> 줄바꿈
      </p>
    </div>
  </div>
</template>

<style scoped>
.sk-composer-wrap {
  border-top: 1px solid var(--sk-border-soft);
  background: var(--sk-canvas);
  padding: 0.75rem 1.25rem 1rem;
}

.sk-composer-inner {
  width: 100%;
  max-width: 46rem;
  margin: 0 auto;
}

.sk-composer-card {
  display: flex;
  align-items: flex-end;
  gap: 0.5rem;
  /* Equal 0.875rem side insets: the text's left gap and the send button's
     right gap read as one inset. Vertical stays tight so the pill hugs one line. */
  padding: 0.375rem 0.875rem;
  border: 1px solid var(--sk-border);
  border-radius: 1.25rem;
  background: var(--sk-surface);
  transition: border-color 0.12s ease, box-shadow 0.12s ease;
}

/* A filled halo, not an outline — so it sits softer than --sk-focus-ring (45%),
   which is tuned for the 2px :focus-visible ring elsewhere in the app. */
.sk-composer-card:focus-within {
  border-color: var(--sk-accent-border);
  box-shadow: 0 0 0 3px color-mix(in oklch, var(--sk-accent) 18%, transparent);
}

.sk-composer-input {
  flex: 1;
  min-width: 0;
}

.sk-composer-input :deep(textarea) {
  padding: 0.5rem 0;
  font-size: 0.9375rem;
  line-height: 1.5;
  background: transparent;
}

/* flex-end pins the button to the last text line as the textarea grows, but the
   textarea's own 0.5rem bottom padding would drop it below that line. Lift it by
   that padding less half the button's overhang over the line box. */
.sk-composer-send {
  flex-shrink: 0;
  border-radius: 999px;
  margin-bottom: 0.3125rem;
}

.sk-composer-hint {
  margin-top: 0.5rem;
  text-align: center;
  font-size: 0.6875rem;
  color: var(--sk-ink-subtle);
}

.sk-composer-hint kbd {
  font-family: inherit;
  font-size: 0.6875rem;
  padding: 0.05rem 0.3rem;
  border-radius: 0.25rem;
  background: var(--sk-muted-surface);
  border: 1px solid var(--sk-border-soft);
}

@media (prefers-reduced-motion: reduce) {
  .sk-composer-card {
    transition: none;
  }
}
</style>
