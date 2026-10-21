<template>
  <img
    :src="displaySrc ?? undefined"
    @error="onError"
  >
</template>

<script setup lang="ts">
// A plain <img> that reloads on the shared 2.5s/5s budget. A cold image GET
// does the tool-FTP fetch inside the request; the cloud ingress 502s it, but
// the server still fills the cache, so a reload a moment later is a hit
// (utils/imageRetry.ts). Other attrs (alt, class, loading) fall through to the
// <img> — which is why the template must keep a single root, comment included.
const props = defineProps<{ src: string }>()

const { src: displaySrc, onError } = useAutoRetrySrc(() => props.src)
</script>
