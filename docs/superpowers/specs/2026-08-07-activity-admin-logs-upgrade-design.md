# 사용 통계 · 운영 로그 화면 개선 설계

- 작성일: 2026-08-07
- 상태: 설계 확정, 구현 전
- 범위: `/admin/logs`와 `/activity` 두 화면의 사용성 개선 4건입니다. 로깅 파이프라인의
  쓰기 경로와 OpenSearch 매핑은 변경하지 않습니다.

## 1. 배경

두 화면 모두 동작하지만, 관리자가 실제로 하려는 일을 한 번에 하지 못합니다.

- `/admin/logs`에서 오류만 보려면 `status_min`/`status_max`에 숫자를 직접 입력해야
  합니다. 오류 추적이 이 화면의 주 용도인데, 그 용도가 자유 입력 뒤에 숨어 있습니다.
- `/admin/logs`의 User 컬럼은 사번만 보여줍니다. `/activity`의 사용자 표는 이미
  이름을 붙여 보여주므로, 같은 관리자가 두 화면 사이를 오갈 때 사번을 손으로
  대조해야 합니다.
- `/activity`의 사용자 표는 기본 정렬이 "요청 많은 순"입니다. 관리자가 이 표를 여는
  이유는 대개 "누가 최근에 쓰고 있는가"이므로 기본값이 목적과 어긋납니다.
- 인기 기능 랭킹에 `CD-SEM`, `홈`이 올라오고 Fab별 사용 카드에 `미지정` 버킷이
  섞입니다. 셋 다 "무엇을 뜻하는지 알 수 없는 항목"으로 읽힙니다.

네 번째 항목은 조사 결과 원인이 서로 달랐습니다. 2절과 5절에 기록합니다.

## 2. 조사 결과 — 랭킹이 불분명해진 두 원인

### 2.1 `CD-SEM`은 모호한 기능이 아니라 누락된 규칙입니다

`page_to_feature()`(`back_dev_home/_logging/feature_map.py:211`)는 규칙에 없는
`/ebeam/<tool>/...` 경로를 **툴 세그먼트**로 떨어뜨립니다. 이 fallback에 걸리는
페이지는 `[fab]/index.vue` 하나뿐이며, 그 페이지가 렌더링하는 것은
`EbeamToolInventoryView` — 즉 **장비 상태**입니다.

`/ebeam/<tool>`(fab 없는 형태)은 `navigateTo(..., { replace: true })`만 하는
redirect 전용 stub입니다. Vue Router는 redirect로 중단된 내비게이션에 대해
`afterEach`를 실행하지 않으므로 beacon이 발사되지 않습니다. 따라서 랭킹에 쌓인
`cdsem`/`hvsem` 행은 사실상 전부 장비 상태 페이지입니다.

네 툴 계열(`cd-sem`, `hv-sem`, `provision`, `verity-sem`)이 모두 같은
`EbeamToolInventoryView`를 렌더링하므로, **하나의 페이지가 네 개의 무의미한 슬러그로
쪼개져** 있습니다.

### 2.2 `미지정`은 쓰레기 데이터가 아니라 FAB 무관 트래픽입니다

Fab 집계는 `fab_name_list` 필드를 기준으로 버킷을 만들고, 비어 있는 문서를
`미지정`으로 모읍니다(`activity/providers/opensearch_reader.py:566-570`).
`fab_name`을 보내지 않는 페이지가 실제로 존재합니다 — `device_statistics`(fab이 아니라
`fac_id`로 조회합니다), AFM, skewvoir 일부 호출입니다.

즉 `미지정`은 "FAB을 고르지 않은 사용자"가 아니라 "FAB 개념이 없는 페이지"입니다.
"모두가 FAB을 눌러야 앱을 쓸 수 있다"는 전제는 `[fab]` 라우트에는 맞지만 이들
페이지에는 맞지 않습니다.

## 3. 결정 요약

| 항목 | 결정 | 변경 위치 |
| --- | --- | --- |
| 4XX/5XX 필터 | 상태 프리셋 세그먼트 컨트롤을 추가하고, 즉시 적용합니다. | 프론트 전용 |
| 로그 사용자 이름 | `routes.py`에서 `lookup_members()`로 조인하고 `members` map으로 실어 보냅니다. | 백엔드 route + 프론트 |
| 사용자 표 기본 정렬 | `recent`(최근 활동 순)으로 바꿉니다. | 프론트 전용 |
| `CD-SEM`/`HV-SEM` | `tool_inventory`(장비 상태) 슬러그를 신설합니다. | feature_map + pageIdentity + fixture |
| `홈` | 랭킹에서 제외합니다. beacon 자체를 보내지 않습니다. | feature_map + pageIdentity + fixture |
| `미지정` FAB | Fab별 카드에서만 제외하고, 제외 사실을 카드에 명시합니다. | 프론트 전용 |

## 4. 항목별 설계

### 4.1 `/admin/logs` — 오류 상태 프리셋

필터 카드 최상단에 세그먼트 컨트롤을 둡니다: **전체 · 4XX · 5XX · 오류 전체**.

| 프리셋 | `status_min` | `status_max` |
| --- | --- | --- |
| 전체 | `''` | `''` |
| 4XX | `400` | `499` |
| 5XX | `500` | `599` |
| 오류 전체 | `400` | `599` |

백엔드는 이미 범위를 받습니다(`admin_logs/query.py:145-153`). 따라서 계약 변경 없이
프론트만 바꿉니다.

**단일 진실 원천은 `status_min`/`status_max`입니다.** 프리셋은 별도 상태를 들지 않고
`draft`의 두 값에 써 넣으며, 현재 활성 프리셋은 그 두 값에서 되읽는 `computed`입니다.
따라서 사용자가 숫자를 직접 고치면 프리셋 표시가 자동으로 해제되고, 두 컨트롤이
서로 어긋날 수 없습니다.

**프리셋은 Search 버튼 없이 즉시 적용합니다.** 이 카드의 다른 컨트롤은 모두
Search를 눌러야 반영되므로 의도적인 예외입니다 — "오류만 보여줘"를 한 번에 하지
못하면 이 항목의 목적이 사라집니다. 대가는 즉시 적용이 `draft`의 다른 미적용
입력값까지 함께 반영한다는 점이며, 이는 `applyFilters()`의 기존 동작을 그대로 쓰기
때문입니다. 프리셋 전용 적용 경로를 따로 두면 적용 경로가 둘로 갈라지므로 택하지
않습니다.

컨트롤은 `UTabs`가 아니라 **칩 형태의 `UButton` 행**을 씁니다. 프리셋은 "선택 없음"
상태를 가질 수 있는데(사용자가 범위를 직접 입력한 경우) `UTabs`에는 그 상태를 표현할
방법이 없습니다.

### 4.2 `/admin/logs` — User 컬럼 이름 표시

조인은 **`admin_logs/routes.py`**에서 수행합니다. `activity/routes.py:52-82`가 이미
같은 판단을 기록해 두었습니다 — OpenSearch 문서에는 이름이 없으므로 provider가
약속해서는 안 되고, `lookup_members()`는 사무실 Redis를 걸지 홈 행을 지어낼지 스스로
결정하므로 `mock.py`와 `office.py`가 기여할 것이 없습니다.

응답 형태는 `/activity`와 다르게 **형제 map**으로 싣습니다.

```python
members: dict[str, str]   # {user_id: emp_nm}
```

행마다 펼치지 않는 이유는 두 가지입니다. 한 페이지가 최대 200행인데 서로 다른
사번은 대개 10개 미만이라 이름이 수십 번 중복됩니다. 그리고 `LogItem`은 이미 원본
문서 전체를 `raw`로 싣고 있으므로, `raw`에 없는 `emp_nm`이 최상위에 붙으면
OpenSearch 필드로 오해됩니다.

이름을 찾지 못한 사번은 map에서 **생략**합니다. 프론트는 map에 없으면 사번을
그대로 보여주므로 `null`을 실을 필요가 없고, 값의 타입이 `str` 하나로 유지됩니다.

셀은 `/activity` 사용자 표와 같은 형태로 렌더링합니다 — 이름이 첫 줄, 사번이 아래
줄이며, 이름이 없으면 사번만 한 줄로 둡니다.

**범위 밖:** 이름으로 검색·필터링하는 기능. member 디렉터리는 사번을 키로 하는
Redis 해시(`HGET members <empno>`)이므로 역인덱스가 없습니다. 이름 → 사번 조회는
별도 설계가 필요합니다.

### 4.3 `/activity` — 사용자 표 기본 정렬

`front-dev-home/app/composables/useActivityUserTable.ts`에서 세 곳을 함께 옮깁니다.

| 줄 | 현재 | 변경 후 |
| --- | --- | --- |
| `:15` | `ref<UserSort>('requests')` | `ref<UserSort>('recent')` |
| `:71` | `sort.value !== 'requests'` | `sort.value !== 'recent'` |
| `:77` | `sort.value = 'requests'` | `sort.value = 'recent'` |

세 줄은 반드시 함께 움직여야 합니다. 기본값만 바꾸면 페이지를 연 순간 "초기화"
버튼이 활성 상태로 켜지고, 누르면 기본값이 아닌 "요청 많은 순"으로 되돌아갑니다.

`recent` 분기에 `user_id` tiebreak를 추가합니다. 현재는 `last_seen`만 비교하므로
타임스탬프가 같은 행들의 순서가 불안정합니다.

정렬 옵션 목록의 순서는 바꾸지 않습니다 — 드롭다운 순서와 기본값은 별개이며,
목록을 흔들면 이미 익숙해진 사용자의 손이 어긋납니다.

### 4.4 기능 랭킹 정리

#### 4.4.1 `tool_inventory` 슬러그 신설

`/ebeam/<tool>` 및 `/ebeam/<tool>/<fab>`(둘 다 페이지 세그먼트가 없는 형태)를 네 툴
계열 공통으로 `tool_inventory`에 매핑합니다. 한국어 라벨은 **장비 상태**입니다.

**규칙에 없는 e-beam 페이지의 fallback은 기존대로 툴 슬러그(`cdsem`/`hvsem`)를
유지합니다.** fallback까지 `tool_inventory`로 바꾸면, 앞으로 추가될 미등록 e-beam
페이지가 조용히 장비 상태로 집계됩니다. 모호한 것보다 나쁩니다.

백엔드는 fab 세그먼트를 떨어낸 뒤 `rest`가 비었는지를 `_PAGE_RULES` 순회 **전에**
확인합니다. 프론트 `canonicalize()`는 현재 `rest.length === 0`일 때 `landing`을
반환하는데(`pageIdentity.ts:97`), 그러면 미등록 페이지의 fallback 값과 충돌하므로
전용 canonical 경로 상수 `TOOL_INVENTORY_PATH = '/tool-inventory'`로 바꾸고 이를
`IDENTITY_RULES`에 등록합니다. 이 값은 실제 라우트 조각이 아니라 fab 허브 형태를
가리키는 합성 경로이므로 그 사실을 주석으로 남깁니다 — 해당 파일은 "라우트 조각만
담는다"를 헤더에 명시하고 있습니다.

**받아들이는 결과:** CD-SEM 장비 상태 → HV-SEM 장비 상태 이동은 하나의 identity이므로
beacon이 다시 발사되지 않습니다. `storage`가 이미 같은 방식으로 동작하며, 랭킹이
답하는 질문은 "어떤 페이지가 인기 있는가"이지 "어떤 툴 계열인가"가 아닙니다.

#### 4.4.2 `홈` 랭킹 제외

`page_to_feature("/")`가 `None`을 반환하고, `resolvePageIdentity('/')`가 `null`을
반환하도록 합니다.

프론트가 `null`을 받으면 `pageView.client.ts`의 `report()`가 POST 자체를 하지
않습니다. 따라서 이것은 weight 0으로 기록되는 것이 아니라 **행이 생기지 않는**
쪽입니다.

`/`는 여전히 실제 페이지이지만 모두가 거쳐 가는 진입 경유지이므로 "인기 기능"
순위에서 의미를 갖지 못합니다. 진입 규모는 DAU/WAU/MAU가 이미 답합니다.

#### 4.4.3 `미지정` FAB 버킷 제외

`activity.vue`의 `fabsForWindow` computed에서 `미지정` 행을 걸러냅니다. API 응답과
office adapter는 건드리지 않으므로 되돌리기가 한 줄입니다.

리터럴을 화면에 심지 않고 `utils/activity.ts`에 상수로 두고, 백엔드 리터럴과 같은
값이라는 사실을 주석으로 남깁니다.

**제외 사실을 카드에 명시합니다.** "Fab별 페이지 사용" 카드 헤더에 `FAB 무관 페이지
제외` 캡션을 둡니다. 조용히 빠진 데이터는 "전부 보여주고 있다"로 읽히며, 이 카드에서
device-statistics·AFM 트래픽이 사라진 것은 설명이 필요한 누락입니다.

#### 4.4.4 과거 라벨 유지

`utils/activity.ts`의 `FEATURE_LABELS`에서 `home`, `cdsem`, `hvsem`, `provision`,
`verity_sem`을 **삭제하지 않습니다**. OpenSearch에 이미 쌓인 행은 30일 창이 지나
빠질 때까지 계속 랭킹에 나오며, 라벨을 지우면 그 기간 동안 humanize fallback이
`Cdsem` 같은 문자열을 보여줍니다.

`tool_inventory: '장비 상태'`를 추가합니다.

## 5. 시계열 분리에 대하여

`feature_map.py` 헤더는 "이미 기록된 슬러그의 이름을 바꾸지 말 것 — 시계열이
쪼개진다"를 명시합니다. 이번 변경은 이름 변경이 아니라 `cdsem` 기록이 멈추고
`tool_inventory` 기록이 시작되는 형태이지만, 결과적으로 약 30일간 랭킹에 두 계열이
공존합니다.

이를 감수합니다. 기존 `cdsem` 계열은 fab 허브 페이지와 임의의 미등록 페이지를 한데
섞고 있었으므로 애초에 해석 가능한 시계열이 아니었습니다. 과거 데이터를 소급 수정할
수단은 없으며(재색인은 이 변경의 범위 밖입니다), 라벨을 유지하므로 공존 기간에도
화면은 읽을 수 있는 상태로 남습니다.

`PAGE_VIEW_SINCE`(`utils/activity.ts:114`)는 영향을 받지 않습니다. 그 값은 page-view
수집이 시작된 날짜이지 슬러그 어휘에 대한 것이 아닙니다.

## 6. 변경 파일

### 백엔드

| 파일 | 변경 |
| --- | --- |
| `back_dev_home/_logging/feature_map.py` | `/` → `None`, 빈 `rest` → `tool_inventory` |
| `back_dev_home/admin_logs/contracts.py` | `NamedLogQueryResponse`(= `LogQueryResponse` + `members`) 추가 |
| `back_dev_home/admin_logs/routes.py` | `lookup_members()` 조인 |

`data.py`와 `providers/*.py`는 변경하지 않습니다.

### 프론트엔드

| 파일 | 변경 |
| --- | --- |
| `app/pages/admin/logs.vue` | 상태 프리셋, User 셀 이름 표시 |
| `app/composables/useAdminLogsApi.ts` | 응답 타입에 `members` 추가 |
| `app/composables/useActivityUserTable.ts` | 기본 정렬 3곳, `recent` tiebreak |
| `app/pages/activity.vue` | `미지정` 제외, 카드 캡션 |
| `app/utils/activity.ts` | `tool_inventory` 라벨, `UNASSIGNED_FAB` 상수 |
| `app/utils/pageIdentity.ts` | `/` → `null`, 빈 `rest` 전용 canonical 경로 |
| `app/utils/__fixtures__/pageIdentityContract.json` | 아래 표 |

### 공유 fixture

| 경로 | 현재 | 변경 후 |
| --- | --- | --- |
| `/` | `home` | `null` |
| `/ebeam/cd-sem` | `cdsem` | `tool_inventory` |
| `/ebeam/cd-sem/M14` | `cdsem` | `tool_inventory` |
| `/ebeam/hv-sem/R3` | `hvsem` | `tool_inventory` |

추가하는 행:

| 경로 | 슬러그 | 목적 |
| --- | --- | --- |
| `/ebeam/provision/R3` | `tool_inventory` | 네 툴 계열이 한 슬러그임을 고정 |
| `/ebeam/verity-sem/M14` | `tool_inventory` | 같음 |
| `/ebeam/cd-sem/M14/unmapped-page` | `cdsem` | fallback이 바뀌지 않았음을 고정 |

## 7. 테스트

| 대상 | 방법 |
| --- | --- |
| `page_to_feature` | `_logging/tests/test_feature_map_contract.py` — fixture 주도이므로 표를 고치면 자동 적용됩니다. `test_feature_map.py`에 `tool_inventory`·`/` 단위 케이스를 추가합니다. |
| `resolvePageIdentity` | `app/utils/pageIdentity.test.ts` — 같은 fixture를 읽으므로 자동 적용됩니다. |
| 로그 이름 조인 | `admin_logs/tests/test_routes.py` **신규** — 디렉터리가 이름을 줄 때 map에 실리고, 못 줄 때 생략되며, 어느 경우에도 `items`가 줄지 않음을 확인합니다. |
| `미지정` 제외 | `app/utils/activity.test.ts`에 필터 헬퍼 케이스를 추가합니다. |
| 상태 프리셋 | 브라우저 확인. 프리셋↔수동 입력 왕복이 `.vue` 안의 `computed`라 `node --test` 범위 밖입니다. |
| 기본 정렬 | 브라우저 확인. 같은 이유로 자동 테스트 범위 밖입니다. |

전체 스위트: `.venv/bin/python -m pytest -q`, `npm test`, `npm run typecheck`,
`npm run lint`, `npm run lint:md`.

브라우저 확인은 `verify` 스킬을 따르며, 관리자 화면이므로 `LASTUSER=local-dev`로
확인합니다.

## 8. 범위 밖

- OpenSearch 재색인 또는 과거 문서의 슬러그 소급 수정.
- `/admin/logs`에서 이름으로 검색·필터링(4.2 참조).
- `/admin/logs`에 팀(`dept_nm`) 컬럼 추가. 조인은 같은 왕복으로 팀도 가져오지만
  화면에 쓰지 않으므로 응답에 싣지 않습니다.
- 오류 건수 KPI·요약 카드. 이번 항목은 필터이지 대시보드가 아닙니다.
- `미지정` 트래픽을 FAB별로 귀속시키는 작업(예: `device_statistics`가 `fac_id`를
  `fab_name`으로도 실어 보내게 하기). 로깅 쓰기 경로 변경이며 별도 판단이 필요합니다.
