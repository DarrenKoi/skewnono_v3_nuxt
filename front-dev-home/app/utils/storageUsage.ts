export const STORAGE_WARNING_THRESHOLD = 90
export const STORAGE_CRITICAL_THRESHOLD = 98

export type StorageUsageTier = 'healthy' | 'warning' | 'critical'

export const storageUsageTier = (percent: number): StorageUsageTier => {
  if (percent >= STORAGE_CRITICAL_THRESHOLD) return 'critical'
  if (percent >= STORAGE_WARNING_THRESHOLD) return 'warning'
  return 'healthy'
}
