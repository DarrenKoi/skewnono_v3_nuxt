<script setup lang="ts">
import { useNavigationStore } from '~/stores/navigation'

// Redirect-only page: route to the user's last-visited fab (restored by persist-fab.client.ts),
// or to R3 on first visit (first item under our R&D-first sort order).
// We use router.replace synchronously instead of `await navigateTo` because top-level await
// in <script setup> suspends rendering and leaves an empty Vue root mounted at the new URL.
definePageMeta({
  middleware: () => {
    // Read the store directly — useNavigation() also calls useRoute()/useRouter(),
    // which Nuxt warns against inside middleware. We only need `fab` here.
    const { fab } = useNavigationStore()
    const target = fab.value && fab.value !== 'all' ? fab.value : 'R3'
    return navigateTo(`/ebeam/cd-sem/${target.toLowerCase()}`, { replace: true })
  }
})
</script>

<template>
  <div />
</template>
