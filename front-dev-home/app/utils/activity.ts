import type { DailyCount } from '~/composables/useActivityApi'

const FEATURE_LABELS: Record<string, string> = {
  activity: '사용 통계',
  admin_logs: '운영 로그',
  afm: 'AFM',
  announcements: '공지사항',
  api_tokens: 'API 토큰',
  cdsem: 'CD-SEM',
  cdsem_device_statistics: '디바이스 통계',
  cdsem_storage: 'CD-SEM Storage',
  equipment: '장비 현황',
  fail_issue: 'Fail Issue',
  health: '서비스 상태',
  hvsem: 'HV-SEM',
  hvsem_storage: 'HV-SEM Storage',
  recipe_search: 'Recipe 검색',
  recipe_tat: 'Recipe TAT',
  sem_list: 'SEM List'
}

export const activityFeatureLabel = (feature: string | null | undefined): string => {
  if (!feature) return '—'
  return FEATURE_LABELS[feature]
    ?? feature
      .split('_')
      .filter(Boolean)
      .map(part => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ')
}

const sumCounts = (series: DailyCount[]): number =>
  series.reduce((sum, day) => sum + day.count, 0)

export interface PersonalActivityInsights {
  recent7Requests: number
  previous7Requests: number
  activeDays7: number
  averagePerActiveDay30: number
  changePercent: number | null
}

export const summarizePersonalActivity = (series: DailyCount[]): PersonalActivityInsights => {
  const recent7 = series.slice(-7)
  const previous7 = series.slice(-14, -7)
  const recent7Requests = sumCounts(recent7)
  const previous7Requests = sumCounts(previous7)
  const activeDays30 = series.filter(day => day.count > 0).length
  const total30 = sumCounts(series)

  return {
    recent7Requests,
    previous7Requests,
    activeDays7: recent7.filter(day => day.count > 0).length,
    averagePerActiveDay30: activeDays30 > 0 ? Math.round((total30 / activeDays30) * 10) / 10 : 0,
    changePercent: previous7Requests > 0
      ? Math.round(((recent7Requests - previous7Requests) / previous7Requests) * 100)
      : null
  }
}
