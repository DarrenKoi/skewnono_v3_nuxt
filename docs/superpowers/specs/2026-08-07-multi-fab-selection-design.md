# 사이드바 FAB 다중 선택 — Phase 1 설계

- 작성일: 2026-08-07
- 상태: 설계 확정, 구현 전
- 범위: 좌측 사이드바에서 FAB을 여러 개 선택하고, filter-style 백엔드
  feature들이 선택된 FAB 집합의 데이터를 합쳐서 보여줍니다.

## 1. 배경

현재 사이드바는 FAB을 하나만 선택할 수 있고, 선택된 FAB은 URL 경로 세그먼트
(`/ebeam/cd-sem/r3/storage`)로 인코딩됩니다. 현업 사용자들이 관심 있는 FAB
2~3개를 한 번에 보고 싶다는 요청이 있었습니다.

타당성 조사 결과, 저장소는 이미 이 방향으로 절반쯤 준비되어 있습니다.

- **storage는 이미 다중 FAB을 지원합니다.** `useStorageApi.ts`가
  `fabNames: string[]`를 받아 `fab_name=R3,M16B`로 보내고, `storage/routes.py`가
  쉼표 목록으로 파싱하며, office adapter가 대문자 set으로 필터링합니다.
  Phase 1은 이 검증된 패턴을 나머지로 확장하는 일입니다.
- 백엔드 feature는 두 부류로 나뉩니다. **filter-style**(데이터셋을 읽고 행을
  FAB으로 거르는 방식 — storage, hardware, recipe_tat, fail_issue, meas_hist)은
  목록 하나 넘기면 되고, **key-style**(FAB이 Redis key 이름이나 fac feed에
  박혀 있는 방식 — recipe_search 계열, live_alarm)은 N회 조회 후 병합이라는
  구조 변경이 필요합니다. Phase 1은 filter-style만 다룹니다.
- activity logging은 이미 목록형입니다(`normalize_fab_name_list`). 변경 없음.

## 2. 결정 요약

| 항목 | 결정 | 근거 |
| --- | --- | --- |
| Phase 1 범위 | filter-style feature만. recipe-search 계열은 Phase B로 미룹니다. | key-style 구조 변경과 UI 재작업이 커서 첫 착륙을 작게 유지합니다(user-confirmed 2026-08-07). |
| recipe-tat 표시 | 선택된 FAB들을 **하나의 pool로 합산**합니다. FAB별 시리즈 분리는 하지 않습니다. | 차트·랭킹 구조가 오늘과 동일하게 유지되어 비용이 가장 작습니다(user-confirmed 2026-08-07). |
| 사이드바 상호작용 | 일반 클릭 = 단독 선택(기존 동작 유지), 체크박스/Cmd·Ctrl+클릭 = 추가·제거. | 기존 사용 습관을 깨지 않으면서 다중 선택을 얹습니다(user-confirmed 2026-08-07). |
| URL 인코딩 | 쉼표 결합 경로 세그먼트 `/ebeam/cd-sem/r3,m16b/storage`. | 기존 쿼리 규약(`fab_name=R3,M16B`)과 일치하고, `+`처럼 공백으로 오해될 여지가 없습니다. 단일 FAB URL은 오늘과 동일하여 기존 북마크가 전부 유효합니다. |
| primary FAB | `fabs[0]`이 primary입니다. 단일 FAB 전용 페이지는 primary를 사용합니다. | 선택 순서를 보존하는 가장 단순한 결정론적 규칙입니다. |
| skew-check | 다중 FAB **영구 제외**. | fleet consensus 통계가 FAB 내부 비교라서 FAB을 섞으면 표시가 아니라 통계 자체가 오염됩니다. |
| pm-planning | Phase 1 제외. | office adapter가 아직 stub이고, 지금 포함해도 검증할 실 데이터 경로가 없습니다. |
| meas-hist | 백엔드는 목록 지원(공유 helper 변경으로 자동 획득), UI는 Phase B. | 페이지가 recipe-search 계열 내비게이션 안에 있어 UI만 따로 먼저 여는 것이 어색합니다. |

## 3. Phase 1 feature 범위

| Feature | 페이지 | 변경 |
| --- | --- | --- |
| storage | `[fab]/storage/` | 백엔드 변경 없음(이미 목록형). 프론트가 목록을 넘기도록 연결만 합니다. |
| hardware | `[fab]/hardware.vue` | 프론트엔드만 — 장비 선택 목록 필터를 FAB set으로 확장(5.2 참조). |
| recipe-tat | `[fab]/recipe-tat/` | 공유 scope/filter 변경으로 획득(아래 5절). |
| fail-issue | `[fab]/fail-issue.vue` | 공유 scope/filter 변경으로 획득. |
| recipe-status | `[fab]/recipe-status.vue` | fail_issue API를 쓰므로 함께 획득. |
| 장비 상태(landing) | `[fab]/index.vue` (4개 tool type) | sem_list 기반 인벤토리를 FAB set으로 클라이언트 필터. |

**제외(동작 불변):** recipe-search 계열(catalog·compare·lateral·open·meas-hist),
live-alarm, skew-check, pm-planning, device-statistics·skewvoir(원래 fabless).

## 4. 프론트엔드 설계

### 4.1 상태 모델 — `stores/navigation.ts`

- `fab: string` → `fabs: string[]`. 불변식: 정규화 대문자, 중복 제거, 선택 순서
  보존, fallback 적용 후 최소 1개. `fabs[0]`이 primary입니다.
- `setFabs(fabs: string[])`가 단일 쓰기 지점을 승계합니다. 기존 `setFab`은
  `setFabs([fab])`로 위임해 호출부 마이그레이션을 점진화합니다.
- store 노출: `fabs`(목록), `fab`(primary — 기존 소비자 호환용 computed).

### 4.2 URL — `utils/fab.ts`

- `parseFabSegment(segment: string): string[]` — 쉼표 분리, 토큰별
  `normalizeFab`, 빈 토큰·sentinel 제거, 중복 제거. 전부 무효면 `[DEFAULT_FAB]`.
- `buildFabSegment(fabs: string[]): string` — 소문자 쉼표 결합. 기존
  `fabSegment`(단일)는 `buildFabSegment`로 위임합니다.
- 새 composable `useFabRoute()` — `[fab]` 페이지마다 복붙되어 있는
  `route.params.fab` 파싱 + `setFab` + `watch` 블록을 하나로 모읍니다. 반환:
  `{ fabs, primaryFab, fabSegmentString }`. Phase 1 페이지들이 이것으로
  이관하고, 제외 페이지는 `primaryFab`만 소비합니다.

### 4.3 영속화 — `plugins/persist-fab.client.ts`

- `skewnono:fab_name` key에 쉼표 결합 목록을 저장합니다. 읽을 때 토큰별로
  기존 `FAB_NAME_PATTERN` 검증, 무효 토큰은 버립니다. 배포 전 단일 값도
  1원소 목록으로 자연스럽게 읽힙니다.

### 4.4 사이드바 — `FabSidebar.vue`

- 펼친 모드: FAB 행에 hover 시 체크박스 노출. 체크박스 클릭 = 추가/제거,
  행 클릭 = 단독 선택. Cmd/Ctrl+클릭도 추가/제거로 동작합니다(접힌 모드 대응).
- 마지막 남은 FAB은 제거할 수 없습니다.
- 선택된 FAB 전부 active 스타일, primary는 현행 솔리드 처리를 유지합니다.
- `useNavigation`: `navigateToFab(fab)`(단독 선택)에 `toggleFab(fab)`(추가·제거)
  을 더합니다. URL push 규칙(같은 feature면 query 보존)은 현행 그대로입니다.
  `toolTypeHref`는 `buildFabSegment(fabs)`를 사용합니다.

### 4.5 단일 FAB 전용 페이지의 다중 선택 처리

- 제외 페이지(skew-check, live-alarm, recipe-search 계열, meas-hist)는
  primary FAB 데이터를 렌더하고, 2개 이상 선택 시에만 한 줄 힌트를 띄웁니다:
  "R3 기준 표시 — 다중 FAB은 추후 지원". 공용 소형 컴포넌트 1개로 구현합니다.
- 리다이렉트·차단은 하지 않습니다. 어떤 URL도 dead end가 되지 않습니다.

### 4.6 표시 의미론

- 집계 뷰(랭킹, 트렌드 라인)는 attribution 없이 합산합니다.
- 행 단위 테이블(storage 행, 장비 인벤토리, lot·측정 테이블)은 기존
  `fab_name` 컬럼/태그를 노출해 행 귀속을 유지합니다. 2개 이상 선택 시
  FAB 컬럼이 보이는지 확인하는 것이 각 페이지 작업의 완료 조건입니다.

## 5. 백엔드 설계

### 5.1 공유 지점 두 곳

- `_analytics_routes.resolve_analytics_scope`(recipe_tat·fail_issue 공유):
  `fab_name: str | None` → `fab_names: list[str]`(쉼표 파싱, strip, 대문자).
  `AnalyticsRequestScope` dataclass 필드도 동일 변경. 응답 meta가 FAB을
  echo하는 곳은 목록을 echo합니다.
  meas_hist는 자체 `_resolve_fab_name`을 쓰므로 이 변경의 영향 밖입니다 —
  filter 계층만 목록형이 되고 route는 Phase B까지 단일 파싱을 유지합니다.
- `_office_meas_hist.filter_clauses`: `fab_name` 인자를
  `fab_names: list[str] | None`으로 바꾸고, 1개면 기존 `term`, 2개 이상이면
  `terms` clause를 냅니다. (기존 단일 경로와 쿼리 모양이 달라지지 않도록
  1개일 때 `term`을 유지합니다.)

### 5.2 개별 feature

- hardware: **백엔드 변경 없음** (설계 후 구현 조사에서 확정). hardware API는
  장비 단위(`/hardware/<eqp_id>/<service>`)이고 `fab_name` 파라미터는 선택된
  장비 자신의 fab을 그대로 보내는 컨텍스트 값이다. FAB 필터의 실체는
  프론트엔드의 장비 선택 목록(`useSemListApi.filterRows`) — 그 함수만
  목록을 받게 확장한다.
- storage: 변경 없음(이미 목록형 — Phase 1의 참조 구현).

### 5.3 mock provider

- 손대는 feature마다 `providers/mock.py`가 대문자 set 필터를 적용합니다
  (storage office adapter의 `wanted` set 패턴과 동일). mock이 office 실물의
  대역이라는 원칙 유지 — docstring에 다중 FAB 필터 동작을 명기합니다.
- office adapter는 `office_example.py`를 같은 시그니처로 갱신합니다.
  (배포 시 사무실에서 `sync_office_adapters`로 복사 갱신.)

### 5.4 계약(contracts)

- scope를 담는 dataclass의 `fab_name: str` 필드는 `fab_names: list[str]`로
  바꿉니다. 단일 값 호환 별칭은 두지 않습니다 — 이 계약의 소비자는 전부
  저장소 안에 있고, provider-contract 테스트가 시그니처 변경을 전부 잡아줍니다.

## 6. Phase B에 기록해 두는 요구사항

- **recipe-search 다중 FAB에는 FAB 태그가 필수입니다.** 같은 recipe 이름이
  FAB마다 존재하므로, 목록의 각 행이 어느 FAB 소속인지 태그로 표시해야 하고
  상세 화면은 해당 recipe의 소속 FAB registry를 조회해야 합니다
  (user-confirmed 2026-08-07). per-fab Redis hash(`v3_{family}_{kind}_{fab}`)
  N회 조회 후 병합 — 전-FAB union 경로가 office_example.py에 선례로 있습니다.
- live-alarm 다중 FAB은 fac feed N개 병합 + refresh 비용 검토가 필요합니다.

## 7. 테스트·검증

- 프론트 unit(`node --test`): `parseFabSegment`/`buildFabSegment` 왕복,
  store 불변식(중복 제거·최소 1개·primary 순서), persist 토큰 검증.
- 백엔드 pytest: routes 쉼표 파싱, mock 목록 필터, `filter_clauses`의
  `term`/`terms` 분기 모양, provider-contract 스위트(office 테스트는
  import-skip 별칭 패턴으로 홈에서도 실행).
- 브라우저 검증(Playwright MCP, `verify` skill): 체크박스 상호작용, 새로고침
  후 URL 왕복, 2개 FAB 선택 시 storage·recipe-tat 합산 데이터, skew-check의
  단일 FAB 힌트.
- 작업은 CLAUDE.md 규칙대로 전용 `git worktree`에서 진행합니다.

## 8. 하지 않는 것

- Pinia 도입, TanStack Query 도입 — 기존 useState·useAsyncData 패턴 유지.
- FAB별 시리즈 분리 차트(사용자가 합산 pool을 선택).
- 사이드바 FAB 목록 숨김·즐겨찾기 필터(요청의 본질이 데이터 다중 선택으로
  확인됨).
- recipe-search·live-alarm·skew-check·pm-planning의 다중 FAB 동작.
