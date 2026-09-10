import { test } from 'node:test'
import assert from 'node:assert/strict'
import { ref } from 'vue'
import { usePagedRows } from './usePagedRows.ts'

const rowsOf = (n: number) => Array.from({ length: n }, (_, i) => i + 1)

test('slices the current page', () => {
  const page = ref(2)
  const { pagedRows } = usePagedRows(rowsOf(30), 25, page)

  assert.deepEqual(pagedRows.value, [26, 27, 28, 29, 30])
})

test('reports a 1-based inclusive window', () => {
  const page = ref(2)
  const { pageStart, pageEnd, pageCount, total } = usePagedRows(rowsOf(30), 25, page)

  assert.equal(pageStart.value, 26)
  assert.equal(pageEnd.value, 30)
  assert.equal(pageCount.value, 2)
  assert.equal(total.value, 30)
})

test('an empty table still reads Page 1 / 1, not 1 / 0', () => {
  const { pageCount, pageStart, pageEnd } = usePagedRows([], 25, ref(1))

  assert.equal(pageCount.value, 1)
  assert.equal(pageStart.value, 0) // "0–0 of 0", not "1–0 of 0"
  assert.equal(pageEnd.value, 0)
})

test('an exactly-full page does not add an empty trailing page', () => {
  const { pageCount } = usePagedRows(rowsOf(50), 25, ref(1))

  assert.equal(pageCount.value, 2)
})

test('tracks a reactive page size', () => {
  const page = ref(1)
  const size = ref(25)
  const { pageCount, pagedRows } = usePagedRows(rowsOf(30), size, page)

  assert.equal(pageCount.value, 2)
  size.value = 50
  assert.equal(pageCount.value, 1)
  assert.equal(pagedRows.value.length, 30)
})

test('tracks reactive rows', () => {
  const rows = ref(rowsOf(10))
  const { total, pageCount } = usePagedRows(rows, 25, ref(1))

  assert.equal(total.value, 10)
  rows.value = rowsOf(60)
  assert.equal(pageCount.value, 3)
})
