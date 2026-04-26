<script setup lang="ts">
definePageMeta({
  middleware: () => {
    const { fab } = useNavigation()
    const target = fab.value && fab.value !== 'all' ? fab.value : 'R3'
    return navigateTo(`/ebeam/provision/${target.toLowerCase()}`, { replace: true })
  }
})
</script>

<template>
  <div />
</template>
