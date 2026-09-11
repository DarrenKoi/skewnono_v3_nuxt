import type { VisitCount } from '~/composables/useActivityApi'
import { shiftIsoDate } from './dateTime.ts'

export type VisitDay = VisitCount

export const visitLabel = (day: VisitDay) => `${day.date} · 페이지 조회 ${day.count.toLocaleString()}회`

export const calendarWeeks = (days: readonly VisitDay[]) => {
  if (!days.length) return []
  const first = days[0]!.date
  const last = days[days.length - 1]!.date
  const offset = (new Date(`${first}T00:00:00Z`).getUTCDay() + 6) % 7
  const start = shiftIsoDate(first, offset)
  const byDate = new Map(days.map(day => [day.date, day]))
  const weeks: { start: string, month: string, days: (VisitDay | null)[] }[] = []
  for (let date = start; date <= last; date = shiftIsoDate(date, -7)) {
    const weekDays = Array.from({ length: 7 }, (_, index) => {
      const key = shiftIsoDate(date, -index)
      return byDate.get(key) ?? null
    })
    const monthDay = weekDays.find(day => day?.date.endsWith('-01'))
    const month = monthDay?.date ?? (weeks.length === 0 ? first : null)
    weeks.push({ start: date, month: month ? `${Number(month.slice(5, 7))}월` : '', days: weekDays })
  }
  return weeks
}
