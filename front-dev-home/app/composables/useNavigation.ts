import type { Category, ToolType, Fab } from '~/stores/navigation'
import { useNavigationStore } from '~/stores/navigation'

export const useNavigation = () => {
  const store = useNavigationStore()
  const router = useRouter()

  const navigateToToolType = (toolType: ToolType) => {
    store.setToolType(toolType)
    router.push(`/ebeam/${toolType}`)
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

  const navigateToCategory = (category: Category) => {
    store.setCategory(category)
    if (category === 'thickness') {
      router.push('/thickness')
    } else {
      router.push(`/ebeam/${store.toolType.value}`)
    }
  }

  return {
    ...store,
    navigateToToolType,
    navigateToFab,
    navigateToCategory
  }
}
