# 사용 통계 페이지 조회 beacon 설계

- **작성일:** 2026-08-04
- **상태:** 승인된 설계, 구현 계획 작성 전 문서 검토 대기
- **적용 범위:** `back_dev_home/_logging`, `back_dev_home/activity`,
  `front-dev-home/app/plugins`, `front-dev-home/app/utils`

## 1. 배경

`/activity`(사용 통계)의 페이지 순위는 현재 `/api/*` 요청 건수를 집계합니다.
요청 건수를 페이지 인기도의 대리 지표로 사용하기 때문에 다음 세 가지 문제가
동시에 발생합니다.

- **mag-pixel 은 순위에 존재할 수 없습니다.** `pages/mag-pixel.vue` 는
  `~/utils/magPixel` 의 순수 계산 함수만 사용하며 API 를 호출하지 않습니다.
  요청이 0건이므로 어떤 mapping 을 추가해도 집계 대상이 되지 않습니다.
- **live-alarm 이 순위를 왜곡합니다.** `useLiveAlarmFeed.ts` 는 15초 ± 3초
  간격으로 polling 하므로 tab 하나당 시간당 약 240건을 발생시킵니다. 현재는
  `_BACKGROUND_EXACT` 에 등록되어 weight 0 으로 집계에서 제외되어 있고,
  동시에 `feature_map.py` 에 규칙이 없어 slug 이 `cdsem` / `hvsem` 으로
  fallback 됩니다. 즉 집계도 되지 않고 이름도 잘못되어 있습니다.
- **announcements 가 순위를 부풀립니다.** `AnnouncementBanner` 가
  `layouts/default.vue` 와 `layouts/hub.vue` 양쪽에 있으므로 모든 페이지
  로드마다 `/api/announcements` 가 1회 호출됩니다. 이는 특정 페이지에 대한
  관심이 아니라 세션 수를 세는 값입니다.

세 문제의 원인은 하나입니다. "요청 건수"와 "페이지를 열었다"는 서로 다른
사건이며, 순위가 답해야 하는 질문은 후자입니다.

이 설계는 페이지 조회 beacon 을 추가하여 **페이지 순위 집계만** 조회 기반으로
전환하고, 나머지 지표는 요청 기반으로 유지합니다.

## 2. 결정 사항

브레인스토밍에서 확정된 항목입니다.

| 항목 | 결정 |
| --- | --- |
| 전환 범위 | 페이지 순위 집계만 전환하고 DAU/WAU/MAU, 요청 총계, 일별 sparkline, FAB 순위는 요청 기반 유지 |
| 집계 단위 | 페이지를 열 때마다 1건(하루 1회 중복 제거하지 않음) |
| 발화 시점 | 경로가 아니라 **페이지 정체성**이 변할 때 |
| 과거 데이터 | backfill 하지 않고 배포 시점부터 새로 집계 |
| 분류 권한 | frontend 는 경로만 보고하고 slug 판정은 backend 가 수행 |

FAB 순위를 요청 기반으로 유지하는 이유는 `fab_name` 이 경로 변경 시점에
확정되지 않기 때문입니다. `fab_name` 은 사용자가 FAB 를 고른 뒤 데이터 요청의
query parameter 로 전달되므로(`useRecipeSearchApi.ts` 등) beacon 이 실어 보낼
수 없습니다.

## 3. 구조

beacon 은 별도의 저장소를 만들지 않고 기존 로그 경로를 그대로 사용합니다.
모든 `/api/*` 요청은 `_logging/activity.py` 의 `after_request` 를 지나
사무실에서는 OpenSearch `usage_events`, 홈에서는 mock 저장소에 기록됩니다.
beacon 자체가 하나의 요청이므로 이 경로에 그대로 올라탑니다.

이 선택의 핵심 근거는 **쓰기 경로를 새로 만들지 않는다**는 점입니다. 이
저장소의 모든 `office_example.py` 는 읽기 전용이며, 사무실에 새 쓰기 경로를
추가하는 일은 별도의 설계 대상입니다.

```text
경로 변경 → resolvePageIdentity(path, query) → 정체성이 바뀌었는가?
                                                  │ 예
                                                  ▼
                          POST /api/page-view {"path": "<경로+query>"}
                                                  │
                       activity/routes.py ────────┤ promote_page_view(slug)
                       204 반환                    │ (g._activity_page_slug 설정)
                                                  ▼
                       _logging/activity.py _emit()
                         feature = g._activity_page_slug ?? route_to_feature(path)
                         classify_activity(...) → ("page_view", 1)
                                                  ▼
                    OpenSearch usage_events(사무실) / mock 저장소(홈)
```

`promote_page_view` 는 기존 `promote_request_fab_names` 의 선례를 그대로
따릅니다. handler 가 `g` 에 값을 올리고 `_build_extra` 가 읽는 구조입니다.

### 3.1 경로를 `/api/page-view` 로 두는 이유

`/api/activity` 는 `_OPERATION_PREFIXES` 에 포함되어 있으므로
`/api/activity/page-view` 로 두면 모든 beacon 이 `operation` / weight 0 으로
분류되어 버려집니다. 이를 피하려면 `classify_activity` 의 우선순위 판정에
예외를 넣어야 하는데, 이 함수는 저장소에서 가장 읽기 쉽게 유지되어야 하는
축에 속합니다. 최상위 경로 `/api/page-view` 를 쓰면 예외 없이 해결됩니다.
blueprint 는 `activity/routes.py` 가 소유하되 경로만 prefix 밖에 둡니다.

## 4. 페이지 정체성

정체성은 두 곳에서 서로 다른 목적으로 다룹니다. 혼동하지 않아야 합니다.

- **frontend `resolvePageIdentity`** — "직전과 같은 페이지인가"만 판단하여
  beacon 발화 여부를 정합니다. slug 을 만들지 않습니다.
- **backend `page_to_feature`** — 전달받은 문자열을 slug 으로 판정합니다.
  slug vocabulary 는 backend 에만 존재하므로 frontend 가 어긋날 여지가
  없습니다.

beacon 은 query 를 포함한 경로 문자열 하나(`"/ebeam/cd-sem/M14/recipe-status?tab=tat"`)
를 보냅니다. `route_to_feature` 가 query 없는 경로를 받는 것과 달리
`page_to_feature` 는 query 를 포함해 받고 필요한 경우에만 해석합니다. 현재
query 를 보는 경로는 `recipe-status` 하나뿐입니다.

`resolvePageIdentity(path, query)` 는 순수 함수이며 다음을 보장합니다.

- 같은 페이지 안에서 FAB 를 바꾸거나 filter query 를 바꾸면 정체성이
  변하지 않습니다. 따라서 beacon 이 다시 발화하지 않습니다.
- 정체성을 확정할 수 없으면 `null` 을 반환하고, `null` 일 때 beacon 은
  발화하지 않습니다.

### 4.1 recipe-status 의 tab

`/ebeam/<tool>/<fab>/recipe-status` 는 단일 route 에 세 tab 을 담은 shell 이며
`?tab=` 이 실제 정체성입니다. Recipe TAT 와 Fail Issue 는 서로 다른 기능이고
backend slug 도 이미 둘로 나뉘어 있으므로, 이 route 에 한해 `tab` 을
정체성에 포함합니다.

| frontend 경로 | slug |
| --- | --- |
| `…/recipe-status?tab=tat` | `recipe_tat` |
| `…/recipe-status?tab=align` | `fail_issue` |
| `…/recipe-status?tab=meas` | `fail_issue` |
| `…/recipe-status` (tab 미확정) | beacon 발화하지 않음 |

`align` 과 `meas` 가 같은 slug 인 이유는 두 tab 이 같은
`/api/<tool>/fail-issue` 응답의 `align_fail_*` 과 `meas_fail_*` 를 각각
보여주는 하나의 기능이기 때문입니다.

tab 이 없는 상태에서 발화하지 않는 이유는 중복 집계를 막기 위해서입니다.
`RecipeStatusView.vue` 는 mount 시 `router.replace` 로 `?tab=` 을 URL 에 다시
써 넣으므로, tab 없는 방문은 곧바로 tab 있는 경로 변경으로 이어집니다. 양쪽
모두 발화하면 한 번의 방문이 두 건으로 기록됩니다.

### 4.2 운영 페이지

`/activity`, `/admin/*`, `/settings`, `/endpoints`, `/identify`, `/intro` 는
기존 `_OPERATION_PREFIXES` 규칙과 같은 취급을 받습니다. 로그에는 남지만
weight 0 이므로 순위에 오르지 않습니다.

## 5. 변경 대상

| 단위 | 책임 |
| --- | --- |
| `app/utils/pageIdentity.ts` | `resolvePageIdentity(path, query)` 순수 함수. 단위 테스트 대상 |
| `app/plugins/pageView.client.ts` | route 감시, 정체성 변화 시 POST. 실패는 무시 |
| `_logging/feature_map.py` | `page_to_feature(path)` 추가. frontend 경로 → slug map |
| `_logging/policy.py` | `page_view` kind 추가, `/api/announcements` 를 `_BACKGROUND_EXACT` 에 추가 |
| `_logging/activity.py` | `promote_page_view()` 추가, `_emit` 이 승격된 slug 를 우선 사용 |
| `activity/routes.py` | `POST /api/page-view` 추가, 204 반환 |
| `activity/providers/mock.py` | `record_request` 가 `page_view` 를 수용, 순위는 조회 기반, seed 에 조회 행 추가 |
| `activity/providers/opensearch_reader.py` | 순위 집계 filter 를 `page_view` 로 교체, 기본 filter 에 `page_view` 허용 |
| `app/utils/activity.ts` | `live_alarm`, `mag_pixel`, `chat` 라벨 추가 |

`page_to_feature` 는 `route_to_feature` 를 고쳐 쓰지 않고 별도 함수로 둡니다.
`recipe-status` 가 보여주듯 두 vocabulary 는 형태가 다릅니다. 하나의 route 가
두 기능에 대응하는 경우는 API 경로 map 에 존재하지 않습니다. slug 상수는
공유하므로 과거 데이터와의 연속성은 유지됩니다.

`feature_map.py` 의 "한 번 기록된 slug 은 이름을 바꾸지 않는다" 규칙을 지켜
`recipe_tat` 과 `fail_issue` 는 그대로 둡니다.

## 6. 오류 처리

- beacon 은 fire-and-forget 입니다. 실패해도 사용자에게 노출하지 않고 화면
  전환을 막지 않습니다.
- 경로가 없거나 해석할 수 없으면 `400` 을 반환하고 조회로 기록하지
  않습니다.
- 20 req / 5 s rate limit 에 걸리면 `429` 가 되고, `classify_activity` 는
  이미 status ≥ 400 을 `operation` / weight 0 으로 처리하므로 오류 없이 집계만
  누락됩니다. 빠른 tab 전환은 과소 집계될 뿐 실패하지 않습니다.

## 7. 전환

순위는 배포 시점부터 새로 쌓입니다. 배포 이전 문서는 `activity_kind` 가
`feature` 이므로 조회 기반 집계에 잡히지 않습니다. 7일 창은 일주일, 30일 창은
한 달에 걸쳐 채워지며, 그 사이에는 누적된 만큼만 표시하고 화면에 집계 시작일을
함께 안내합니다. 요청 기반 과거 데이터는 `/admin-logs` 에서 그대로 조회할 수
있습니다.

요청 기반 집계로 자동 fallback 하지 않습니다. 같은 숫자가 예고 없이 다른
단위로 바뀌는 편이 빈 구간보다 해석을 더 어렵게 만들고, fallback 이 동작하는
구간이 정확히 live-alarm 과 announcements 왜곡이 되살아나는 구간이기
때문입니다.

## 8. 테스트

backend

- `page_to_feature` 경로 → slug mapping 표. `recipe-status` 의 세 tab 포함
- `classify_activity` 가 beacon 을 `("page_view", 1)` 로,
  `/api/announcements` 를 `("background", 0)` 으로 분류
- middleware 통합: `POST /api/page-view` 가 `feature=<페이지 slug>` 로
  기록되고 `page-view` 로 기록되지 않음
- mock provider 가 조회 행으로 순위를 만들고 요청 행은 순위에 넣지 않음
- reader 집계 질의 형태 검증

frontend

- `pageIdentity.test.ts`: FAB 전환과 feature segment 재작성이 재발화를
  일으키지 않음, `?tab=` 미확정 시 `null` 반환, 세 tab 이 각각 다른 정체성

## 9. 범위 밖

- FAB 순위의 조회 기반 전환. `fab_name` 이 경로 변경 시점에 확정되지 않아
  별도 설계가 필요합니다.
- 과거 요청 로그로부터의 조회 backfill.
- 체류 시간 측정. 이번 설계는 "열었다"만 셉니다.
