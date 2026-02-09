import { useNavigationStore } from '~/stores/navigation'

export const useFavorites = () => {
  const store = useNavigationStore()

  const isFavorite = (toolId: string) => {
    return computed(() => store.favorites.value.includes(toolId))
  }

  return {
    favorites: store.favorites,
    addFavorite: store.addFavorite,
    removeFavorite: store.removeFavorite,
    toggleFavorite: store.toggleFavorite,
    isFavorite
  }
}
