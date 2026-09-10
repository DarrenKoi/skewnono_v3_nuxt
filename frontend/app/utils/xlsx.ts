// 워크북 한 권을 브라우저에 파일로 떨어뜨립니다.
//
// exceljs 는 동적 import 입니다 — 수백 KB 짜리 라이브러리이고, 내보내기 버튼을
// 누르기 전에는 한 바이트도 필요하지 않습니다. 이 저장소의 내보내기 세 곳이
// 같은 부트스트랩(`default` 벗기기 + Blob + 링크 클릭)을 각자 들고 있던 것을
// 여기로 모았습니다.
//
// **이 파일에는 행을 만드는 로직을 두지 않습니다.** `node --test` 에는
// document 도 URL.createObjectURL 도 없어서 여기는 실행할 수 없는 코드이고,
// 실행할 수 없는 파일에 판단이 들어가는 순간 그 판단은 영영 검증되지
// 않습니다. 행 조립은 순수 빌더(equipmentExport.ts 등)의 몫입니다.
import { downloadBlob, safeSheetName, toSheetRows } from './tableExport.ts'

export const XLSX_MIME
  = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

// 수식 주입 방어(`tableExport.guardFormulaCell`)를 여기서는 **부르지 않습니다**.
// 2026-08-11 리뷰가 이 파일을 그 구멍으로 적어 두었지만, 확인해 보니 전제가
// 틀렸습니다: `.xlsx` 는 칸마다 타입이 명시된 형식이라 수식은 `<f>` 요소로만
// 수식이고, exceljs 는 문자열을 받으면 언제나 공유 문자열로 씁니다. `=1+1` 을
// addRow 로 넣고 다시 읽으면 type=String / formula=null 이며 sheet XML 에
// `<f>` 가 0 개입니다. 첫 글자로 짐작하는 것은 CSV·TSV 쪽이고, 방어도 거기
// 있습니다. 여기에 따옴표를 달면 Excel 이 그 따옴표를 값으로 보여 줍니다.

/** 시트 한 장. 첫 행이 헤더라는 것은 빌더 쪽 약속입니다. */
export interface WorkbookSheet {
  name: string
  rows: (string | number)[][]
  /**
   * 굵게 + 옅은 채움으로 띄울 행. 빌더가 행을 보고 정합니다(예: mother 파라미터)
   * — 어느 행인지는 판단이고, 판단은 `node --test` 가 실행할 수 있는 빌더에
   * 있어야 합니다. 여기는 그 답을 서식으로 옮길 뿐입니다. 첫 행(헤더)에는
   * 묻지 않습니다.
   */
  emphasize?: (row: (string | number)[]) => boolean
}

/** 강조 행의 채움색. 회색 계열이라 초과 행의 조건부 서식과 부딪히지 않습니다. */
const EMPHASIS_FILL = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFEDE9FE' } } as const

/** exceljs 의 빈 Workbook. CJS/ESM interop 때문에 `default` 를 벗깁니다. */
export async function createWorkbook() {
  const mod = await import('exceljs')
  const ExcelJS = (mod as unknown as { default?: typeof mod }).default ?? mod
  return new ExcelJS.Workbook()
}

type Workbook = Awaited<ReturnType<typeof createWorkbook>>

export async function writeWorkbook(
  book: Workbook,
  filename: string
): Promise<void> {
  const buffer = await book.xlsx.writeBuffer()
  downloadBlob(filename, new Blob([buffer], { type: XLSX_MIME }))
}

/**
 * 행 배열만 있는 단순한 경우의 한 줄 경로.
 *
 * 시트 이름은 `safeSheetName` 이 씻습니다(31자 상한 + 엑셀이 금지하는 글자).
 * 이미지 삽입이나 열 너비처럼 시트별 후처리가 필요한 호출자는 이걸 쓰지 말고
 * `createWorkbook()` + 자기 루프 + `writeWorkbook()` 을 씁니다.
 */
export async function downloadWorkbook(
  filename: string,
  sheets: WorkbookSheet[]
): Promise<void> {
  const book = await createWorkbook()
  for (const sheet of sheets) {
    const ws = book.addWorksheet(safeSheetName(sheet.name))
    sheet.rows.forEach((row, i) => {
      const added = ws.addRow(row)
      if (i > 0 && sheet.emphasize?.(row)) {
        added.font = { bold: true }
        added.fill = EMPHASIS_FILL
      }
    })
  }
  await writeWorkbook(book, filename)
}

/**
 * 표 한 장짜리 내보내기. `downloadCsv` 가 있던 자리를 그대로 받습니다 —
 * 같은 (파일명, 헤더, 행) 시그니처라 호출 지점은 `await` 만 붙으면 됩니다.
 * 칸 정규화는 `toSheetRows` 의 몫입니다(여기는 실행할 수 없는 파일입니다).
 */
export async function downloadTable(
  filename: string,
  headers: string[],
  rows: unknown[][]
): Promise<void> {
  if (rows.length === 0) return
  await downloadWorkbook(filename, [{ name: 'Sheet1', rows: toSheetRows(headers, rows) }])
}
