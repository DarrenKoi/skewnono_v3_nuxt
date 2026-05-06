// One shared cache key for /api/announcements. Mounted once in app.vue and
// reused if any other component ever needs to read it.
const ANNOUNCEMENTS_CACHE_KEY = 'announcements'

export type AnnouncementLevel = 'info' | 'warning' | 'critical'

export interface Announcement {
  id: string
  level: AnnouncementLevel
  title: string
  body?: string
  starts_at?: string
  ends_at?: string
  dismissible?: boolean
}

const joinApiPath = (base: string, path: string) => {
  const normalizedBase = base.endsWith('/') ? base.slice(0, -1) : base
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${normalizedBase}${normalizedPath}`
}

export const useAnnouncementsApi = () => {
  const config = useRuntimeConfig()
  const url = joinApiPath(config.public.apiBase, '/announcements')

  const fetchAnnouncements = async (): Promise<Announcement[]> => {
    return await $fetch<Announcement[]>(url)
  }

  return { fetchAnnouncements }
}

export const useAnnouncements = () => {
  const { fetchAnnouncements } = useAnnouncementsApi()
  return useAsyncData(ANNOUNCEMENTS_CACHE_KEY, fetchAnnouncements, {
    default: () => [] as Announcement[],
    getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
  })
}
