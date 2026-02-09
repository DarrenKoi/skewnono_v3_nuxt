import { useNavigationStore } from '~/stores/navigation'

export const useRecent = () => {
  const store = useNavigationStore()

  return {
    recent: store.recent,
    addRecent: store.addRecent
  }
}
