import { NOTICES, type Notice } from '~/data/notices'

// Read state for 공지사항: the newest notice date this browser has seen. A notice dated
// after it is new, which is what the header's N badge shows. Empty storage means nothing
// was ever seen, so every notice is new to a first-time visitor — correct, they have not
// read any of them.
export const useNotices = () => {
  const lastSeen = usePersistedState<string>('notices-last-seen', 'sk:notices_last_seen', {
    default: () => '',
    normalize: parsed => (typeof parsed === 'string' ? parsed : ''),
    isEmpty: value => value === ''
  })

  const isNew = (notice: Notice) => notice.date > lastSeen.value
  const hasNew = computed(() => NOTICES.some(isNew))
  const markAllSeen = () => {
    if (NOTICES[0]) lastSeen.value = NOTICES[0].date
  }

  return { notices: NOTICES, isNew, hasNew, markAllSeen }
}
