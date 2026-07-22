import type { ToolType, Fab } from '~/stores/navigation'
import { useNavigationStore } from '~/stores/navigation'
import { isFablessFeature, matchFeatureFromPath } from '~/utils/features'

export const useNavigation = () => {
  const store = useNavigationStore()
  const route = useRoute()
  const router = useRouter()

  const featureEnabledForToolType = (feature: string, toolType: ToolType) => {
    if (
      feature === 'storage'
      || feature === 'recipe-search'
      || feature === 'recipe-status'
      || feature === 'hardware'
      || feature === 'live-alarm'
      || feature === 'skewvoir'
    ) return toolType === 'cd-sem' || toolType === 'hv-sem'
    if (feature === 'device-statistics') return toolType === 'cd-sem'
    if (feature === 'skew-check') return toolType === 'cd-sem'
    return false
  }

  const currentFeature = () => matchFeatureFromPath(route.path)

  const toolTypeHref = (toolType: ToolType) => {
    const feature = currentFeature()
    const enabled = feature && featureEnabledForToolType(feature, toolType)

    if (enabled && isFablessFeature(feature)) {
      return `/ebeam/${toolType}/${feature}`
    }

    const fab = store.fab.value
    const featureSuffix = enabled ? `/${feature}` : ''
    return fab && fab !== 'all'
      ? `/ebeam/${toolType}/${fab.toLowerCase()}${featureSuffix}`
      : `/ebeam/${toolType}`
  }

  const navigateToToolType = (toolType: ToolType) => {
    store.setToolType(toolType)
    const feature = currentFeature()
    const sameFeature = feature !== '' && featureEnabledForToolType(feature, toolType)
    // Staying on the same feature keeps its query params (e.g. recipe-status
    // ?tab=) valid; landing on a different page must not inherit them.
    router.push(sameFeature
      ? { path: toolTypeHref(toolType), query: route.query }
      : toolTypeHref(toolType))
  }

  const navigateToFab = (fab: Fab) => {
    store.setFab(fab)
    const toolType = store.toolType.value
    if (fab === 'all') {
      router.push(`/ebeam/${toolType}`)
      return
    }

    const feature = currentFeature()
    const featureEnabled = feature && featureEnabledForToolType(feature, toolType)

    // Fabless features have no fab segment in the URL — store update is enough; the page reads
    // fab from the store/localStorage. Skip the router push to avoid a same-URL history entry.
    // (FabSidebar hides itself on these pages via `hideFabSidebar: true`, so this branch is
    // primarily defensive.)
    if (featureEnabled && isFablessFeature(feature)) {
      return
    }

    // Same feature, new fab: keep the feature's query params (e.g.
    // recipe-status ?tab=) so the visible state stays URL-encoded.
    if (featureEnabled) {
      router.push({ path: `/ebeam/${toolType}/${fab.toLowerCase()}/${feature}`, query: route.query })
      return
    }
    router.push(`/ebeam/${toolType}/${fab.toLowerCase()}`)
  }

  return {
    ...store,
    toolTypeHref,
    navigateToToolType,
    navigateToFab
  }
}
