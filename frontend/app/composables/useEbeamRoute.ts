export const useEbeamRoute = () => {
  const route = useRoute()
  return computed(() => route.path === '/ebeam' || route.path.startsWith('/ebeam/'))
}
