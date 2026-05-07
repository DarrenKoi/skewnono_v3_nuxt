<template>
  <div class="px-4 py-10 text-center">
    <div class="mx-auto mb-3 inline-flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-50 text-zinc-400 ring-1 ring-zinc-100 dark:bg-zinc-900 dark:ring-zinc-800">
      <UIcon
        :name="icon"
        class="h-4 w-4"
      />
    </div>
    <p class="text-[11.5px] font-medium leading-snug text-zinc-600 dark:text-zinc-300">
      {{ title }}
    </p>
    <p class="mt-1 text-[10.5px] leading-snug text-zinc-400 dark:text-zinc-500">
      {{ line1 }}<br>{{ line2 }}
    </p>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  icon: string
  title: string
  line1: string
  line2: string
}>()
</script>
