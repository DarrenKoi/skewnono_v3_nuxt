<script setup lang="ts">
useHead({
  meta: [
    { name: 'viewport', content: 'width=device-width, initial-scale=1' }
  ],
  // Icons are declared ONCE, in nuxt.config.ts (the /favicon/ set). A second
  // set here doubles Chrome's icon-candidate list, and every candidate is
  // retried on each navigation whenever the backend fails an icon fetch.
  htmlAttrs: {
    lang: 'en'
  }
})

const title = '스큐노노 v3'
const description = 'Web application for e-beam metrology, SEM management, and data analytics.'

useSeoMeta({
  title,
  description,
  ogTitle: title,
  ogDescription: description
})

// Identity gate: resolve who the visitor is before rendering the shell, so a
// blocked member id sees only the denied screen (no flash of protected UI).
// The 'activity-me' cache key is shared with the activity page, so this adds
// no extra request for allowed users.
const { error: meError } = await useActivityMe()
const accessDenied = computed(() => isAccessDeniedError(meError.value))
</script>

<template>
  <UApp>
    <AccessDeniedScreen v-if="accessDenied" />
    <template v-else>
      <!-- The banner lives inside each layout, not here: the layouts size
           themselves to the viewport (default.vue is h-screen), so a sibling
           above them pushes the whole shell down by the banner's height and
           the last rows fall below the fold. -->
      <NuxtLayout>
        <NuxtPage />
      </NuxtLayout>
    </template>
  </UApp>
</template>
