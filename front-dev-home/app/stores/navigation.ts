import { useState } from 'nuxt/app'
import { computed, readonly } from 'vue'

export type Category = 'ebeam' | 'afm'
export type ToolType = 'cd-sem' | 'hv-sem' | 'verity-sem' | 'provision'
// Fab holds a fab_name value from the Flask sem-list response (e.g. "R3", "R4", "M16B").
// The literal 'all' is reserved as an internal "no fab selected" sentinel and is never rendered in the sidebar.
export type Fab = string

export interface NavigationState {
  category: Category
  toolType: ToolType
  fab: Fab
  favorites: string[]
}

const defaultState: NavigationState = {
  category: 'ebeam',
  toolType: 'cd-sem',
  fab: 'all',
  favorites: []
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
    state.value.favorites = state.value.favorites.filter((favoriteId: string) => favoriteId !== toolId)
  }

  const toggleFavorite = (toolId: string) => {
    if (state.value.favorites.includes(toolId)) {
      removeFavorite(toolId)
    } else {
      addFavorite(toolId)
    }
  }

  return {
    state: readonly(state),
    category: computed(() => state.value.category),
    toolType: computed(() => state.value.toolType),
    fab: computed(() => state.value.fab),
    favorites: computed(() => state.value.favorites),
    setCategory,
    setToolType,
    setFab,
    addFavorite,
    removeFavorite,
    toggleFavorite
  }
}
