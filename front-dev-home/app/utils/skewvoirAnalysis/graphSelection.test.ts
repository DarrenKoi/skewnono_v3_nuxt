import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  addGraphSelection,
  cdGraphId,
  fdcGraphId,
  graphSelectionIds,
  reconcileGraphSelection,
  selectCdOnly,
  toggleGraphSelection
} from './graphSelection.ts'

test('CD and same-named FDC parameters use different ids', () => {
  assert.deepEqual(
    graphSelectionIds('StigmaX', ['StigmaX']),
    ['cd:StigmaX', 'fdc:StigmaX']
  )
})

test('the default graph selection contains CD and every FDC in model order', () => {
  assert.deepEqual(
    graphSelectionIds('CD_TOP', ['StigmaX', 'Brightness']),
    ['cd:CD_TOP', 'fdc:StigmaX', 'fdc:Brightness']
  )
})

test('CD-only selection contains only the active CD graph', () => {
  assert.deepEqual(selectCdOnly('CD_TOP'), ['cd:CD_TOP'])
})

test('toggle removes a selected graph', () => {
  const selected = [cdGraphId('CD_TOP'), fdcGraphId('StigmaX')]
  assert.deepEqual(
    toggleGraphSelection(selected, fdcGraphId('StigmaX')),
    ['cd:CD_TOP']
  )
})

test('toggle adds an unselected graph', () => {
  const selected = [cdGraphId('CD_TOP'), fdcGraphId('StigmaX')]
  assert.deepEqual(
    toggleGraphSelection(selected, fdcGraphId('Brightness')),
    ['cd:CD_TOP', 'fdc:StigmaX', 'fdc:Brightness']
  )
})

test('axis reconciliation selects the full next set when the previous set was fully selected', () => {
  const previous = graphSelectionIds('CD_TOP', ['StigmaX'])
  const next = graphSelectionIds('CD_TOP', ['StigmaX', 'Brightness'])
  assert.deepEqual(
    reconcileGraphSelection(previous, previous, next),
    next
  )
})

test('axis reconciliation preserves only the intersection for a custom selection', () => {
  const previous = graphSelectionIds('CD_TOP', ['StigmaX'])
  const selected = [cdGraphId('CD_TOP')]
  const next = graphSelectionIds('CD_TOP', ['Brightness'])
  assert.deepEqual(
    reconcileGraphSelection(selected, previous, next),
    ['cd:CD_TOP']
  )
})

test('axis reconciliation preserves an intentionally empty selection', () => {
  const previous = graphSelectionIds('CD_TOP', ['StigmaX'])
  const next = graphSelectionIds('CD_TOP', ['Brightness'])
  assert.deepEqual(reconcileGraphSelection([], previous, next), [])
})

test('drill adds only the clicked FDC and preserves existing choices', () => {
  assert.deepEqual(
    addGraphSelection(
      [cdGraphId('CD_TOP'), fdcGraphId('StigmaX')],
      fdcGraphId('Brightness')
    ),
    ['cd:CD_TOP', 'fdc:StigmaX', 'fdc:Brightness']
  )
})

test('drill does not duplicate an already-selected FDC', () => {
  const selected = [cdGraphId('CD_TOP'), fdcGraphId('StigmaX')]
  assert.deepEqual(
    addGraphSelection(selected, fdcGraphId('StigmaX')),
    selected
  )
})
