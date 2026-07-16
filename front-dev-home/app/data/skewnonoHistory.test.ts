import { test } from 'node:test'
import assert from 'node:assert/strict'
import { skewnonoHistory } from './skewnonoHistory.ts'

test('lists SKEWNONO releases from v1 through the current v3', () => {
  assert.deepEqual(
    skewnonoHistory.map(({ version, releasedAt }) => ({ version, releasedAt })),
    [
      { version: 'v1', releasedAt: '2024' },
      { version: 'v2', releasedAt: '2025' },
      { version: 'v3', releasedAt: '2026.07' }
    ]
  )
  assert.deepEqual(
    skewnonoHistory.filter(version => version.current).map(version => version.version),
    ['v3']
  )
})

test('keeps legacy releases concise and gives v3 four detailed feature areas', () => {
  const [v1, v2, v3] = skewnonoHistory

  assert.deepEqual(v1?.features.map(feature => feature.title), [
    '장비 상태',
    '측정 이력',
    'FDC Sharpness'
  ])
  assert.equal(v2?.features.length, 3)
  assert.deepEqual(v3?.features.map(feature => feature.title), [
    'CD-SEM · HV-SEM 통합 관리',
    'Hardware · Calibration 분석',
    'Device Statistics 강화',
    'Skewvoir 분석'
  ])
  assert.ok(v3?.features.every(feature => feature.description))
})

test('names every supported memory category in Device Statistics', () => {
  const deviceStatistics = skewnonoHistory
    .find(release => release.current)
    ?.features.find(feature => feature.title === 'Device Statistics 강화')

  assert.ok(deviceStatistics?.description)
  assert.match(deviceStatistics.description, /DRAM/)
  assert.match(deviceStatistics.description, /NAND/)
  assert.match(deviceStatistics.description, /New Memory/)
})
