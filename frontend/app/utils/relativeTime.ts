// Korean relative-time labels for chat thread lists and message timestamps.
// Pure + deterministic: pass `now` to make it testable.

export const formatRelativeTime = (iso: string, now: Date = new Date()): string => {
  const then = new Date(iso)
  const ms = now.getTime() - then.getTime()
  if (Number.isNaN(ms)) return ''

  const sec = Math.floor(ms / 1000)
  if (sec < 60) return '방금'

  const min = Math.floor(sec / 60)
  if (min < 60) return `${min}분 전`

  const hour = Math.floor(min / 60)
  if (hour < 24) return `${hour}시간 전`

  const day = Math.floor(hour / 24)
  if (day < 7) return `${day}일 전`

  return `${then.getMonth() + 1}월 ${then.getDate()}일`
}
