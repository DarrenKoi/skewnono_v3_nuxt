# 설정 화면 설명 문구 정리 설계

## 목적

설정 화면에서 설정과 직접 관련 없는 About 정보를 제거하고, API 토큰과 Appearance 영역의 설명을 쉬운 한국어로 제공합니다.

## 변경 범위

- `front-dev-home/app/pages/settings.vue`에서 About 카드 전체를 제거합니다.
- `front-dev-home/app/components/settings/ApiTokens.vue`의 API 토큰 안내 문장을 한국어로 번역합니다.
- `front-dev-home/app/components/settings/ColorModeSelector.vue`의 안내 문장, 선택 항목 설명, 적용 및 저장 상태 문장을 한국어로 번역합니다.
- `front-dev-home/app/components/settings/EchartThemeSelector.vue`의 안내 문장과 적용 및 저장 상태 문장을 한국어로 번역합니다.
- `front-dev-home/app/utils/echartsThemes.ts`의 각 차트 테마 설명을 한국어로 번역합니다.

## 문구 원칙

- 전문 용어보다 일상적인 한국어를 우선합니다.
- 한 문장을 짧게 쓰고 사용자가 해야 할 행동을 바로 알 수 있게 합니다.
- `/api/*`와 `Authorization: Bearer ...`는 실제 사용 형식이므로 그대로 유지합니다.
- `Light`, `Dark`, `System`, `Default`, `Vintage`, `Macarons` 같은 모드와 테마 이름은 선택 항목을 구분하는 고유 이름이므로 유지합니다.
- API 토큰 화면의 버튼, 표, 대화 상자 등 나머지 영문 UI는 이번 변경 범위에 포함하지 않습니다.

## 동작 및 화면 영향

데이터 흐름, 상태 저장, API 호출, 접근성 속성, 레이아웃은 변경하지 않습니다. About 카드가 사라지고 기존 설명 문구만 한국어로 표시됩니다.

## Appearance 카드 분리

- `SettingsColorModeSelector`는 `Appearance` 카드에 단독으로 배치합니다.
- `SettingsEchartThemeSelector`는 별도의 `ECharts theme` 카드에 단독으로 배치합니다.
- 두 카드는 설정 페이지에서 세로로 배치하고 기존 카드 간격을 유지합니다.
- 두 선택기 컴포넌트의 상태 저장과 선택 동작은 변경하지 않습니다.
- 카드 분리 외의 레이아웃과 문구는 변경하지 않습니다.

## 확인 방법

- `front-dev-home/`에서 `npm run lint`를 실행합니다.
- `front-dev-home/`에서 `npm run typecheck`를 실행합니다.
- `git diff --check`로 공백 오류를 확인합니다.
