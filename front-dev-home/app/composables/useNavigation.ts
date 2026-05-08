import type { ToolType, Fab } from '~/stores/navigation'
import { useNavigationStore } from '~/stores/navigation'

export const useNavigation = () => {
  const store = useNavigationStore()
  const route = useRoute()
  const router = useRouter()

  const featureEnabledForToolType = (feature: string, toolType: ToolType) => {
    if (feature === 'storage' || feature === 'recipe-search' || feature === 'recipe-tat') return toolType === 'cd-sem' || toolType === 'hv-sem'
    if (feature === 'device-statistics') return toolType === 'cd-sem'
    return false
  }

  const currentFeaturePath = (toolType: ToolType) => {
    const match = route.path.match(/\/(storage|recipe-search|recipe-tat|device-statistics)(?:\/|$)/)
    const feature = match?.[1]
    return feature && featureEnabledForToolType(feature, toolType) ? `/${feature}` : ''
  }

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
      router.push(`/ebeam/${toolType}/${fab.toLowerCase()}${currentFeaturePath(toolType)}`)
    }
  }

  return {
    ...store,
    toolTypeHref,
    navigateToToolType,
    navigateToFab
  }
}
