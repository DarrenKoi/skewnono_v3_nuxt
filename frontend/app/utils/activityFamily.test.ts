import assert from 'node:assert/strict'
import test from 'node:test'
import { TOOL_FAMILY_SINCE, familyRail, toolFamilyLabel, toolFamilyNotice } from './activityFamily.ts'

const row = (family: string, total = 0, pages: { feature: string, count: number }[] = []) =>
  ({ family, total, pages })

test('the rail lists every family in a fixed order, Hitachi named on its two', () => {
  const rail = familyRail([
    row('cdsem', 6, [{ feature: 'storage', count: 39 }]),
    row('hvsem', 2),
    row('veritysem'),
    row('provision'),
    row('afm', 1)
  ])

  assert.deepEqual(
    rail.map(item => [item.vendor ?? null, item.label, item.total]),
    [
      ['Hitachi', 'CD-SEM', 6],
      ['Hitachi', 'HV-SEM', 2],
      [null, 'VeritySEM', 0],
      [null, 'Provision', 0],
      [null, 'AFM', 1]
    ]
  )
  assert.deepEqual(rail[0]!.pages, [{ feature: 'storage', count: 39 }])
})

test('the order is the rail’s, not the response’s, and a missing family is a zero', () => {
  const rail = familyRail([row('afm', 3), row('cdsem', 1)])

  assert.deepEqual(
    rail.map(item => [item.family, item.total]),
    [['cdsem', 1], ['hvsem', 0], ['veritysem', 0], ['provision', 0], ['afm', 3]]
  )
})

test('a family the frontend has no label for still shows, under its own slug', () => {
  // The backend lists families from its registry. One added there must not
  // vanish here just because this file has not caught up.
  const rail = familyRail([row('cdsem', 1), row('thickness', 4)])

  assert.deepEqual(rail[rail.length - 1], {
    family: 'thickness',
    label: 'thickness',
    total: 4,
    pages: []
  })
  assert.equal(toolFamilyLabel('thickness'), 'thickness')
  assert.equal(toolFamilyLabel('hvsem'), 'HV-SEM')
})

test('the notice shows while the window reaches before families were recorded', () => {
  const since = new Date(`${TOOL_FAMILY_SINCE}T00:00:00+09:00`)
  const threeDaysIn = new Date(since.getTime() + 3 * 86_400_000)
  const wellAfter = new Date(since.getTime() + 40 * 86_400_000)

  assert.match(toolFamilyNotice(7, threeDaysIn) ?? '', new RegExp(TOOL_FAMILY_SINCE))
  assert.equal(toolFamilyNotice(7, wellAfter), null)
  assert.equal(toolFamilyNotice(30, wellAfter), null)
})
