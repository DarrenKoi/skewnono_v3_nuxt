# 디바이스 통계 구현 계획

## 목적

`디바이스 통계` 탭에서 Flask mock backend의 데이터를 조회하여 Nuxt 화면에 표시합니다. `docs/datatables`에 정리된 `r3_device_grp`와 `device_desc` 구조를 기준으로 Phase 1 home/offline 환경에서 사용할 mock 데이터를 생성합니다.

## 데이터 기준

- `r3_device_grp`는 `R3` 전용 데이터로 생성합니다.
- `device_desc`는 `M11`, `M12`, `M14`, `M15`, `M16` Fab 데이터로 생성합니다.
- 각 source는 약 2,000개 row를 생성합니다.
- 모든 도메인 컬럼 값은 string으로 유지합니다.
- R 계열은 `fac_id -> prod_catg_cd -> lot_cd` 순서로 탐색합니다.
- M 계열은 `fac_id -> tech_nm` 순서로 탐색합니다.

## API 계획

- Flask에 `GET /api/device-statistics` endpoint를 추가합니다.
- `fac_id` query parameter는 comma-separated multi-select 값을 받습니다.
- 예시는 `GET /api/device-statistics?fac_id=R3,M11,M14`입니다.
- `fac_id`가 없으면 전체 mock row를 반환합니다.
- 응답은 row 배열만 반환합니다.
- source별로 없는 컬럼은 빈 문자열 `""`로 채웁니다.

## 화면 계획

- 기존 `front-dev-home/app/pages/ebeam/cd-sem/[fab]/device-statistics.vue` placeholder를 실제 화면으로 교체합니다.
- route의 Fab 값을 초기 선택값으로 사용하되, 화면 안에서 Fab multi-select override를 제공합니다.
- `R3`가 선택되면 `prod_catg_cd`와 `lot_cd` multi-select filter를 표시합니다.
- `M`으로 시작하는 Fab이 선택되면 `tech_nm` multi-select filter를 표시합니다.
- R과 M Fab이 함께 선택되면 두 filter group을 모두 표시합니다.
- 검색 가능한 paginated table로 filtered row를 표시합니다.
- v1에서는 chart library를 추가하지 않고 Nuxt UI와 Tailwind class만 사용합니다.

## 검증 계획

- `/api/device-statistics?fac_id=R3`가 2,000개 R3 row를 반환하는지 확인합니다.
- `/api/device-statistics?fac_id=M11,M14`가 선택된 M Fab row만 반환하는지 확인합니다.
- `/api/device-statistics`가 4,000개 전체 row를 반환하는지 확인합니다.
- `front-dev-home/`에서 `npm.cmd run lint`와 `npm.cmd run typecheck`를 실행합니다.
- repo root에서 `npm.cmd run lint:md`를 실행합니다.
