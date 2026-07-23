# Recipe Status Device Chip Height Design

## Goal

`Recipe 현황`의 `디바이스 선택` 영역에서 `lot_cd` 디바이스 코드 칩의 상하 여백을 늘려 가독성과 클릭 편의성을 개선합니다.

## Design

- 공용 `AnalyticsDevicePicker`의 `lot_cd` 디바이스 코드 버튼 높이만 `h-6`에서 `h-7`로 변경합니다.
- 카테고리 필터 칩의 높이, 디바이스 칩의 가로 패딩, 글꼴, 간격, 줄바꿈 및 스크롤 동작은 유지합니다.
- 이 공용 선택기를 사용하는 Recipe TAT 및 Fail Issue의 디바이스별 화면에 동일하게 적용합니다.

## Verification

- 프런트엔드 ESLint를 실행합니다.
- 프런트엔드 TypeScript 검사를 실행합니다.
- 변경 diff에서 `lot_cd` 디바이스 코드 버튼의 높이 외 UI 또는 동작 변경이 없는지 확인합니다.
