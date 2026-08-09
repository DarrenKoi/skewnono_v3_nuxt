<script setup lang="ts">
import { useNavigationStore } from '~/stores/navigation'
import { buildFabSegment } from '~/utils/fab'

definePageMeta({
  middleware: () => {
    // Read the store directly — useNavigation() also calls useRoute()/useRouter(),
    // which Nuxt warns against inside middleware. We only need `fab` here.
    const { fabs } = useNavigationStore()
    return navigateTo(`/ebeam/veritysem/${buildFabSegment(fabs.value)}`, { replace: true })
  }
})
</script>

<template>
  <div />
</template>
