<script setup lang="ts">
useHead({
  meta: [
    { name: 'viewport', content: 'width=device-width, initial-scale=1' }
  ],
  link: [
    { rel: 'icon', type: 'image/svg+xml', sizes: 'any', href: '/favicon.svg' },
    { rel: 'icon', type: 'image/png', sizes: '256x256', href: '/favicon.png' }
  ],
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
</script>

<template>
  <UApp>
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </UApp>
</template>
