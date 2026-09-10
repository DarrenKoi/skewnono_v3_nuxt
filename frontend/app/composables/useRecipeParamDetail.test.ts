import { describe, it } from 'node:test'
import assert from 'node:assert/strict'

import { SLOT_KEYS, paramDetailKey, recipeImageUrl, slotsOf } from './useRecipeParamDetail.ts'

const BASE = '/api'

const LOCATOR = {
  eqp_ip: '10.1.2.3',
  class_name: 'CLS',
  idw: 'IDW_A',
  idp: 'IDP_B'
}

describe('recipeImageUrl', () => {
  it('honours the runtime apiBase rather than hardcoding /api', () => {
    // Phase 3 can move the base; every neighbouring composable already routes
    // through joinApiPath, and this one used to be the exception.
    assert.ok(
      recipeImageUrl('/proxy/v2', 'cdsem', LOCATOR, 'X.jpeg')
        .startsWith('/proxy/v2/cdsem/recipe-search/recipe-image?')
    )
  })

  it('targets the tool-scoped recipe-image endpoint', () => {
    const url = recipeImageUrl(BASE, 'cdsem', LOCATOR, 'IMMP0001.jpeg')
    assert.ok(url.startsWith('/api/cdsem/recipe-search/recipe-image?'))
  })

  it('carries every locator field plus the name', () => {
    const params = new URLSearchParams(
      recipeImageUrl(BASE, 'cdsem', LOCATOR, 'IMMP0001.jpeg').split('?')[1]
    )
    assert.equal(params.get('eqp_ip'), '10.1.2.3')
    assert.equal(params.get('class_name'), 'CLS')
    assert.equal(params.get('idw'), 'IDW_A')
    assert.equal(params.get('idp'), 'IDP_B')
    assert.equal(params.get('name'), 'IMMP0001.jpeg')
  })

  it('adds preview=1 only for display URLs — download links stay untouched', () => {
    // preview asks the server for the browser-renderable rendition (TIFF →
    // WebP, 2026-08-08); the plain URL is the 원본 다운로드 promise.
    const display = new URLSearchParams(
      recipeImageUrl(BASE, 'cdsem', LOCATOR, 'IMMS0001-U.tif', { preview: true }).split('?')[1]
    )
    const plain = new URLSearchParams(
      recipeImageUrl(BASE, 'cdsem', LOCATOR, 'IMMS0001-U.tif').split('?')[1]
    )
    assert.equal(display.get('preview'), '1')
    assert.equal(plain.get('preview'), null)
  })

  it('encodes a name that would otherwise break the query string', () => {
    const url = recipeImageUrl(BASE, 'cdsem', LOCATOR, 'A&B 0001.jpeg')
    assert.ok(!url.includes('A&B 0001'))
    const params = new URLSearchParams(url.split('?')[1])
    assert.equal(params.get('name'), 'A&B 0001.jpeg')
  })

  it('keeps hvsem and cdsem on separate paths', () => {
    assert.notEqual(
      recipeImageUrl(BASE, 'cdsem', LOCATOR, 'X.jpeg'),
      recipeImageUrl(BASE, 'hvsem', LOCATOR, 'X.jpeg')
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

describe('paramDetailKey', () => {
  // Two rows of ONE parameter, as the mock really generates them: Para_13 at
  // SEQ 4/6 and at SEQ 11/15 name different files.
  const seq4 = {
    img_add1: 'IMMP0004',
    img_add2: 'PRMP0004',
    image_add3: 'I2MP0004',
    img_meas1: 'IMMS0004',
    img_meas2: 'PRMS0004'
  }
  const seq11 = {
    img_add1: 'IMMP0011',
    img_add2: 'PRMP0011',
    image_add3: 'I2MP0011',
    img_meas1: 'IMMS0011',
    img_meas2: 'PRMS0011'
  }

  it('separates two rows of the SAME parameter that name different files', () => {
    // The whole point. Keyed on the parameter alone these two collided, and the
    // second row silently showed the first row's images and settings.
    assert.notEqual(
      paramDetailKey('Para_13', seq4),
      paramDetailKey('Para_13', seq11)
    )
  })

  it('is stable for the same parameter and slots', () => {
    // Re-selecting a row already viewed must hit the cache: the raw folder is
    // immutable for a given recipe, so a second fetch would cost five FTP reads
    // for a guaranteed-identical answer.
    assert.equal(paramDetailKey('Para_13', seq4), paramDetailKey('Para_13', { ...seq4 }))
  })

  it('changes when ANY ONE of the five slots changes', () => {
    for (const slot of SLOT_KEYS) {
      assert.notEqual(
        paramDetailKey('Para_13', seq4),
        paramDetailKey('Para_13', { ...seq4, [slot]: 'OTHER000' }),
        `${slot} did not affect the key`
      )
    }
  })

  it('does not depend on the slots object insertion order', () => {
    // Read through SLOT_KEYS, not Object.values — a refresh() that rebuilt rows
    // in another shape must not miss the cache.
    const reversed = Object.fromEntries([...SLOT_KEYS].reverse().map(k => [k, seq4[k]]))
    assert.equal(paramDetailKey('Para_13', seq4), paramDetailKey('Para_13', reversed))
  })

  it('separates two parameters that share every slot', () => {
    assert.notEqual(paramDetailKey('Para_13', seq4), paramDetailKey('Para_14', seq4))
  })

  it('treats an absent slot as empty, and not as the "non" sentinel', () => {
    // '' means the column was missing; 'non' means the office said "no file".
    assert.notEqual(
      paramDetailKey('Para_1', { ...seq4, img_add2: '' }),
      paramDetailKey('Para_1', { ...seq4, img_add2: 'non' })
    )
    assert.equal(
      paramDetailKey('Para_1', { img_add1: 'A' }),
      paramDetailKey('Para_1', { img_add1: 'A', img_add2: '', image_add3: '', img_meas1: '', img_meas2: '' })
    )
  })

  it('cannot be forged by a value containing a plausible separator', () => {
    // Recipe and file names really do contain / : _ — any of them as the
    // separator would let one pair produce another pair's key.
    assert.notEqual(
      paramDetailKey('Para_1:IMMP0004', seq11),
      paramDetailKey('Para_1', { ...seq11, img_add1: 'IMMP0004' })
    )
    assert.notEqual(
      paramDetailKey('A/B', { img_add1: 'C' }),
      paramDetailKey('A', { img_add1: 'B/C' })
    )
  })
})
