// CD-SEM 배율 ↔ 픽셀 크기 유도.
//
// 원본: docs/datatables/cdsem_mag_pixel_table.txt
//   FOV_µm       = 135000 / Mag
//   PixelSize_nm = FOV_µm × 1000 / N_pixels
//
// 135000의 단위는 µm(= 135 mm 화면폭)이다. 원본 문서는 이를 nm으로 적었으나
// 그러면 FOV가 µm으로 나오지 않는다 — 문서 쪽을 정정했다.
//
// null 규율: mock은 빈 row에 mag 0 / pixel "0,0"을 싣는다
// (msr_file/providers/mock.py:562). 135000/0은 Infinity이므로, 유효하지 않은
// 입력에는 null을 반환하고 호출부가 게이팅한다. useMsrFileApi.ts의 cd_value가
// 쓰는 것과 같은 규율이다 — 절대 0으로 강제 변환하지 않는다.

/** 1× 배율에서의 장비 화면폭 (µm). 135,000 µm = 135 mm. */
const SCREEN_WIDTH_UM = 135_000

/** 장비가 제공하는 픽셀 설정. 실사용은 512·1024가 대부분이다. */
export const PIXEL_SETTINGS = [512, 1024, 2048, 4096] as const
export type PixelSetting = typeof PIXEL_SETTINGS[number]

/** 스캔 시간 기준 픽셀 수 — 배수는 이 값 대비로 센다. */
const BASE_PIXELS = 512

const isPositive = (n: unknown): n is number =>
  typeof n === 'number' && Number.isFinite(n) && n > 0

/** 배율에서 FOV(µm). mag가 양의 유한수가 아니면 null. */
export const fovUm = (mag: number): number | null =>
  isPositive(mag) ? SCREEN_WIDTH_UM / mag : null

/** 배율에서 FOV(nm). */
export const fovNm = (mag: number): number | null => {
  const um = fovUm(mag)
  return um === null ? null : um * 1000
}

export interface PixelDims {
  x: number
  y: number
}

/**
 * `meas_condition_pixel`("512,512")을 파싱한다.
 * 빈 row 센티널 "0,0", 빈 문자열, 형식 오류는 전부 null.
 */
export const parsePixelSetting = (text: string | null | undefined): PixelDims | null => {
  if (typeof text !== 'string') return null
  const parts = text.split(',')
  if (parts.length !== 2) return null
  const x = Number(parts[0]?.trim())
  const y = Number(parts[1]?.trim())
  return isPositive(x) && isPositive(y) ? { x, y } : null
}

/**
 * 픽셀당 실제 길이(nm).
 * FOV는 **폭**이므로 비정사각 설정이 오면 x(가로 픽셀 수)를 넘겨야 한다.
 */
export const pixelSizeNm = (mag: number, pixels: number): number | null => {
  const nm = fovNm(mag)
  return nm !== null && isPositive(pixels) ? nm / pixels : null
}

/** CD 하나에 얹히는 픽셀 수. */
export const pxPerCd = (mag: number, pixels: number, cdNm: number): number | null => {
  const size = pixelSizeNm(mag, pixels)
  return size !== null && isPositive(cdNm) ? cdNm / size : null
}

/** 512 px 대비 상대 스캔 시간. 시간 ∝ X×Y이므로 픽셀 수의 제곱에 비례한다. */
export const scanTimeFactor = (pixels: number): number | null =>
  isPositive(pixels) ? (pixels / BASE_PIXELS) ** 2 : null

// ── Series (CG / GT) ────────────────────────────────────────────────────────
//
// MAG 범위가 계열마다 다르다. 판정은 반드시 모델코드 **접두사**로 한다 —
// back_dev_home/ebeam/hitachi/_tool_specs.py의 model_to_tool_type()과
// composables/useSemListApi.ts의 classifyToolType()이 쓰는 방식이다.
// TOOL_SPECS.eqp_models 목록은 mock 재료이지 분류기가 아니다: 그 목록으로
// 분류했다가 목록에 없는 실장비 8대가 오피스 화면에서 조용히 사라진 적이
// 있다(2026-07-24).

export type MagSeries = 'CG' | 'GT'

/** CG 계열 MAG (23개). 확인된 전 구간. */
const MAG_CG: readonly number[] = [
  1000, 2000, 5000, 8000, 10_000, 20_000, 50_000, 60_000, 70_000, 80_000,
  100_000, 120_000, 150_000, 180_000, 200_000, 220_000, 250_000, 300_000,
  350_000, 400_000, 420_000, 450_000, 500_000
]

/**
 * GT 계열이 500K 위로 더 갖는 구간 (5개).
 * 원본 문서가 "확인 안되지만 100000단위로 가정"이라고 명시한 값이므로
 * isAssumedMag()로 표시해 확정값과 구분한다.
 */
const MAG_GT_ASSUMED: readonly number[] = [600_000, 700_000, 800_000, 900_000, 1_000_000]

const MAG_GT: readonly number[] = [...MAG_CG, ...MAG_GT_ASSUMED]

const SERIES_PREFIXES: readonly MagSeries[] = ['CG', 'GT']

/** 모델코드 접두사로 계열을 판정한다. CD-SEM이 아니면 null. */
export const seriesFromModel = (eqpModelCd: string | null | undefined): MagSeries | null => {
  if (typeof eqpModelCd !== 'string') return null
  const code = eqpModelCd.trim().toUpperCase()
  return SERIES_PREFIXES.find(prefix => code.startsWith(prefix)) ?? null
}

export const magRange = (series: MagSeries): readonly number[] =>
  series === 'GT' ? MAG_GT : MAG_CG

/** 원본 문서에서 확인되지 않아 가정한 구간인지. */
export const isAssumedMag = (series: MagSeries, mag: number): boolean =>
  series === 'GT' && MAG_GT_ASSUMED.includes(mag)

export interface MagPixelCell {
  pixels: number
  nmPerPx: number
  /** 512 px 대비 상대 스캔 시간. */
  scanFactor: number
}

export interface MagPixelRow {
  mag: number
  fovNm: number
  /** true면 원본 문서 미확인 구간 — 화면에서 `가정` 배지를 붙인다. */
  assumed: boolean
  cells: MagPixelCell[]
}

/** 계열 전체의 Mag × Pixel 참조표. 순수 데이터이며 렌더링은 호출부가 한다. */
export const buildMagPixelTable = (series: MagSeries): MagPixelRow[] => {
  const rows: MagPixelRow[] = []
  for (const mag of magRange(series)) {
    const fov = fovNm(mag)
    if (fov === null) continue
    const cells: MagPixelCell[] = []
    for (const pixels of PIXEL_SETTINGS) {
      const factor = scanTimeFactor(pixels)
      if (factor === null) continue
      cells.push({ pixels, nmPerPx: fov / pixels, scanFactor: factor })
    }
    rows.push({ mag, fovNm: fov, assumed: isAssumedMag(series, mag), cells })
  }
  return rows
}
