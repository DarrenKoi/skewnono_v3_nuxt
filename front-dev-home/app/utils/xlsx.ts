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
import { downloadBlob } from './csvDownload.ts'

export const XLSX_MIME
  = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

/** 시트 한 장. 첫 행이 헤더라는 것은 빌더 쪽 약속입니다. */
export interface WorkbookSheet {
  name: string
  rows: (string | number)[][]
}

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
 * 시트 이름은 31자로 자릅니다 — 엑셀 상한이고, 넘기면 exceljs 가 던집니다.
 * 이미지 삽입이나 열 너비처럼 시트별 후처리가 필요한 호출자는 이걸 쓰지 말고
 * `createWorkbook()` + 자기 루프 + `writeWorkbook()` 을 씁니다.
 */
export async function downloadWorkbook(
  filename: string,
  sheets: WorkbookSheet[]
): Promise<void> {
  const book = await createWorkbook()
  for (const sheet of sheets) {
    const ws = book.addWorksheet(sheet.name.slice(0, 31))
    for (const row of sheet.rows) ws.addRow(row)
  }
  await writeWorkbook(book, filename)
}
