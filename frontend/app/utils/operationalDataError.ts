type ErrorShape = {
  statusCode?: number
  data?: {
    error?: { code?: string }
    data?: { error?: { code?: string } }
  }
}

export const operationalDataErrorMessage = (
  error: unknown,
  fallback: string
): string => {
  const value = error as ErrorShape | null
  const code = value?.data?.error?.code ?? value?.data?.data?.error?.code
  if (value?.statusCode === 403 || code === 'forbidden') {
    return '관리자만 접근할 수 있는 페이지입니다.'
  }
  if (
    value?.statusCode === 503
    || code === 'activity_query_failed'
    || code === 'log_query_failed'
  ) {
    return 'OpenSearch 로그를 일시적으로 조회할 수 없습니다. 잠시 후 다시 시도해 주세요.'
  }
  return fallback
}
