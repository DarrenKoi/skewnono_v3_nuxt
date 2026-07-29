import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { SLOT_KEYS, recipeImageUrl, slotsOf } from './useRecipeParamDetail.ts'

const LOCATOR = {
  eqp_ip: '10.1.2.3',
  class_name: 'CLS',
  idw: 'IDW_A',
  idp: 'IDP_B'
}

describe('recipeImageUrl', () => {
  it('targets the tool-scoped recipe-image endpoint', () => {
    const url = recipeImageUrl('cdsem', LOCATOR, 'IMMP0001.jpeg')
    assert.ok(url.startsWith('/api/cdsem/recipe-search/recipe-image?'))
  })

  it('carries every locator field plus the name', () => {
    const params = new URLSearchParams(
      recipeImageUrl('cdsem', LOCATOR, 'IMMP0001.jpeg').split('?')[1]
    )
    assert.equal(params.get('eqp_ip'), '10.1.2.3')
    assert.equal(params.get('class_name'), 'CLS')
    assert.equal(params.get('idw'), 'IDW_A')
    assert.equal(params.get('idp'), 'IDP_B')
    assert.equal(params.get('name'), 'IMMP0001.jpeg')
  })

  it('encodes a name that would otherwise break the query string', () => {
    const url = recipeImageUrl('cdsem', LOCATOR, 'A&B 0001.jpeg')
    assert.ok(!url.includes('A&B 0001'))
    const params = new URLSearchParams(url.split('?')[1])
    assert.equal(params.get('name'), 'A&B 0001.jpeg')
  })

  it('keeps hvsem and cdsem on separate paths', () => {
    assert.notEqual(
      recipeImageUrl('cdsem', LOCATOR, 'X.jpeg'),
      recipeImageUrl('hvsem', LOCATOR, 'X.jpeg')
    )
  })
})

describe('slotsOf', () => {
  const row = {
    img_add1: 'IMMP0001',
    img_add2: 'PRMP0001',
    image_add3: 'non',
    img_meas1: 'IMMS0001',
    img_meas2: 'PRMS0001'
  }

  it('extracts exactly the five slot columns', () => {
    assert.deepEqual(Object.keys(slotsOf(row)).sort(), [...SLOT_KEYS].sort())
  })

  it('passes values through verbatim, sentinel included', () => {
    // "non" is French for "no file" and the server needs to see it — dropping
    // it here would make an absent slot indistinguishable from a missing key.
    assert.equal(slotsOf(row).image_add3, 'non')
    assert.equal(slotsOf(row).img_meas2, 'PRMS0001')
  })

  it('ignores columns that are not slots', () => {
    const withExtras = { ...row, Parameter: 'Para_1', SEQ: 3 }
    assert.deepEqual(Object.keys(slotsOf(withExtras as never)).sort(), [...SLOT_KEYS].sort())
  })
})
