<script setup lang="ts">
import { useNavigationStore } from '~/stores/navigation'
import { fabSegment } from '~/utils/fab'

definePageMeta({
  middleware: () => {
    // Read the store directly — useNavigation() also calls useRoute()/useRouter(),
    // which Nuxt warns against inside middleware. We only need `fab` here.
    const { fab } = useNavigationStore()
    return navigateTo(`/ebeam/hv-sem/${fabSegment(fab.value)}`, { replace: true })
  }
})
</script>

<template>
  <div />
</template>
