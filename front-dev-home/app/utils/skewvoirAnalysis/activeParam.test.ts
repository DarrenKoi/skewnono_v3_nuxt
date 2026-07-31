import { test } from 'node:test'
import assert from 'node:assert/strict'
import { resolveActiveParam, activeParamPool } from './activeParam.ts'

test('single scope honours a URL mp the focus file has', () => {
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: 'GATE_CD', focusParams: ['WAFER', 'GATE_CD'], setParams: []
  }), 'GATE_CD')
})

test('single scope falls back to the first NAMED param when the focus lacks the URL mp', () => {
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: 'GATE_CD', focusParams: ['', 'WAFER'], setParams: []
  }), 'WAFER')
})

test('set scope accepts a param the focus lacks but another set member has', () => {
  assert.equal(resolveActiveParam({
    scope: 'set', urlMp: 'GATE_CD', focusParams: ['WAFER'], setParams: ['WAFER', 'GATE_CD']
  }), 'GATE_CD')
})

test('set scope with EMPTY setParams falls back to focus rules — the set files are not loaded yet', () => {
  // shouldLoadSet() excludes the dashboard view, so scope=set + view=dashboard
  // leaves setFiles empty. Judging against an empty pool would reject every
  // parameter and corrupt the URL.
  assert.equal(resolveActiveParam({
    scope: 'set', urlMp: 'GATE_CD', focusParams: ['WAFER'], setParams: []
  }), 'WAFER')
})

test('an explicit pick of the unnamed settling MP is honoured, but never defaulted to', () => {
  // The unnamed MP's name IS the empty string, so `urlMp != null` (not truthy).
  assert.equal(resolveActiveParam({
    scope: 'set', urlMp: '', focusParams: ['', 'WAFER'], setParams: ['', 'WAFER']
  }), '')
  assert.equal(resolveActiveParam({
    scope: 'set', urlMp: undefined, focusParams: ['', 'WAFER'], setParams: ['', 'WAFER']
  }), 'WAFER')
})

test('a file whose only parameter is the unnamed MP falls back to it', () => {
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: undefined, focusParams: [''], setParams: []
  }), '')
})

test('no parameters at all yields the URL mp, else the empty string', () => {
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: 'WAFER', focusParams: [], setParams: []
  }), 'WAFER')
  assert.equal(resolveActiveParam({
    scope: 'single', urlMp: undefined, focusParams: [], setParams: []
  }), '')
})

test('activeParamPool widens to the set only under set scope with a loaded set', () => {
  assert.deepEqual(activeParamPool({
    scope: 'set', urlMp: undefined, focusParams: ['WAFER'], setParams: ['WAFER', 'GATE_CD']
  }), ['WAFER', 'GATE_CD'])
  assert.deepEqual(activeParamPool({
    scope: 'single', urlMp: undefined, focusParams: ['WAFER'], setParams: ['WAFER', 'GATE_CD']
  }), ['WAFER'])
})
