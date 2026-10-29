import { joinApiPath } from '~/utils/apiPath'

// One shared cache key for /api/announcements. Mounted once in app.vue and
// reused if any other component ever needs to read it. Exported so
// /admin/announcements can refresh the banner after a post.
export const ANNOUNCEMENTS_CACHE_KEY = 'announcements'

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

export const useAnnouncementsApi = () => {
  const config = useRuntimeConfig()
  const url = joinApiPath(config.public.apiBase, '/announcements')

  const fetchAnnouncements = async (): Promise<Announcement[]> => {
    return await $fetch<Announcement[]>(url)
  }

  return { fetchAnnouncements }
}

export interface AnnouncementDraft {
  level: AnnouncementLevel
  title: string
  body: string
  dismissible: boolean
  starts_at?: string
  ends_at?: string
}

export const useAnnouncementsAdminApi = () => {
  const config = useRuntimeConfig()
  const url = joinApiPath(config.public.apiBase, '/admin/announcements')

  const fetchAll = (): Promise<Announcement[]> => $fetch<Announcement[]>(url)

  const add = (draft: AnnouncementDraft): Promise<Announcement> =>
    $fetch<Announcement>(url, { method: 'POST', body: draft })

  const remove = (id: string): Promise<{ removed: string }> =>
    $fetch<{ removed: string }>(`${url}/${encodeURIComponent(id)}`, { method: 'DELETE' })

  return { fetchAll, add, remove }
}

export const useAnnouncements = () => {
  const { fetchAnnouncements } = useAnnouncementsApi()
  return useAsyncData(ANNOUNCEMENTS_CACHE_KEY, fetchAnnouncements, {
    default: () => [] as Announcement[],
    // OnInitial so refreshNuxtData from the admin page really refetches.
    getCachedData: payloadCacheOnInitial
  })
}
