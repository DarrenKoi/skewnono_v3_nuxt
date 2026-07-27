import assert from 'node:assert/strict'
import test from 'node:test'

import { operationalDataErrorMessage } from './operationalDataError.ts'

test('maps OpenSearch 503 to a stable unavailable message', () => {
  assert.equal(
    operationalDataErrorMessage(
      {
        statusCode: 503,
        data: { error: { code: 'activity_query_failed' } }
      },
      'fallback'
    ),
    'OpenSearch 로그를 일시적으로 조회할 수 없습니다. 잠시 후 다시 시도해 주세요.'
  )
})

test('maps admin forbidden without exposing a raw FetchError', () => {
  assert.equal(
    operationalDataErrorMessage(
      { statusCode: 403, data: { error: { code: 'forbidden' } } },
      'fallback'
    ),
    '관리자만 접근할 수 있는 페이지입니다.'
  )
})

test('uses the supplied fallback for unrelated failures', () => {
  assert.equal(
    operationalDataErrorMessage(new Error('network'), '조회에 실패했습니다.'),
    '조회에 실패했습니다.'
  )
})
