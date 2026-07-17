<script setup lang="ts">
const value = defineModel<string>()
defineProps<{ disabled?: boolean }>()
const open = ref(false)

const hasValue = computed(() => !!value.value?.trim())
</script>

<template>
  <div class="sk-sysprompt">
    <div class="sk-sysprompt-inner">
      <button
        type="button"
        class="sk-sysprompt-toggle"
        @click="open = !open"
      >
        <UIcon
          :name="open ? 'i-lucide-chevron-down' : 'i-lucide-chevron-right'"
          class="sk-sysprompt-caret"
        />
        <span>시스템 프롬프트</span>
        <span
          v-if="hasValue"
          class="sk-sysprompt-badge"
        >설정됨</span>
        <span
          v-if="disabled"
          class="sk-sysprompt-lock"
        >
          <UIcon name="i-lucide-lock" /> 대화 시작 후 고정
        </span>
      </button>
      <div
        v-if="open"
        class="sk-sysprompt-body"
      >
        <UTextarea
          v-model="value"
          :rows="3"
          class="w-full"
          placeholder="어시스턴트의 역할이나 말투를 정해 주세요 (선택)"
          :disabled="disabled"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.sk-sysprompt {
  border-bottom: 1px solid var(--sk-border-soft);
  background: var(--sk-canvas);
}

.sk-sysprompt-inner {
  max-width: 46rem;
  margin: 0 auto;
  padding: 0 1.25rem;
}

.sk-sysprompt-toggle {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  width: 100%;
  padding: 0.5rem 0;
  font-size: 0.8125rem;
  color: var(--sk-ink-muted);
  text-align: left;
}

.sk-sysprompt-caret {
  color: var(--sk-ink-subtle);
}

.sk-sysprompt-badge {
  padding: 0.05rem 0.4rem;
  border-radius: 999px;
  background: var(--sk-accent-soft);
  color: var(--sk-accent);
  font-size: 0.6875rem;
  font-weight: 600;
}

.sk-sysprompt-lock {
  display: inline-flex;
  align-items: center;
  gap: 0.2rem;
  margin-left: auto;
  font-size: 0.6875rem;
  color: var(--sk-ink-subtle);
}

.sk-sysprompt-body {
  padding-bottom: 0.75rem;
}
</style>
