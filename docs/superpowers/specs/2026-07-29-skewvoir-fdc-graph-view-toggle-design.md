# Skewvoir FDC 그래프 보기 전환 설계

Date: 2026-07-29

## 목적

`skewvoir/analysis`의 단일 MSR `FDC 분석` 화면에서 파라미터 매트릭스와
개별 그래프를 동시에 길게 나열하지 않고, 사용자가 두 보기를 전환하도록
합니다. 개별 그래프 보기에서는 필요한 CD 및 Dynamic FDC 그래프만 선택하여
세로로 비교할 수 있어야 합니다.

이번 변경은 화면 구성과 로컬 표시 상태만 다룹니다. FDC 데이터 모델,
sequence 정렬, 상관계수 계산, URL 계약 및 backend API는 변경하지 않습니다.

## 확정된 화면 구성

워크벤치 상단에 다음 두 보기 버튼을 탭 형태로 배치합니다.

| 보기 | 내용 |
| --- | --- |
| 파라미터 매트릭스 | 기존 FDC 파라미터 매트릭스를 표시합니다. 기본 보기입니다. |
| 개별 그래프 | 사용자가 선택한 CD 및 Dynamic FDC 그래프를 세로로 표시합니다. |

보기 전환은 `SequenceWorkbench.vue`의 loading, error, 측정점 없음 상태에는
표시하지 않습니다. 현재 정상 데이터를 렌더링하는 `<template v-else>` 내부
최상단에서만 표시하므로, 데이터가 없는 상태에서 빈 탭이 노출되지 않습니다.

매트릭스 보기의 읽기 순서는 `보기 전환 → 파라미터 매트릭스 → 측정 순서`입니다.
개별 그래프 보기의 읽기 순서는
`보기 전환 → 그래프 선택 버튼 → 측정 순서 → 선택된 개별 그래프`입니다.
따라서 측정 순서는 매트릭스 보기에서 매트릭스 바로 아래에 배치되며, 개별
그래프 보기에서는 그래프를 읽기 전에 공통 cursor를 조작할 수 있습니다.

비활성 보기는 `v-if`로 DOM과 ECharts 인스턴스를 해제합니다. 숨겨진 차트를
유지하는 `v-show`는 불필요한 chart 인스턴스와 숨김 상태의 크기 계산 문제를
만들 수 있으므로 사용하지 않습니다. 이 선택으로 매트릭스 탭을 떠났다가
돌아오면 사용자가 조정한 dataZoom 범위가 전체 범위로 초기화됩니다. 탭 전환
시점의 chart 인스턴스와 zoom 상태를 보존하지 않는 것을 이번 변경의 수용된
절충으로 명시합니다.

## 개별 그래프 선택

개별 그래프 보기 상단에 다음 컨트롤을 배치합니다.

- `CD만 선택`: 활성 CD 그래프만 선택합니다.
- `전체 선택`: 활성 CD와 현재 MSR의 모든 Dynamic FDC 그래프를 선택합니다.
- CD 및 각 Dynamic FDC 파라미터 토글 버튼: 사용자가 그래프를 개별적으로
  추가하거나 제거합니다.

첫 진입 시 `전체 선택` 상태를 기본으로 합니다. focus MSR 또는 활성 CD
파라미터가 바뀌면 사용 가능한 그래프 이름이 이전과 같더라도 새 집합 전체를
다시 선택합니다. 보기 모드는 유지합니다.

FDC axis mode만 바뀌면 다음 규칙으로 선택을 조정합니다.

- 변경 전 사용 가능 그래프가 모두 선택돼 있었다면 변경 후 집합도 모두
  선택합니다.
- 사용자가 일부만 선택한 상태였다면 새 집합과 기존 선택의 교집합만
  유지합니다. 새로 등장한 그래프는 자동으로 추가하지 않습니다.
- 사라진 그래프 식별자는 선택에서 제거합니다.

따라서 axis 전환이 사용자의 부분 선택을 조용히 전체 선택으로 덮어쓰지
않습니다. 보기 모드와 그래프 선택은 page-local 상태이며 URL query나 local
storage에 저장하지 않습니다.

Dynamic FDC가 있는 상태에서 사용자가 모든 그래프를 해제하면 측정 순서
아래에 `선택된 그래프가 없습니다` 빈 상태와 선택 안내를 표시합니다.

Dynamic FDC가 없는 MSR에서는 중복되는 `CD만 선택`, `전체 선택` 및 개별 토글
toolbar를 표시하지 않고 CD 그래프를 항상 표시합니다. 기존 `FDC 없음`과
`model.fdcReason` 안내는 매트릭스 보기와 개별 그래프 보기 모두에서
유지합니다. 이 경우 전체 해제 빈 상태는 표시하지 않습니다.

선택 식별자는 화면 표시명과 분리합니다. CD와 이름이 같은 FDC 파라미터가
생겨도 충돌하지 않도록 `cd:<active-param>` 및 `fdc:<fdc-param>` 형태의 내부
식별자를 사용합니다.

## 매트릭스 drill 동작

기존 매트릭스 셀 클릭은 공유 sequence cursor 이동과 해당 파라미터 개별
그래프로의 drill을 함께 수행합니다. 탭 전환 뒤에도 이 계약을 보존합니다.

Dynamic FDC 셀을 클릭하면 다음 순서로 처리합니다.

1. 기존처럼 공유 sequence와 연결된 site를 갱신합니다.
2. 클릭한 FDC 파라미터가 해제된 상태라면 선택 집합에 추가합니다.
3. 보기를 `개별 그래프`로 전환합니다.
4. `nextTick`과 한 번의 `requestAnimationFrame` 뒤 해당 panel root에
   `tabindex="-1"`로 programmatic focus를 이동하고, 같은 panel을
   `scrollIntoView({ block: 'nearest', behavior: 'smooth' })`로 이동합니다.

CD 셀 클릭은 기존처럼 cursor만 이동하며 보기 전환을 발생시키지 않습니다.
사용자가 구성한 다른 그래프 선택은 drill 과정에서 유지하고, 클릭한
파라미터만 추가합니다. 전환으로 매트릭스가 unmount되더라도 keyboard focus가
`document.body`로 유실되지 않아야 합니다.

## 시각적 수정

### 이벤트 레인 색상

측정 실패는 기존 `--sk-bad` 빨강을 유지합니다. 이미지는 현재
`--sk-brand` terracotta 대신 light/dark mode 모두에서 빨강과 구분되는
파랑 계열을 사용합니다. 정확한 클래스는
`bg-sky-600 dark:bg-sky-400`이며 범례와 sequence별 점에 동일하게
적용합니다. 정렬은 기존 `--sk-ok` 초록을 유지합니다.

이번 색상은 이벤트 레인에만 적용합니다. 전역 semantic token을 새로 만들거나
다른 화면의 brand 색상을 변경하지 않습니다. 실제 light/dark 배경에서의
시각적 구분은 브라우저로 검증합니다.

### CD 매트릭스 셀 너비

현재 CD row의 ECharts grid는 첫 열부터 마지막 열까지 span하여 FDC 셀보다
넓습니다. CD grid의 matrix coordinate를 첫 번째 열 한 칸으로 바꾸어 각 FDC
셀과 같은 너비로 표시합니다. 나머지 열은 빈 matrix 공간으로 남기며 CD
데이터, 축, 단위, marker 및 클릭 동작은 변경하지 않습니다.

구현은 CD 전용 coordinate 삼항 분기를 제거하고 모든 셀에
`coord: [colKey(colIdx), row.label]`을 적용합니다. CD row가 정확히 한 cell을
가지며 그 `colIdx`가 0인 기존 `paramMatrix.ts` 불변식을 사용합니다. 축 제목은
CD와 FDC 모두 동일한 폭 제약을 받도록
`nameTruncate: { maxWidth: 112, ellipsis: '…' }`를 적용합니다. shared dataZoom
slider는 모든 graph grid를 함께 제어하므로 기존처럼 matrix 전체 폭을
유지하며 CD cell 폭에 맞추지 않습니다.

## 컴포넌트 변경

| 파일 | 변경 |
| --- | --- |
| `fdc/SequenceWorkbench.vue` | 보기 전환, 그래프 다중 선택, 조건부 렌더링, 측정 순서 재배치 및 matrix drill 전환을 담당합니다. |
| `fdc/SequenceEventLane.vue` | 이미지 범례와 점을 파랑 계열로 변경합니다. |
| `fdc/ParamMatrix.vue` | CD grid의 전체 열 span을 제거하고 첫 열 한 칸에 배치합니다. |
| `utils/skewvoirAnalysis/graphSelection.ts` | 그래프 식별자, 전체/CD 선택, 토글, axis 집합 조정 및 drill 선택 추가를 순수 함수로 제공합니다. |
| `utils/skewvoirAnalysis/graphSelection.test.ts` | 그래프 선택과 집합 변경 규칙을 Node test runner로 검증합니다. |

새 backend 코드, composable, store 또는 URL query는 추가하지 않습니다.
컴포넌트 밖에서 검증할 수 있도록 선택 상태 계산만 pure frontend util로
분리합니다.

## 상태 및 접근성

보기 전환은 `tablist`와 두 `tab`으로 구현합니다. 활성 tab만 `tabindex="0"`을
가지고 나머지는 `-1`인 roving tabindex를 사용합니다. `ArrowLeft`,
`ArrowRight`, `Home`, `End`로 tab focus와 보기를 전환합니다. 매트릭스 tab은
`fdc-matrix-panel`, 개별 그래프 tab은 `fdc-individual-panel`을
`aria-controls`로 가리킵니다. 두 panel 중 활성 panel만 `v-if`로 렌더링하며
각 `tabpanel`은 자신을 제어하는 tab id를 `aria-labelledby`로 참조합니다.

`CD만 선택`과 `전체 선택`은 명령 버튼입니다. CD 및 FDC 파라미터 토글
버튼만 눌림 상태를 `aria-pressed`로 노출합니다. 모든 컨트롤은 키보드로
조작할 수 있어야 하며, 색상만으로 선택 상태를 전달하지 않습니다.

선택한 그래프의 원래 색상 매핑은 유지합니다. 동일한 FDC 파라미터는 매트릭스와
개별 그래프에서 계속 같은 색상을 사용합니다.

## 검증

구현 후 다음을 확인합니다.

- frontend `npm test`
- frontend `npm run typecheck`
- 변경 파일 대상 ESLint 또는 전체 `npm run lint` 결과
- `git diff --check`
- `graphSelection.test.ts`에서 기본 전체 선택, CD만 선택, 전체 해제, 같은 이름의
  CD/FDC 식별자 비충돌, axis 변경 시 전체/부분 선택 조정, drill 시 기존
  선택 보존을 검증합니다.
- 실행 중인 앱에서 매트릭스/개별 그래프 전환과 비활성 chart 해제를 확인합니다.
- 매트릭스 탭 복귀 시 dataZoom 초기화가 수용된 동작과 일치하는지 확인합니다.
- `CD만 선택`, `전체 선택`, 개별 토글 및 전체 해제 빈 상태를 확인합니다.
- focus MSR 및 활성 CD 파라미터 변경 시 집합 동일 여부와 무관하게 전체
  선택으로 초기화되는지 확인합니다.
- axis mode 변경 시 전체 선택은 새 집합 전체로, 부분 선택은 교집합으로
  조정되는지 확인합니다.
- Dynamic FDC가 없는 MSR에서 selector와 빈 상태가 숨겨지고, CD와 `FDC 없음`
  안내가 두 보기에 모두 남는지 확인합니다.
- 매트릭스 FDC 셀 클릭 시 개별 그래프 전환, 선택 추가 및 scroll이 이어지는지
  확인하고, focus가 대상 panel로 이동하는지 확인합니다.
- tab의 roving tabindex, 방향키, `Home`/`End` 및 tabpanel 연결을 확인합니다.
- 측정 순서의 위치, 실패/이미지/정렬 색상 구분 및 CD/FDC 셀 너비를 light/dark
  mode에서 확인하고, CD/FDC 축 제목의 truncate를 확인합니다.

브라우저 검증이 불가능하면 source, typecheck 및 test 결과와 함께 시각적 동작이
미검증임을 명시합니다.
