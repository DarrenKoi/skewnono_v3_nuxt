/**
 * 스프레드시트가 **수식으로 읽어 버리는** 첫 글자들.
 *
 * CSV·TSV 에는 칸의 타입이 없어서 Excel·Sheets·LibreOffice 는 첫 글자로
 * 짐작합니다. `=`·`+`·`-`·`@` 로 시작하면 수식이고, 탭과 캐리지 리턴도 같은
 * 자리에서 수식 시작으로 해석됩니다. 그래서 사무실 식별자 하나가
 * `=HYPERLINK(...)` 이면 파일을 연 사람의 Excel 이 그것을 실행합니다.
 *
 * `.xlsx` 는 이 방어가 **필요 없습니다** — 거기서는 수식인지가 XML 에 명시되고
 * (`<f>` 요소), exceljs 는 문자열을 넘기면 언제나 공유 문자열(`t="s"`)로 씁니다.
 * 확인한 사실입니다: `=1+1` 을 addRow 로 넣고 다시 읽으면 type 은 String,
 * formula 는 null 이며 sheet XML 에 `<f>` 가 하나도 없습니다. 짐작으로 읽는
 * 형식만 이 방어가 필요합니다.
 */
const FORMULA_LEAD = /^[=+\-@\t\r]/

/**
 * 평범한 숫자 리터럴. `-1.5` 같은 값까지 감싸 버리면 Excel 에서 **텍스트**가
 * 되어 정렬도 계산도 안 됩니다 — 측정값에 음수가 흔한 저장소라 이 구제는
 * 장식이 아닙니다. 위험한 것은 `-1+1` 처럼 숫자로 끝나지 않는 쪽입니다.
 */
const PLAIN_NUMBER = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/

/**
 * 수식으로 읽힐 값 앞에 작은따옴표를 답니다 — Excel 이 "이건 텍스트" 로 읽는
 * 표시이고, 화면에는 보이지 않습니다.
 *
 * 글자 하나짜리(`-`, `+`, `=`)는 그대로 둡니다. 그것만으로는 수식이 될 수 없고,
 * `-` 는 이 저장소의 표에서 "값 없음" 자리에 흔히 쓰입니다.
 */
export const guardFormulaCell = (value: string): string =>
  value.length > 1 && FORMULA_LEAD.test(value) && !PLAIN_NUMBER.test(value)
    ? `'${value}`
    : value

export const escapeCsvValue = (value: unknown): string => {
  const normalized = guardFormulaCell(String(value ?? '')).replace(/"/g, '""')
  return `"${normalized}"`
}

// Compose CSV text (no BOM): header + rows, every value escaped, CRLF-joined.
// Pure — safe to import and call under `node --test`.
export const buildCsvContent = (headers: string[], rows: unknown[][]): string => {
  const headerRow = headers.map(escapeCsvValue).join(',')
  const bodyRows = rows.map(row => row.map(escapeCsvValue).join(','))
  return [headerRow, ...bodyRows].join('\r\n')
}

// Hand a Blob to the browser as a download. The object-URL dance is fiddly and
// easy to get subtly wrong (a missing revoke leaks the blob for the life of the
// document), so it lives here once rather than in each exporter. Client-only.
export const downloadBlob = (filename: string, blob: Blob): void => {
  if (!import.meta.client) return

  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

// Download an arbitrary CSV string. Excel reads UTF-8 only when a BOM (U+FEFF)
// is present, so this is the single place the BOM is added. Client-only.
export const downloadCsvRaw = (filename: string, content: string): void => {
  if (!import.meta.client || content.length === 0) return

  downloadBlob(filename, new Blob(['﻿' + content], { type: 'text/csv;charset=utf-8;' }))
}

export const downloadCsv = (
  filename: string,
  headers: string[],
  rows: unknown[][]
): void => {
  if (rows.length === 0) return
  downloadCsvRaw(filename, buildCsvContent(headers, rows))
}

// Copy plain text with the same fallback used by table exports. Clipboard API
// access can be unavailable outside HTTPS/localhost, so keep the legacy path
// for office deployments that still run over an internal HTTP address.
//
// `container` places the fallback's hidden textarea somewhere other than
// <body>. Callers inside a modal must pass an element within the dialog:
// the dialog traps focus, so a textarea parked on <body> gets focus yanked
// back by the focus guard before execCommand('copy') reads the selection.
export const copyTextToClipboard = async (
  text: string,
  container?: HTMLElement
): Promise<boolean> => {
  if (!import.meta.client) return false

  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // Fall through to the execCommand fallback (e.g. http:// production).
    }
  }

  const host = container ?? document.body
  try {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.top = '-9999px'
    textarea.style.opacity = '0'
    host.appendChild(textarea)
    textarea.focus()
    textarea.select()
    const ok = document.execCommand('copy')
    host.removeChild(textarea)
    return ok
  } catch {
    return false
  }
}

// Copy a table to the clipboard as TSV (tab-separated). Excel, Google
// Sheets, and other spreadsheets split pasted text on tabs, so TSV pastes
// straight into cells with no import step. Tabs/newlines inside a value are
// flattened to spaces so a stray value can't break the row/column grid.
// Returns true on success so callers can show a confirmation toast.
export const copyTableToClipboard = async (
  headers: string[],
  rows: unknown[][]
): Promise<boolean> => {
  if (!import.meta.client || rows.length === 0) return false

  // 붙여넣는 곳이 대개 Excel 이라 CSV 와 같은 방어가 필요합니다. 평탄화를
  // 먼저 하는 것은, 탭·개행이 공백이 된 **뒤의** 첫 글자가 Excel 이 보는
  // 첫 글자이기 때문입니다.
  const toCell = (value: unknown): string =>
    guardFormulaCell(String(value ?? '').replace(/[\t\r\n]+/g, ' '))
  const tsv = [headers, ...rows]
    .map(row => row.map(toCell).join('\t'))
    .join('\r\n')

  return copyTextToClipboard(tsv)
}

/**
 * 파일 이름 한 토막을 파일 시스템이 받아들이는 형태로 씻습니다.
 *
 * lot 코드·recipe 이름·파라미터 이름은 전부 office 값이라 슬래시를 비롯해
 * 파일 이름에 못 쓰는 문자가 섞여 옵니다. 내보내기 세 곳(lotParamExport ·
 * complianceExport · recipeParamExport)이 같은 정규식을 각자 들고 있었고,
 * 셋 다 주석으로 "…와 같은 이유" 라며 서로를 가리키고 있었습니다 — 코드가
 * 아니라 산문으로 추적하던 중복이라 여기로 모읍니다.
 *
 * 빈 값이 `unknown` 이 되는 것은 이름 없는 파일(`_params.csv`)이 무엇을 담고
 * 있는지 스스로 말하지 못하기 때문입니다.
 */
export const safeFileNamePart = (value: string): string =>
  (value || 'unknown').replace(/[^\w.-]+/g, '_')
