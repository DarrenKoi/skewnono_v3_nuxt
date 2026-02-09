export type Category = 'ebeam' | 'thickness'
export type ToolType = 'cd-sem' | 'hv-sem' | 'verity-sem' | 'provision'
export type Fab = 'all' | 'R3' | 'M11' | 'M12' | 'M14' | 'M15' | 'M16'

export interface NavigationState {
  category: Category
  toolType: ToolType
  fab: Fab
  favorites: string[]
  recent: string[]
}

const defaultState: NavigationState = {
  category: 'ebeam',
  toolType: 'cd-sem',
  fab: 'all',
  favorites: [],
  recent: []
}

export function useNavigationStore() {
  const state = useState<NavigationState>('navigation', () => ({ ...defaultState }))

  const setCategory = (category: Category) => {
    state.value.category = category
  }

  const setToolType = (toolType: ToolType) => {
    state.value.toolType = toolType
  }

  const setFab = (fab: Fab) => {
    state.value.fab = fab
  }

  const addFavorite = (toolId: string) => {
    if (!state.value.favorites.includes(toolId)) {
      state.value.favorites.push(toolId)
    }
  }

  const removeFavorite = (toolId: string) => {
    state.value.favorites = state.value.favorites.filter(f => f !== toolId)
  }

  const toggleFavorite = (toolId: string) => {
    if (state.value.favorites.includes(toolId)) {
      removeFavorite(toolId)
    } else {
      addFavorite(toolId)
    }
  }

  const addRecent = (toolId: string) => {
    state.value.recent = [toolId, ...state.value.recent.filter(r => r !== toolId)].slice(0, 10)
  }

  return {
    state: readonly(state),
    category: computed(() => state.value.category),
    toolType: computed(() => state.value.toolType),
    fab: computed(() => state.value.fab),
    favorites: computed(() => state.value.favorites),
    recent: computed(() => state.value.recent),
    setCategory,
    setToolType,
    setFab,
    addFavorite,
    removeFavorite,
    toggleFavorite,
    addRecent
  }
}
