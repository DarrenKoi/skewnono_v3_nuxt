import type { ToolType, Fab } from '~/stores/navigation'
import { useNavigationStore } from '~/stores/navigation'

export const useNavigation = () => {
  const store = useNavigationStore()
  const router = useRouter()

  const toolTypeHref = (toolType: ToolType) => {
    const fab = store.fab.value
    return fab && fab !== 'all'
      ? `/ebeam/${toolType}/${fab.toLowerCase()}`
      : `/ebeam/${toolType}`
  }

  const navigateToToolType = (toolType: ToolType) => {
    store.setToolType(toolType)
    router.push(toolTypeHref(toolType))
  }

  const navigateToFab = (fab: Fab) => {
    store.setFab(fab)
    const toolType = store.toolType.value
    if (fab === 'all') {
      router.push(`/ebeam/${toolType}`)
    } else {
      router.push(`/ebeam/${toolType}/${fab.toLowerCase()}`)
    }
  }

  return {
    ...store,
    toolTypeHref,
    navigateToToolType,
    navigateToFab
  }
}
