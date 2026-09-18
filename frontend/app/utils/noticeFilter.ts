// What the 공지사항 page shows for a given set of filters. Pure so node --test can pin it;
// pages/notices.vue owns the state and the paging.

import type { Notice, NoticeCategory } from '~/data/notices'

export interface NoticeFilter {
  query: string
  category: NoticeCategory | null
  area: string | null
  /** Only notices dated after this (the reader's last-seen date); null = no restriction. */
  unreadAfter: string | null
}

/** A notice's areas, in section order — the tags on its card and the area filter's values. */
export const noticeAreas = (notice: Notice): string[] => notice.sections.map(section => section.area)

export const matchesNotice = (notice: Notice, filter: NoticeFilter): boolean => {
  if (filter.category && notice.category !== filter.category) return false
  if (filter.area && !noticeAreas(notice).includes(filter.area)) return false
  if (filter.unreadAfter !== null && !(notice.date > filter.unreadAfter)) return false
  const query = filter.query.trim().toLowerCase()
  if (!query) return true
  const haystack = [
    notice.title,
    notice.category,
    ...notice.sections.flatMap(section => [section.area, ...section.items])
  ].join(' ').toLowerCase()
  return haystack.includes(query)
}

export interface NoticeMonth {
  /** '2026년 9월' */
  label: string
  notices: Notice[]
}

/** Consecutive runs of one month, in the input's (newest-first) order. */
export const groupNoticesByMonth = (notices: Notice[]): NoticeMonth[] => {
  const months: NoticeMonth[] = []
  for (const notice of notices) {
    const [year, month] = notice.date.split('-')
    const label = `${year}년 ${Number(month)}월`
    const last = months.at(-1)
    if (last?.label === label) last.notices.push(notice)
    else months.push({ label, notices: [notice] })
  }
  return months
}
