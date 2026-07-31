# Recipe Open 이미지 + 설정 영역 분리 설계

- **Date:** 2026-07-31
- **Status:** approved
- **Area:** `recipe-search/open`의 `이미지 + 설정` 탭

## 목적

현재 `ParamSettings.vue`는 이미지 세 개를 상단에 한 줄로 표시하고,
AF/PR 전체를 왼쪽에, 모든 이미지의 빔 조건을 오른쪽에 표시합니다. 이
배치는 설정의 실제 용도와 좌우 영역이 일치하지 않습니다.

`이미지 + 설정` 탭을 다음 두 영역으로 재구성합니다.

- 왼쪽은 Addressing 관련 이미지와 설정만 표시합니다.
- 오른쪽은 Measurement 관련 이미지와 설정만 표시합니다.

백엔드 응답과 API contract는 변경하지 않습니다.

## 화면 구성

데스크톱에서는 같은 너비의 두 열을 사용합니다.

| 왼쪽: Addressing | 오른쪽: Measurement |
| --- | --- |
| Addressing 이미지 썸네일 | Measurement 이미지 썸네일 |
| `addressing_*` AF/PR 설정 | `measurement_*` AF/PR 설정 |
| Addressing 이미지의 빔 조건 | Measurement 이미지의 빔 조건 |

각 열은 제목, 이미지, AF/PR, 빔 조건 순서로 표시합니다. 같은 이미지의
썸네일과 빔 조건은 동일한 열에 남습니다. 모바일과 좁은 화면에서는
Addressing 영역 다음에 Measurement 영역을 세로로 쌓습니다.

이미지가 없는 영역도 열 자체는 유지하여 좌우 의미가 선택한 파라미터에
따라 바뀌지 않게 합니다. 기존 로딩, 오류, 파일 없음 상태는 그대로
사용합니다.

## 데이터 분류

이미지는 기존 `ParamImage`와 `IMAGE_SLOTS`의 role을 사용합니다.

- `role === "address"`는 왼쪽에 배치합니다.
- `role === "measure"`는 오른쪽에 배치합니다.

AF/PR은 Sequence 탭으로 이동한 `sequence_*` 행을 먼저 제외한 뒤,
남은 행의 `section` prefix로 분류합니다.

- `addressing_*`는 왼쪽에 배치합니다.
- `measurement_*`는 오른쪽에 배치합니다.
- 두 prefix에 속하지 않는 행은 누락하지 않고 두 열 아래의
  `기타 AF / PR` 영역에 표시합니다.

각 결과 block은 원본 `source`와 행 순서를 유지합니다. 원본 block이
`null`이면 각 분류 결과도 `null`이며, 파일은 있으나 해당 분류 행이
없으면 빈 block을 유지합니다. 따라서 기존 `파일 없음`과
`읽을 수 있는 설정이 없습니다`의 의미 차이를 보존합니다.

## 구현 경계

`utils/recipeView.ts`에 순수 분류 함수를 추가합니다. 이 함수는 하나의
`SettingBlock`을 Addressing, Measurement, 기타 세 block으로 분리합니다.
`ParamSettings.vue`는 이미지 role 필터와 이 분류 결과만 사용하여 두 열을
렌더링합니다.

`SettingTable.vue`, raw-recipe endpoint, `ParamDetail` type, backend provider는
변경하지 않습니다.

## 검증

Node test로 다음 동작을 먼저 고정합니다.

1. Addressing과 Measurement 행이 각 결과로 정확히 분리됩니다.
2. 같은 section 안의 행 순서와 원본 `source`가 유지됩니다.
3. 알 수 없는 section과 section 없는 행이 기타 결과에 남습니다.
4. 입력이 `null`일 때 세 결과 모두 `null`입니다.
5. 파일은 있으나 한 domain의 행이 없을 때 해당 결과는 빈 block입니다.

구현 후 frontend unit test, typecheck, scoped ESLint를 실행합니다. 실행 중인
화면을 사용할 수 있으면 `recipe-search/open`에서 데스크톱 두 열과 좁은
화면의 Addressing-first stacking도 확인합니다.

## 범위 밖

- AF/PR 또는 빔 조건의 field 이름 변경
- 백엔드 응답 shape 변경
- AMP, Sequence, 측정 위치 탭 변경
- 이미지 lightbox 또는 이미지 fetch 방식 변경
