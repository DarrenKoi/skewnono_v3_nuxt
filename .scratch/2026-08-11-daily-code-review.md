# 2026-08-11 일일 코드 리뷰 — 장비별 탭 단순화 · device-statistics · 복사 버튼 폴백 · probe 스크립트

작성일: 2026-08-11 · 리뷰 범위: `bf1e060a..HEAD` (커밋 34건, 파일 83개, 삽입 약 5900줄)

> 리뷰 방식: 네 개 클러스터로 병렬 분석 후 핵심 주장은 원문 코드로 재확인했다.
> 확정 버그와 정황(suspect)을 구분했고, 중대도는 High/Medium/Low 로 표기한다.

> **2026-09-01 후기**: §1 의 수식 주입 항목은 **전제가 틀렸다**. 원문을 지우지
> 않고 그 자리에 정정을 붙여 둔다 — 이 파일을 읽고 `xlsx.ts` 를 고치러 가는
> 일이 실제로 한 번 있었기 때문이다. 같은 절의 다운로드 오류 처리 항목은
> 부분적으로 해결되었다.

## 0. 워킹 트리 정리 사항 (가장 시급)

- **`scripts/test_office_endpoints.py` 가 아직 HEAD 에 남아 있다.** "rename" 커밋
  `f5000393` 은 `probe_office_endpoints.py` 를 새로 만들었지만 옛 파일을 지우지
  않았다. 삭제는 지금 staged 상태로 커밋되지 않은 채 방치되어 있다.
- 두 파일은 이미 갈라져 있다(drift): HEAD 의 옛 복사본은 토큰 상수가 오타
  (`\ud0a0` "킬가능" ≠ `\ud070` "큰가능"), `recipe-image` 카탈로그 항목 누락,
  `--allow-implicit-identity` 부재. `git ls-files` 에는 보이지 않아(index 전용
  삭제) 전체 트리 restore/stash 시 낡은 복사본이 되살아난다.
- 조치: staged 삭제를 **이 경로 하나만** 명시해서 커밋한다. 그 전까지
  `python -m scripts.test_office_endpoints` 는 깨진 코드를 실행한다.

## 1. Excel 내보내기 / 장비별 탭 refactor

- **[Medium] fleet refetch 창에서 기간/장비 세트가 섞인 내보내기** —
  `RecipeTatEquipmentView.vue:102-104,145-150` · `FailIssueEquipmentView.vue:107-109,155-161`.
  fab/기간 변경 시 Nuxt 가 새 `useAsyncData` 키의 초기값을 **이전 키의 페이로드로
  채우므로**(`asyncData.js` 의 `initialValue` 로직), fleet 표는 로딩 표시 없이 옛
  기간 행을 계속 렌더링한다(로딩은 `!equipmentRows.length` 일 때만). 이 창에 옛
  행의 장비를 체크하면 `장비` 시트는 옛 기간, `레시피`/`일별추이` 는 새 기간이
  되거나, refetch 가 해당 id 를 떨어뜨리면 `exportEquipmentRows`
  (`equipmentExport.ts:47-50`) 가 `장비` 시트에서만 열을 조용히 생략한다 — 검색
  경로에 대해 막은 "두 시트가 서로 다른 장비"(`60a36fa9`)와 같은 결함이 기간
  변경 경로에 그대로 열려 있다. fleet 스냅샷과 compare 스냅샷을 묶는 불변식이 없다.
- **[Low · 정정 2026-09-01] 셀에 수식 주입 보호 없음 — 겨눈 곳이 반대였다.**
  원문은 이렇게 적었다: *"`equipmentExport.ts:72-80,101-109,166-176,200-209`.
  `eqp_id`·`fab_name`·`eqp_model_cd`·레시피 `full_name` 을 raw 로 기록한다. 옛
  CSV 경로(`csvDownload.ts:1-4`)는 모든 값을 escape 했다. 사무실 식별자가
  `=`/`+`/`-`/`@` 로 시작하면 Excel 이 수식으로 평가한다."* — 위험한 쪽을
  xlsx 로, 안전한 쪽을 CSV 로 두었는데 **둘 다 뒤집힌다.**
  - `.xlsx` 는 애초에 취약하지 않다. 칸마다 타입이 명시된 형식이라 수식은
    `<f>` 요소로만 수식이고, exceljs 는 문자열을 받으면 언제나 공유 문자열로
    쓴다. `=1+1` 을 `addRow` 로 넣고 다시 읽으면 type=String · formula=null
    이며 sheet XML 에 `<f>` 가 0 개다(2026-09-01 확인). 거기에 방어를 넣으면
    Excel 이 그 따옴표를 값으로 보여 줄 뿐이다.
  - 노출된 쪽은 **CSV·클립보드 TSV** 였다. 따옴표로 감싸는 것은 수식 주입을
    막지 못한다 — Excel 은 `"=1+1"` 도 수식으로 읽는다. 칸의 타입이 없어 첫
    글자로 짐작하기 때문이고, 내보내기 15곳·붙여넣기 15곳이 그 경로를 지난다.
  - 조치(`5128f581`): `csvDownload.guardFormulaCell` 을 `escapeCsvValue` 와
    `copyTableToClipboard` 두 길목에 걸었다. 숫자는 감싸지 않는다 — `-1.5` 를
    감싸면 Excel 에서 텍스트가 되어 정렬도 계산도 안 되는데 이 저장소엔 음수
    측정값이 흔하다. 적대적 값을 API 응답에 주입해 실제 화면에서 받아 본 CSV 가
    `'=HYPERLINK(...)` 로 적히는 것과, 평소 내보내기가 방어 전과 바이트 단위로
    같은 것을 함께 확인했다. `xlsx.ts` 에는 왜 방어가 없는지 주석을 남겼다.
- **[Low · 부분 해결 2026-09-01] 다운로드 경로에 오류 처리 없음** — 두
  EquipmentView 의 `await downloadWorkbook(...)` 에 try/catch 가 없고,
  `xlsx.ts:32-38` 는 `writeBuffer()` 의 rejection 을 그대로 unhandled rejection
  으로 흘린다. 워크북 생성 실패가 사용자에게 아무 피드백 없이 사라진다.
  → 2026-09-01 에 생긴 세 번째 호출자(`ComplianceTable.vue` 의 디바이스별 Excel
  칩)에는 catch + toast 를 달았다(`5d95288c`). 스피너를 쓰는 자리라 조용한 실패가
  "버튼이 죽었다" 로 읽히는 것이 더 나빴다. **원문이 지목한 두 EquipmentView 는
  아직 그대로다.**
- **[Suspect] 시트 간 공백 판정 근거 불일치** — `장비` 시트는 `exec_count === 0`,
  `레시피` 시트는 `meas_counts === 0` 로 공백 처리(`equipmentExport.ts:78,106`).
  mock 은 `exec_count ≡ Σ meas_counts` 를 보장하므로 일치하지만, 사무실 어댑터가
  갈라지면 같은 파일 안에서 한 시트는 비우고 다른 시트는 0 을 채운다.
- **[Suspect] `일별추이` 가 모든 계열의 날짜 집합 일치를 전제** —
  `equipmentExport.ts:115,214` 는 `trends[0]` 의 날짜를 축으로 쓴다. 계열별 날짜
  집합이 갈라지는 어댑터라면 없는 날이 공백이 아니라 0 으로 찍힌다.

## 2. device-statistics

- **[Medium] 정렬 비교기가 표면마다 다르다** — 차트는 `localeCompare`(numeric
  미지정, `lotSort.ts:71`), 표는 TanStack 의 alphanumeric 비교기
  (`LotTable.vue:534,578-584`). mock 로트 코드에는 숫자 접두어(`100`, `1001`,
  `60B2` — `statistics.py:440`)가 실제로 있다: 차트는 `100` 을 `60B2` 앞에,
  표는 `60B2` 를 먼저 둔다. `ff633954` 는 정렬 **축**만 통일했지 비교기는
  통일하지 못했다.
- **[Medium] 동률 처리도 표면마다 다르다** — `lotSort.ts:75` 는 이름으로
  tie-break, TanStack 은 stable sort 로 API 순서를 유지. 좁은 버킷에서는
  `para_total` 동률이 흔하므로 같은 칩을 눌러도 표와 차트의 순서가 어긋난다.
- **[Medium] 토큰 포함 판정이 단어 조각까지 오매치** — `lotHealth.ts:89` 와
  `recipe_population.py:130` 의 `/(_[A-Z]*CDU|_FULL|_HALF|_MTX)/i` 에 단어 경계가
  없다. `_FULLY`, `_HALF_PITCH`, `_MTX001` 같은 이름이 모두 매치되어 정상
  레시피가 판정 분모·이상치 중앙값 기준선에서 빠진다. 오매치가 툴팁
  `exempt_recipes` 로 보인다는 건 사실이나, 정상 레시피가 판정에서 빠지는 결과는
  데이터 품질 회귀다. 테스트는 underscore 없는 쪽(false)만 고정하고
  underscore 인접 오매치를 고정하지 않았다.
- **[Low] `stage` 열 정렬이 표와 카드/CSV 에서 뒤집힌다** — 표는
  대소문자 무시 alphanumeric(`LotTable.vue:498`), 내보내기 미러는 대소문자 구분
  `localeCompare`(`556-585`). `Pool` vs `PV` 순서가 다르다.
- **[Low] 활성 칩을 다시 눌러도 열 헤더 정렬이 리셋되지 않는다** —
  `LotTable.vue:536` 은 `props.sort` **변경**에만 반응한다. 주석의 "칩이
  이깁니다" 는 다른 칩을 눌렀을 때만 참이다.
- **[Suspect] 중복 스텝 정체성이 mock 캐시에서 조용히 버려진다** —
  `statistics.py:266-269` 의 dict comprehension 은 중복 `(oper_seq, samp_seq)` 를
  조용히 한 행으로 접는다. 새 계약 테스트가 provider 별로 막고 있어 잠재적일 뿐,
  위반을 숨기는 구조다.

## 3. 산발적 프론트 수정

- **[Medium] compare 패널의 필터 앵커 불일치** —
  `FailIssueEquipmentCompare.vue:245-248` · `RecipeTatEquipmentCompare.vue:209-212`.
  "오늘 데이터" 필터는 `summary?.anchor_date` 를 기준으로 하지만 x 축 날짜는
  계열별 필터링 후 `visibleTrends[0].points` 에서 나온다. 계열이 앵커 날짜까지
  0-fill 되어 있지 않으면 일부 계열만 N−1 개가 되어 축(series[0])이 데이터와
  어긋난다. `anchor_date` 가 undefined(요약 미도착·커스텀 기간)면 토글은 조용히
  무시된다.
- **[Low] 클립보드 폴백의 포커스 상실 + textarea 누수** — `csvDownload.ts:76-83`.
  `textarea.focus()` 를 되돌리지 않아(http 프로덕션에서 복사 클릭마다) 포커스가
  `<body>` 로 떨어져 키보드 사용자의 탭 순서가 깨진다. 또 `execCommand` 가
  throw 하면 catch 가 false 만 반환하고 textarea 를 제거하지 않아 숨은 textarea
  가 DOM 에 남는다.
- **[Low] BoolPill 의 `undefined` 는 여전히 오렌더** — `BoolPill.vue:19`.
  `null` 은 `—` 로 처리되지만 `undefined` 는 `False` 로 떨어지고,
  `f9a1cac9` 가 고치려던 "type check failed" 경고를 그대로 낸다(required prop,
  기본값 없음). 계약이 null 이 아닌 키 누락으로 온다면 경고가 부활한다.
- **[Suspect] 앵커 날짜 한 점만 가진 계열**이 필터로 비면 series[0] 이 비어 축이
  빈 채 형제 계열 데이터만 남는다.

## 4. probe_office_endpoints.py

- **[Medium] 404 를 통과로 친다** — `probe_office_endpoints.py:415-423`. 제거된
  라우트도 Flask 기본 404 를 반환하므로, 스크립트의 본래 목적("swap 이
  엔드포인트를 깨뜨리는지")에서 위양성(false positive)이 된다. 주석의 "예제
  파라미터가 없을 수 있음"은 "라우트가 사라짐"과 구분할 수 없다.
- **[Medium] docstring 의 read-only 주장이 거짓** — 48-50 줄은 "모든 호출이
  GET, 아무 데도 쓰지 않는다"고 하지만 sweep 은 `param-detail`·`msr-files` 에
  실 토큰으로 POST 두 건을 보낸다(136, 157 줄). 부작용 여부는 미검증인데
  read-only 로 광고된 스크립트다.
- **[Medium] 테스트가 위험 경로를 안 건드린다** — `tests/test_probe_office_endpoints.py`.
  fake `Requests` 가 `get` 만 구현해 `_do_catalog_sweep`/`_fetch_with_retry`/
  `_build_url`/`_render_path` 가 구조적으로 테스트 불가. 429 재시도, 5xx/3xx
  분류, 전송 실패, 엉터리/정상 토큰 leg, strict(비암시) probe 는 전부 무커버.
- **[Low] `--token` 이 셸 히스토리/프로세스 목록에 평문 노출** — 도움말이
  env var 대신 이 옵션을 권장하고 있다(484-488 줄).
- **[Low] auth probe leg 에 sweep 의 429 재시도가 없다** — 301-310 줄.
  문서화된 "동시 사용자 존재" 상황에서 429 하나가 스윕 전체를 중단시킨다.

## 5. 확인된 깨끗한 영역

- 스토리지 라우트 가드(`7d8cea8e`): `hasStorageView === SEM_TOOL_TYPES` 가 실제
  라우트 존재와 일치, dangling 링크 없음.
- 클립보드 http 폴백 메커니즘 자체(`csvDownload.ts:53-84`): https 경로 보존,
  execCommand 는 클릭 태스크 안에서 동기 실행(사용자 활성 보존).
- `useRecipeSearchApi` 의 null Boolean 변경: 타입 어노테이션뿐, 런타임/조회
  결과 변화 없음.
- 워크북 시트 헤더/값 열 정렬(모든 시트), 시트 간 필드 교차 없음, 남은
  `percentiles`/`occupancy`/`tat_index` 참조 없음.
- `70495aa0` 비교 페이로드 비움: 키 변경 시 Nuxt 가 자식 데이터를 새 키에
  재바인딩하므로 옛 선택이 재발신될 수 없음.

## 요약

| 중대도 | 건수 |
| --- | --- |
| High | 0 |
| Medium | 8 |
| Low | 7 |
| Suspect | 4 |

확정 크래시는 없으나, 사무실 반영 전에 고칠 Medium 셋 — fleet refetch 내보내기
혼합(§1-1), lot 정렬 비교기 분열(§2-1·2), probe 의 404 위양성(§4-1) — 과
커밋되지 않은 staged 삭제(§0)가 가장 실질적이다. 후자는 유일하게 작업을 조용히
잃을 수 있는 항목이다.

### 2026-09-01 갱신

위 표는 리뷰 당일의 집계 그대로 둔다. 그 뒤에 움직인 것만 적는다.

| 항목 | 상태 |
| --- | --- |
| §1 수식 주입 | 정정 후 해결 — 취약한 곳은 xlsx 가 아니라 CSV·클립보드였다 (`5128f581`) |
| §1 다운로드 오류 처리 | 부분 해결 — 신규 호출자만 (`5d95288c`), EquipmentView 둘은 미해결 |

수식 주입 항목이 남긴 교훈은 형식마다 판단이 다르다는 것이다. 첫 글자로 타입을
짐작하는 형식(CSV·TSV)만 이 방어가 필요하고, 칸마다 타입을 적는 형식(xlsx)은
필요하지 않다. "내보내기 = 수식 주입 위험" 으로 뭉뚱그리면 안전한 곳을 고치고
취약한 곳을 놓친다 — 이 파일이 3주 동안 그렇게 안내했다.
