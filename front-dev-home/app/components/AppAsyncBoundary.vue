<template>
  <Suspense :timeout="0">
    <slot />

    <template #fallback>
      <AppLoadingState
        :title="title"
        :description="description"
      />
    </template>
  </Suspense>
</template>

<script setup lang="ts">
// Suspense boundary for pages whose view component awaits its data in setup
// (`await useAsyncData(...)`). Without a boundary here the suspension bubbles
// up to Nuxt's own <NuxtPage> Suspense, so the router keeps the *previous*
// page on screen until the fetch resolves and the user gets no feedback at all.
// Owning the boundary lets the route commit immediately and render the loading
// state instead. `:timeout="0"` shows the fallback right away rather than
// holding the old subtree for a grace period.
//
// The default slot must have a single root element — that is a Suspense
// constraint, not one this wrapper adds.
defineProps<{
  title: string
  description?: string
}>()
</script>
