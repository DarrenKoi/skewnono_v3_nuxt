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

/**
 * 계열을 대표하는 실제 장비 모델명. 현장에서 'CG'/'GT'라는 접두사보다 모델명으로
 * 부르므로 UI 레이블은 이쪽을 쓴다. 판정 키는 접두사 그대로 두고 표시만 바꾸는
 * 것이라, seriesFromModel()이 접두사 매칭인 한 두 값은 어긋날 수 없다 —
 * 그 불변식은 테스트가 지킨다.
 */
export const SERIES_MODEL: Readonly<Record<MagSeries, string>> = {
  CG: 'CG6300',
  GT: 'GT2000'
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

// ── 셋업 역산 ───────────────────────────────────────────────────────────────
//
// 제약이 둘이고 서로 반대 방향으로 당긴다.
//   ① FOV 제약  — 패턴 N개 + 여유 마진이 화면에 다 들어와야 한다 → 배율 상한
//   ② 픽셀 제약 — CD 하나에 픽셀이 충분히 얹혀야 측정된다      → 픽셀 하한
// 그래서 답은 하나가 아니라 성립 구간이고, 추천은 그 구간의 한 점이다.

/** 여유 마진 프리셋 (각 변 기준). 배율이 이산값이라 자유 입력은 없는 정밀도를 시사한다. */
export const MARGIN_PRESETS = [0, 0.05, 0.10, 0.15, 0.20] as const
export const DEFAULT_MARGIN = 0.10
export const DEFAULT_PATTERN_COUNT = 8

/**
 * CD 하나를 신뢰성 있게 측정하기 위한 최소 픽셀 수 — **잠정값**.
 * 사내 계측 기준이 아직 정해지지 않았다(사용자 확인 2026-07-25). 화면에서
 * 조정 가능하게 열어두었으므로, 기준이 확정되면 이 상수만 바꾸면 된다.
 */
export const DEFAULT_MIN_PX_PER_CD = 8

/**
 * 패턴 span과 여유 마진을 담기 위해 필요한 FOV(nm).
 *
 * 패턴은 화면 가운데에 놓이고 각 변에 marginRatio만큼 빈 공간이 필요하므로,
 * 패턴이 차지하는 비율은 (1 − 2r)이다. 마진 10%면 패턴은 FOV의 80%.
 *
 * 이 값은 렌더링용이 아니라 **배율 선택을 구속하는 값**이다. 마진을 빼면
 * 패턴이 화면 끝에 붙는 배율이 추천된다.
 */
export const requiredFovNm = (
  patternCount: number,
  pitchNm: number,
  marginRatio: number
): number | null => {
  if (!isPositive(patternCount) || !isPositive(pitchNm)) return null
  if (typeof marginRatio !== 'number' || !Number.isFinite(marginRatio)) return null
  if (marginRatio < 0 || marginRatio >= 0.5) return null
  return (patternCount * pitchNm) / (1 - 2 * marginRatio)
}

export type CellVerdict = 'ok' | 'under-pixel' | 'over-fov'

/** 표의 한 칸 판정. FOV 실패와 픽셀 실패는 원인이 달라 구분해서 표시한다. */
export const cellVerdict = (
  mag: number,
  pixels: number,
  cdNm: number,
  requiredFov: number,
  minPxPerCd: number
): CellVerdict | null => {
  const fov = fovNm(mag)
  if (fov === null) return null
  if (fov < requiredFov) return 'over-fov'
  const ratio = pxPerCd(mag, pixels, cdNm)
  if (ratio === null) return null
  return ratio >= minPxPerCd ? 'ok' : 'under-pixel'
}

export interface CalcInput {
  series: MagSeries
  cdNm: number
  /** null이면 CD × 2 (bar:space 1:1)로 가정한다. */
  pitchNm: number | null
  patternCount: number
  marginRatio: number
  minPxPerCd: number
}

export interface Recommendation {
  requiredFovNm: number
  effectivePitchNm: number
  /** true면 pitch를 CD × 2로 가정했다 — 화면에 밝힌다. */
  pitchAssumed: boolean
  mag: number | null
  pixels: number | null
  nmPerPx: number | null
  pxPerCd: number | null
  scanFactor: number | null
  reason: 'ok' | 'no-mag' | 'no-pixels'
}

/**
 * 배율은 높을수록 FOV가 좁아 px/CD가 커지므로, 패턴이 들어오는 한도 안에서
 * **가장 높은 배율**이 해상도상 최적이다. 픽셀 수는 기준만 넘으면 더 키울
 * 이유가 없고 스캔 시간만 제곱으로 늘어나므로 **가장 작은 값**을 고른다.
 */
export const recommend = (calc: CalcInput): Recommendation | null => {
  const { series, cdNm, patternCount, marginRatio, minPxPerCd } = calc
  if (!isPositive(cdNm) || !isPositive(minPxPerCd)) return null

  const pitchAssumed = calc.pitchNm === null
  const effectivePitchNm = pitchAssumed ? cdNm * 2 : calc.pitchNm
  // Domain rule (user-confirmed 2026-07-25): pitch can never be smaller than CD --
  // a bar cannot be wider than the repeat unit it sits in. Equality is rejected
  // too, deliberately: pitch == CD means zero space between bars, which is
  // physically meaningless for a line/space pattern. Do not relax this guard.
  if (!isPositive(effectivePitchNm) || effectivePitchNm <= cdNm) return null

  const required = requiredFovNm(patternCount, effectivePitchNm, marginRatio)
  if (required === null) return null

  const base = { requiredFovNm: required, effectivePitchNm, pitchAssumed }
  const empty = { nmPerPx: null, pxPerCd: null, scanFactor: null }

  const fitting = magRange(series).filter((mag) => {
    const fov = fovNm(mag)
    return fov !== null && fov >= required
  })
  if (fitting.length === 0) {
    return { ...base, ...empty, mag: null, pixels: null, reason: 'no-mag' }
  }

  const mag = Math.max(...fitting)
  const pixels = PIXEL_SETTINGS.find((p) => {
    const ratio = pxPerCd(mag, p, cdNm)
    return ratio !== null && ratio >= minPxPerCd
  })
  if (pixels === undefined) {
    return { ...base, ...empty, mag, pixels: null, reason: 'no-pixels' }
  }

  return {
    ...base,
    mag,
    pixels,
    nmPerPx: pixelSizeNm(mag, pixels),
    pxPerCd: pxPerCd(mag, pixels, cdNm),
    scanFactor: scanTimeFactor(pixels),
    reason: 'ok'
  }
}

export interface MarginSensitivityRow {
  marginRatio: number
  requiredFovNm: number | null
  mag: number | null
}

/**
 * 마진 프리셋별 결과. 배율이 이산값이라 마진이 연속적으로 반응하지 않는다 —
 * 5%와 10%가 같은 배율로 떨어지는 구간이 있다. 지금 마진에 여유가 얼마나
 * 남았는지 보여주는 것이 목적이다.
 */
export const marginSensitivity = (calc: CalcInput): MarginSensitivityRow[] =>
  MARGIN_PRESETS.map((marginRatio) => {
    const rec = recommend({ ...calc, marginRatio })
    return {
      marginRatio,
      requiredFovNm: rec?.requiredFovNm ?? null,
      mag: rec?.mag ?? null
    }
  })

// ── 경계 확대 뷰의 신호 모델 ────────────────────────────────────────────────
//
// 이 블록의 규율은 하나다: **경계 프로파일은 픽셀 설정을 인자로 받지 않는다.**
//
// 이전 구현은 번짐 폭을 `픽셀크기 × 1.5`로 잡았다. 그러면 번짐이 항상 ±1.5칸을
// 차지하므로 512든 4096이든 그림이 사실상 같아지고("경계에 몇 칸이 걸리는가"가
// 정의상 상수), 게다가 "픽셀을 늘리면 경계가 물리적으로 얇아진다"는 거짓을
// 그리게 된다. 실제로는 경계 번짐 폭(빔 직경 + 상호작용 부피 + 측벽 기울기)이
// nm 단위로 고정돼 있고, 픽셀 수를 올릴 때 달라지는 것은 그 고정된 폭 위에
// 샘플이 몇 개 얹히느냐다. 그래서 여기서는 연속 신호를 먼저 정의하고(픽셀
// 무관), 픽셀은 그 신호를 footprint로 적분해서 얻는다.

/**
 * 경계 전이 폭(nm) — **설명용 대표값**이지 장비 실측 스펙이 아니다.
 * CD-SEM의 경계 번짐은 빔 직경·상호작용 부피·측벽 기울기가 함께 만드는 값이라
 * 장비·조건마다 다르다. 화면에서도 대표값임을 밝히고 쓴다.
 */
export const SEM_EDGE_WIDTH_NM = 3

/** 확대 창의 폭 — 거친 쪽 픽셀 설정 기준 픽셀 개수. 셀 수 있을 만큼만 담는다. */
export const EDGE_WINDOW_PX = 12

/** 신호 레벨(0..1). 컴포넌트의 색 램프도 이 값을 기준점으로 쓴다. */
export const SEM_LEVELS = { space: 0.06, core: 0.42, rim: 1 } as const

/** 경계 피크가 base 위에 얹히는 최대 증가분. */
const RIM_GAIN = 0.72

/** 픽셀 하나를 적분할 때 쓰는 분할 수. */
const FOOTPRINT_SUBSAMPLES = 16

const clamp01 = (v: number): number => Math.min(1, Math.max(0, v))

/**
 * 경계 중심 x=0 기준 연속 밝기(0..1). bar 안쪽이 음수, space 쪽이 양수.
 *
 * 인자에 픽셀 크기가 **없다**는 점이 이 함수의 전부다 — 이것이 픽셀 설정과
 * 무관한 시료 쪽 사실이고, 샘플링은 samplePixelNm()이 따로 한다.
 */
export const edgeIntensity = (xNm: number): number => {
  const t = clamp01(xNm / SEM_EDGE_WIDTH_NM + 0.5)
  const smooth = t * t * (3 - 2 * t)
  const base = SEM_LEVELS.core + (SEM_LEVELS.space - SEM_LEVELS.core) * smooth
  const sigma = SEM_EDGE_WIDTH_NM * 0.5
  const rim = RIM_GAIN * Math.exp(-((xNm / sigma) ** 2))
  return Math.min(SEM_LEVELS.rim, base + rim)
}

/**
 * 픽셀 하나의 값 = 그 픽셀이 덮는 구간의 신호 평균.
 * 큰 픽셀이 경계 피크를 뭉개는 이유가 여기 있다 — 피크가 배경과 함께 평균된다.
 */
export const samplePixelNm = (centerNm: number, nmPerPx: number): number | null => {
  if (!isPositive(nmPerPx) || !Number.isFinite(centerNm)) return null
  let sum = 0
  for (let k = 0; k < FOOTPRINT_SUBSAMPLES; k++) {
    sum += edgeIntensity(centerNm + ((k + 0.5) / FOOTPRINT_SUBSAMPLES - 0.5) * nmPerPx)
  }
  return sum / FOOTPRINT_SUBSAMPLES
}

/**
 * 확대 창의 반폭(nm). 거친 쪽 설정에서 EDGE_WINDOW_PX개가 들어가게 잡되,
 * 이웃 경계까지 넘어가지 않도록 CD/2 · space/2로 자른다.
 *
 * 창을 **nm으로** 고정하는 것이 핵심이다. 픽셀 개수로 고정하면 설정을 바꿀 때
 * 확대 배율까지 같이 바뀌어, 두 줄이 같은 구간을 보고 있지 않게 된다.
 */
export const edgeWindowHalfNm = (
  cdNm: number,
  pitchNm: number,
  coarseNmPerPx: number
): number | null => {
  const spaceNm = pitchNm - cdNm
  if (!isPositive(cdNm) || !isPositive(spaceNm) || !isPositive(coarseNmPerPx)) return null
  return Math.min((EDGE_WINDOW_PX / 2) * coarseNmPerPx, cdNm / 2, spaceNm / 2)
}

export interface EdgeStrip {
  pixels: number
  nmPerPx: number
  /** 고정 물리 경계폭에 걸치는 픽셀 수 — 설정에 따라 실제로 변하는 지표. */
  pxOnEdge: number
  /** 창 안 각 픽셀의 밝기 0..1. 전부 정확히 nmPerPx 폭이다. */
  samples: number[]
}

/**
 * 같은 물리 창을 한 픽셀 설정으로 샘플링한 결과.
 * 칸을 창에 맞춰 늘이지 않는다 — 칸 폭은 언제나 정확히 nmPerPx이고,
 * 창 끝에서 딱 떨어지지 않으면 그대로 잘린다(실제 격자도 그렇다).
 */
export const edgeStrip = (
  pixels: number,
  nmPerPx: number,
  halfWindowNm: number
): EdgeStrip | null => {
  if (!isPositive(pixels) || !isPositive(nmPerPx) || !isPositive(halfWindowNm)) return null
  const count = Math.max(1, Math.round((2 * halfWindowNm) / nmPerPx))
  const samples: number[] = []
  for (let i = 0; i < count; i++) {
    const value = samplePixelNm(-halfWindowNm + (i + 0.5) * nmPerPx, nmPerPx)
    if (value === null) return null
    samples.push(value)
  }
  return { pixels, nmPerPx, pxOnEdge: SEM_EDGE_WIDTH_NM / nmPerPx, samples }
}

/**
 * 비교할 픽셀 설정 쌍 [거친 쪽, 고운 쪽].
 * 이 화면이 답하는 질문이 "지금 설정으로 되나, 한 단계 올려야 하나"이므로
 * 추천값과 그 바로 위 단계를 세운다. 이미 최상단이면 한 단계 아래와 비교한다.
 */
export const edgeComparePair = (pixels: number): [number, number] => {
  const i = PIXEL_SETTINGS.indexOf(pixels as PixelSetting)
  if (i < 0) return [pixels, pixels * 2]
  if (i === PIXEL_SETTINGS.length - 1) return [PIXEL_SETTINGS[i - 1]!, PIXEL_SETTINGS[i]!]
  return [PIXEL_SETTINGS[i]!, PIXEL_SETTINGS[i + 1]!]
}

export interface PixelGuidance {
  tone: 'ok' | 'warn' | 'error'
  headline: string
  detail: string
}

/**
 * 실사용은 512·1024 둘뿐이고 그 사이가 스캔 시간 4배 차이다. 이 화면이 실제로
 * 답하는 질문은 "512로 되나, 1024로 올려야 하나"이므로 결론과 근거를 함께 낸다.
 */
export const pixelGuidance = (rec: Recommendation, minPxPerCd: number): PixelGuidance => {
  if (rec.reason === 'no-mag') {
    return {
      tone: 'error',
      headline: '성립하는 배율이 없습니다',
      detail: `최저 배율에서도 필요 FOV ${Math.round(rec.requiredFovNm).toLocaleString()} nm를 담을 수 없습니다. 패턴 수나 여유 마진을 줄이세요.`
    }
  }
  if (rec.reason === 'no-pixels') {
    return {
      tone: 'error',
      headline: '픽셀이 부족합니다',
      detail: `${(rec.mag ?? 0).toLocaleString()}×에서는 4096 px로도 기준 ${minPxPerCd} px/CD에 미달합니다. 패턴 수를 줄이거나 기준을 재검토하세요.`
    }
  }
  const ratio = rec.pxPerCd ?? 0
  if (rec.pixels === 512) {
    return {
      tone: 'ok',
      headline: '512로 충분합니다',
      detail: `${ratio.toFixed(1)} px/CD로, 기준 ${minPxPerCd}의 ${(ratio / minPxPerCd).toFixed(1)}배입니다. 1024로 올리면 스캔 시간만 4배가 됩니다.`
    }
  }
  return {
    tone: 'warn',
    headline: `${rec.pixels} px가 필요합니다`,
    detail: `512로는 기준 ${minPxPerCd} px/CD에 미달합니다. 스캔 시간 ×${rec.scanFactor ?? '—'}를 감수해야 합니다.`
  }
}
