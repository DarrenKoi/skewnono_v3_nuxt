import { useState } from 'nuxt/app'
import { computed, readonly } from 'vue'
import { NO_FAB, hasFab, canonicalFabList } from '~/utils/fab'
import type { ToolType } from '~/utils/toolType'

export type { ToolType }
// Fab holds a fab_name value from the Flask sem-list response (e.g. "R3", "R4", "M16B").
// NO_FAB ('all') is reserved as an internal "no fab selected" sentinel and is never rendered
// in the sidebar; utils/fab resolves it to R3 wherever a URL needs a fab segment.
export type Fab = string

export interface NavigationState {
  toolType: ToolType
  fabs: string[]
  favorites: string[]
  selectedToolId: string
}

const defaultState: NavigationState = {
  toolType: 'cd-sem',
  fabs: [],
  favorites: [],
  selectedToolId: ''
}

export function useNavigationStore() {
  const state = useState<NavigationState>('navigation', () => ({ ...defaultState }))

  const setToolType = (toolType: ToolType) => {
    state.value.toolType = toolType
  }

  // The single write point for fabs. Invariant: canonical uppercase, deduped,
  // selection order preserved, sentinel dropped. fabs[0] is the primary fab.
  const setFabs = (fabs: readonly string[]) => {
    state.value.fabs = canonicalFabList(fabs)
  }

  // Single-select compatibility: every legacy caller funnels through the
  // same invariant. NO_FAB (or blank) clears the selection.
  const setFab = (fab: Fab) => {
    setFabs(hasFab(fab) ? [fab] : [])
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
    fabs: computed(() => state.value.fabs),
    // Primary-fab compatibility accessor: single-fab consumers keep reading `fab`.
    fab: computed(() => state.value.fabs[0] ?? NO_FAB),
    favorites: computed(() => state.value.favorites),
    selectedToolId: computed(() => state.value.selectedToolId),
    setToolType,
    setFabs,
    setFab,
    addFavorite,
    removeFavorite,
    toggleFavorite,
    setSelectedTool
  }
}
