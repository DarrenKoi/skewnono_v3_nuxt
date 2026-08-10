# 01 — 공용 xlsx 다운로더 추출

Status: open
Plan: [`../plan.md`](../plan.md)

`await import('exceljs')` 부트스트랩이 `recipeCompare.ts`와
`recipeParamExport.ts`에 복제돼 있습니다. 세 번째 사용처(장비별 내보내기)가
생기므로 한 곳으로 모읍니다.

**Files:**

- Create: `front-dev-home/app/utils/xlsx.ts`
- Modify: `front-dev-home/app/utils/recipeCompare.ts` (284-291, 372-408)
- Modify: `front-dev-home/app/utils/recipeParamExport.ts` (18, 225, 238-245, 288-290)

**Interfaces:**

- Produces:
  - `export interface WorkbookSheet { name: string, rows: (string | number)[][] }`
  - `export async function createWorkbook(): Promise<Workbook>`
  - `export async function writeWorkbook(book: Workbook, filename: string): Promise<void>`
  - `export async function downloadWorkbook(filename: string, sheets: WorkbookSheet[]): Promise<void>`
  - `export const XLSX_MIME: string`
- Consumes: `downloadBlob` from `./csvDownload.ts`

**단위 테스트가 없는 티켓입니다.** `node --test`에는 `document`도
`URL.createObjectURL`도 없어서 이 파일은 실행할 수 없습니다. 그래서 이 파일에
행을 만드는 로직을 두지 않는 것이 규약이고(그쪽은 02·03의 순수 빌더로 나갑니다),
검증은 기존 테스트 무회귀 + 타입체크 + 실제 브라우저 내보내기 1회입니다.

---

- [ ] **Step 1: 작업 트리 분리**

```bash
cd /Users/daeyoung/Codes/skewnono_v3_nuxt
git worktree add ../skewnono-equipment-tab -b work/equipment-tab
cd ../skewnono-equipment-tab/front-dev-home
```

이후 모든 티켓은 이 워크트리 안에서 작업합니다.

- [ ] **Step 2: 기준선 확인 — 지금 테스트가 통과하는지 먼저 본다**

Run: `npm test 2>&1 | tail -5`
Expected: 실패 0건. 여기서 이미 깨져 있으면 그것은 이 작업의 책임이 아니므로
멈추고 보고합니다.

- [ ] **Step 3: `utils/xlsx.ts` 작성**

Create `front-dev-home/app/utils/xlsx.ts`:

```ts
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
```

- [ ] **Step 4: auto-import 이름 충돌 확인**

Run:

```bash
cd /Users/daeyoung/Codes/skewnono-equipment-tab/front-dev-home/app
grep -rn "WorkbookSheet\|createWorkbook\|writeWorkbook\|downloadWorkbook\|XLSX_MIME" \
  --include="*.ts" --include="*.vue" . | grep -v "utils/xlsx.ts"
```

Expected: `utils/recipeCompare.ts`의 `WorkbookSheet` 3줄과
`utils/recipeParamExport.ts`의 `XLSX_MIME` 2줄만 나옵니다. 둘 다 Step 5·6에서
제거됩니다. 그 밖의 히트가 있으면 이름을 바꿔야 합니다 — `utils/`의 export는
전역 auto-import 이름이라 중복이 생기면 한쪽이 조용히 버려집니다.

- [ ] **Step 5: `recipeCompare.ts` 재배선**

`utils/recipeCompare.ts` 상단 import 블록에 한 줄 추가합니다(기존 import는
그대로 둡니다):

```ts
import { createWorkbook, writeWorkbook, type WorkbookSheet } from './xlsx.ts'
```

284-287의 선언을 **삭제**합니다:

```ts
export interface WorkbookSheet {
  name: string
  rows: (string | number)[][]
}
```

재수출하지 않습니다 — 재수출은 같은 타입에 auto-import 이름을 둘 만듭니다.

`downloadCompareWorkbook`의 몸통을 바꿉니다. 첫 세 줄

```ts
  const mod = await import('exceljs')
  const ExcelJS = (mod as unknown as { default?: typeof mod }).default ?? mod
  const book = new ExcelJS.Workbook()
```

를 한 줄로:

```ts
  const book = await createWorkbook()
```

그리고 마지막 blob/anchor 블록

```ts
  const buffer = await book.xlsx.writeBuffer()
  const blob = new Blob([buffer], {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
  })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
```

를 한 줄로:

```ts
  await writeWorkbook(book, filename)
```

가운데 시트 루프(`for (const sheet of workbook.sheets)`)와 이미지 splice 블록,
그 위의 주석은 **그대로 둡니다** — 이 함수가 `downloadWorkbook`을 쓰지 못하는
이유가 바로 그 splice입니다.

- [ ] **Step 6: `recipeParamExport.ts` 재배선**

18줄의 `import { downloadBlob } from './csvDownload.ts'`를 삭제하고 대신:

```ts
import { createWorkbook, writeWorkbook } from './xlsx.ts'
```

225줄의 `const XLSX_MIME = '...'` 선언을 삭제합니다.

`downloadParamWorkbook`의 부트스트랩 세 줄을 `const book = await createWorkbook()`
로, 마지막 두 줄

```ts
  const buffer = await book.xlsx.writeBuffer()
  downloadBlob(filename, new Blob([buffer], { type: XLSX_MIME }))
```

를 `await writeWorkbook(book, filename)` 로 바꿉니다. 열 너비 루프와 이미지
fetch 블록은 그대로 둡니다.

- [ ] **Step 7: 테스트·타입체크·린트**

Run:

```bash
cd /Users/daeyoung/Codes/skewnono-equipment-tab/front-dev-home
npm test 2>&1 | tail -5
npm run typecheck
npm run lint
```

Expected: 세 명령 모두 통과. 특히 `recipeCompare.test.ts`의
`buildCompareWorkbook` 테스트 2개가 계속 통과해야 합니다 — 이 티켓은
빌더를 건드리지 않았으므로 그래야 정상입니다.

- [ ] **Step 8: 커밋**

```bash
cd /Users/daeyoung/Codes/skewnono-equipment-tab
git add front-dev-home/app/utils/xlsx.ts \
        front-dev-home/app/utils/recipeCompare.ts \
        front-dev-home/app/utils/recipeParamExport.ts
git commit -m "refactor(front): exceljs 부트스트랩을 utils/xlsx.ts로 모은다

recipeCompare 와 recipeParamExport 가 각자 들고 있던 동적 import·Blob·
링크 클릭 배관을 한 곳으로 옮겼습니다. 장비별 내보내기가 세 번째
사용처가 되므로 지금이 추출 시점입니다. WorkbookSheet 타입도 함께
옮겨 auto-import 이름이 하나만 남게 했습니다.

두 기존 호출자의 동작은 바뀌지 않습니다 — 이미지 삽입과 열 너비처럼
시트별 후처리가 있는 쪽은 자기 루프를 그대로 유지합니다."
```
