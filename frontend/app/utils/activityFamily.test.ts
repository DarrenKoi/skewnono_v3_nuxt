import assert from 'node:assert/strict'
import test from 'node:test'
import { TOOL_FAMILY_SINCE, familyRail, toolFamilyNotice } from './activityFamily.ts'

const row = (family: string, total = 0, pages: { feature: string, count: number }[] = []) =>
  ({ family, total, pages })

test('each family row gets its label, with Hitachi named on its two', () => {
  // Order and zero rows are the backend's promise (every family, registry
  // order), so the rail keeps what it is given and only names it.
  const rail = familyRail([
    row('cdsem', 6, [{ feature: 'storage', count: 39 }]),
    row('hvsem', 2),
    row('veritysem'),
    row('provision'),
    row('afm', 1)
  ])

  assert.deepEqual(
    rail.map(item => [item.key, item.prefix ?? null, item.label, item.total]),
    [
      ['cdsem', 'Hitachi', 'CD-SEM', 6],
      ['hvsem', 'Hitachi', 'HV-SEM', 2],
      ['veritysem', null, 'VeritySEM', 0],
      ['provision', null, 'Provision', 0],
      ['afm', null, 'AFM', 1]
    ]
  )
  assert.deepEqual(rail[0]!.pages, [{ feature: 'storage', count: 39 }])
})

test('a family the frontend has no label for still shows, under its own slug', () => {
  // The backend lists families from its registry. One added there must not
  // vanish here just because this file has not caught up.
  assert.deepEqual(familyRail([row('thickness', 4)]), [
    { key: 'thickness', label: 'thickness', total: 4, pages: [] }
  ])
})

test('the notice shows while the window reaches before families were recorded', () => {
  const since = new Date(`${TOOL_FAMILY_SINCE}T00:00:00+09:00`)
  const threeDaysIn = new Date(since.getTime() + 3 * 86_400_000)
  const wellAfter = new Date(since.getTime() + 40 * 86_400_000)

  assert.match(toolFamilyNotice(7, threeDaysIn) ?? '', new RegExp(TOOL_FAMILY_SINCE))
  assert.equal(toolFamilyNotice(7, wellAfter), null)
  assert.equal(toolFamilyNotice(30, wellAfter), null)
})
