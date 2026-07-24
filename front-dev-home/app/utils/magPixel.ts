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
