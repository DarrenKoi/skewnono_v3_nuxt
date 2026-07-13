<template>
  <div class="space-y-4">
    <EbeamFeatureHeader
      :title="`${title} — ${fab}`"
      :subtitle="subtitle"
      :eyebrow="eyebrow"
    />

    <div class="dashboard-surface rounded-2xl p-6">
      <div class="mx-auto flex max-w-md flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-zinc-300 px-6 py-14 text-center dark:border-zinc-700">
        <UIcon
          :name="icon"
          class="h-8 w-8 text-(--sk-ink-muted)"
        />
        <p class="text-sm font-medium text-zinc-700 dark:text-zinc-200">
          준비 중입니다
        </p>
        <p class="text-xs text-(--sk-ink-muted)">
          Coming soon
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{
  title: string
  subtitle?: string
  eyebrow?: string
  fab: string
  icon?: string
}>(), {
  subtitle: '',
  eyebrow: '',
  icon: 'i-lucide-construction'
})
</script>
