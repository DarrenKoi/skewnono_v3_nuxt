<script setup lang="ts">
import { useNavigationStore } from '~/stores/navigation'

definePageMeta({
  middleware: () => {
    // Read the store directly — useNavigation() also calls useRoute()/useRouter(),
    // which Nuxt warns against inside middleware. We only need `fab` here.
    const { fab } = useNavigationStore()
    const target = fab.value && fab.value !== 'all' ? fab.value : 'R3'
    return navigateTo(`/ebeam/provision/${target.toLowerCase()}`, { replace: true })
  }
})
</script>

<template>
  <div />
</template>
