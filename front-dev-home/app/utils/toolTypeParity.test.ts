import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { classifyToolType } from './toolType.ts'

// 백엔드와 같은 파일을 읽습니다. 경로가 깨지면 테스트가 죽는 편이,
// 두 분류기가 조용히 갈라지는 것보다 낫습니다.
const FIXTURE = new URL(
  '../../../back_dev_home/ebeam/__fixtures__/tool_type_cases.json',
  import.meta.url
)

const { cases } = JSON.parse(readFileSync(FIXTURE, 'utf-8')) as {
  cases: { model: string, expected: string | null }[]
}

test('frontend classifier matches the shared fixture', () => {
  assert.ok(cases.length > 0, 'fixture is empty — path likely wrong')
  for (const { model, expected } of cases) {
    assert.equal(classifyToolType(model), expected, model)
  }
})
