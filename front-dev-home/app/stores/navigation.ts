import { useState } from 'nuxt/app'
import { computed, readonly } from 'vue'
import { NO_FAB, hasFab, normalizeFab } from '~/utils/fab'

export type ToolType = 'cd-sem' | 'hv-sem' | 'verity-sem' | 'provision'
// Fab holds a fab_name value from the Flask sem-list response (e.g. "R3", "R4", "M16B").
// NO_FAB ('all') is reserved as an internal "no fab selected" sentinel and is never rendered
// in the sidebar; utils/fab resolves it to R3 wherever a URL needs a fab segment.
export type Fab = string

export interface NavigationState {
  toolType: ToolType
  fab: Fab
  favorites: string[]
  selectedToolId: string
}

const defaultState: NavigationState = {
  toolType: 'cd-sem',
  fab: NO_FAB,
  favorites: [],
  selectedToolId: ''
}

export function useNavigationStore() {
  const state = useState<NavigationState>('navigation', () => ({ ...defaultState }))

  const setToolType = (toolType: ToolType) => {
    state.value.toolType = toolType
  }

  // The single write point for fab, so the store's invariant holds no matter which of the
  // ~30 callers is writing: a real fab is stored canonically uppercase, and anything empty
  // or sentinel-shaped (in any casing) is stored as exactly NO_FAB. Callers pass values
  // straight from a URL segment or an API row, whose casing varies by source DB.
  const setFab = (fab: Fab) => {
    state.value.fab = hasFab(fab) ? normalizeFab(fab) : NO_FAB
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

  const setSelectedTool = (toolId: string) => {
    state.value.selectedToolId = toolId
  }

  return {
    state: readonly(state),
    toolType: computed(() => state.value.toolType),
    fab: computed(() => state.value.fab),
    favorites: computed(() => state.value.favorites),
    selectedToolId: computed(() => state.value.selectedToolId),
    setToolType,
    setFab,
    addFavorite,
    removeFavorite,
    toggleFavorite,
    setSelectedTool
  }
}
