// Skewvoir overview → detail hand-offs.
//
// The 측정 개요 (Dashboard) does not grow a mini-chart per detail view — instead
// it offers ONE-CLICK hand-off actions that land on the matching detail view
// ALREADY CONFIGURED with the site / parameter / sequence the overview had in
// focus. A hand-off is only ever generated from a CONFIRMED fact already sitting
// in memory (no new fetch): if the fact isn't there, the caller renders the
// `reason` text instead of a button that would open an empty page.
//
// Pure and framework-free (mirrors utils/skewvoirAnalysis/spatial.ts) so the
// mapping from facts → hand-off targets is unit-testable without Nuxt.
//
// Runs under raw `node --test` — sibling imports carry an explicit `.ts`
// extension.
import type { MsrFileRow } from '~/composables/useMsrFileApi'
import { isMeasuredRow } from '../msrRows.ts'
import { parseChipXY } from '../waferChip.ts'

export type HandoffKey = 'position' | 'sequence' | 'paired' | 'gallery'

export interface HandoffFacts {
  activeParam: string
  availableParams: string[]
  focusedSite: string | null
}

// A hand-off's confirmed-fact test + its atomic query patch. `query` uses the
// same three-valued shape as useSkewvoirRoute's patchQuery: a string writes the
// key, null clears it — so a caller passes this object straight through in ONE
// router.replace and never needs to know the target view's param names.
export interface HandoffTarget {
  key: HandoffKey
  label: string
  ready: boolean
  reason: string | null
  query: Record<string, string | null>
}

// Any measured row for the parameter with a coordinate the spatial view can
// place — the same chip_number parse the WaferMap / spatial workbench use.
export const hasSpatialCoordinates = (rows: MsrFileRow[], parameter: string): boolean =>
  rows.some(r => r.parameter === parameter && isMeasuredRow(r) && parseChipXY(r.chip_number) != null)

// Any measured row for the parameter — the sequence workbench needs at least
// one point to plot along the measurement order (dynamic FDC is optional; its
// own absence renders "FDC 없음" inside the workbench, not blocked here).
export const hasSequenceData = (rows: MsrFileRow[], parameter: string): boolean =>
  rows.some(r => r.parameter === parameter && isMeasuredRow(r))

// Any row carrying an image filename — the gallery review queue's evidence.
export const hasImageEvidence = (rows: MsrFileRow[], parameter: string): boolean =>
  rows.some(r => r.parameter === parameter && !!r.mp_image_name_01)

// Compute the four hand-off targets from the overview's already-loaded facts.
// `hasCoordinates` / `hasSequenceData` / `hasImages` are passed in (rather than
// rows) so this stays a pure decision function — callers derive them once
// (e.g. via the helpers above) and every hand-off consumer reuses the same
// verdict, matching the wafer map / table / chip strip that already agree on
// what counts as "measured".
export const buildHandoffs = (
  facts: HandoffFacts,
  confirmed: { coordinates: boolean, sequence: boolean, images: boolean }
): HandoffTarget[] => {
  const [firstParam, secondParam] = facts.availableParams
  const paired = facts.availableParams.length >= 2

  return [
    {
      key: 'position',
      label: '공간 pattern 자세히',
      ready: confirmed.coordinates,
      reason: confirmed.coordinates ? null : '좌표 데이터가 없어 공간 분석을 열 수 없습니다.',
      query: {
        view: 'position-stack',
        scope: 'single',
        site: facts.focusedSite,
        mp: facts.activeParam || null
      }
    },
    {
      key: 'sequence',
      label: '측정 순서와 FDC',
      ready: confirmed.sequence,
      reason: confirmed.sequence ? null : '측정 순서 데이터가 없어 Time-Series를 열 수 없습니다.',
      query: {
        view: 'time-series',
        scope: 'single'
      }
    },
    {
      key: 'paired',
      label: '짝지은 값',
      ready: paired,
      reason: paired ? null : '비교할 파라미터가 2개 이상 필요합니다.',
      query: {
        view: 'correlation',
        scope: 'single',
        x: firstParam ?? null,
        y: secondParam ?? firstParam ?? null
      }
    },
    {
      key: 'gallery',
      label: '검토할 이미지',
      ready: confirmed.images,
      reason: confirmed.images ? null : '검토할 이미지 근거가 없습니다.',
      query: {
        view: 'gallery',
        scope: 'single',
        site: facts.focusedSite,
        mp: facts.activeParam || null,
        filter: 'priority'
      }
    }
  ]
}
