import { downloadTable } from '~/utils/xlsx'

/**
 * 표 한 장을 `.xlsx` 로 내려받되, **실패하면 말해 줍니다.**
 *
 * CSV 시절의 `downloadCsv` 는 동기라 실패할 수가 없었습니다. `.xlsx` 는
 * exceljs 를 동적 import 하므로 청크를 못 받으면 거절합니다 — 사내 http 배포에서
 * 이건 이론이 아닙니다: 탭을 열어 둔 채 `pack.py` 로 재배포하면 그 탭이 들고 있는
 * 청크 해시가 사라져 404 가 납니다. 잡지 않으면 버튼이 조용히 아무 일도 안 하고
 * unhandled rejection 만 콘솔에 남습니다.
 *
 * 호출부마다 try/catch 를 복사하는 대신 여기 한 곳에 답니다. 워크북을 직접
 * 조립하는 쪽(recipeParamExport · complianceExport 등)은 각자 실패 메시지가
 * 달라서 자기 try/catch 를 그대로 씁니다 — 여기는 한 장짜리 경로 전용입니다.
 */
export const EXCEL_DOWNLOAD_FAILED = {
  title: 'Excel 다운로드에 실패했습니다.',
  description: '잠시 후 다시 시도하거나, 페이지를 새로고침해 주세요.',
  icon: 'i-lucide-x',
  color: 'error'
} as const

export const useTableDownload = () => {
  const toast = useToast()

  return async (filename: string, headers: string[], rows: unknown[][]) => {
    try {
      await downloadTable(filename, headers, rows)
    } catch {
      toast.add({ ...EXCEL_DOWNLOAD_FAILED })
    }
  }
}
