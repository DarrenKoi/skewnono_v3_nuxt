# Skewvoir 워크스페이스 view 사용량 계측 설계

- **작성일:** 2026-08-04
- **상태:** 승인된 설계, 구현 계획 작성 전 문서 검토 대기
- **적용 범위:** `back_dev_home/_logging`, `back_dev_home/activity`,
  `front-dev-home/app/composables`, `front-dev-home/app/pages/activity.vue`,
  `docs/datatables/skewnono_logging.txt`

## 1. 배경

`/activity`(사용 통계) 페이지의 기능 순위에 `msr-images` 항목이 노출되고
있습니다. 그러나 이는 모니터링 대상이 아닙니다. `msr-images`는 Skewvoir가
내부적으로 사용하는 이미지 조회·warm 경로일 뿐이며, 사용자가 인지하는 기능이
아닙니다.

실제로 알고 싶은 것은 Skewvoir 워크스페이스의 **분석 view 사용량**입니다.
즉 측정 개요·위치 비교·FDC 분석·Time-Series·상관/분포·이미지 갤러리 중 어떤
lens가 실제로 쓰이는지입니다.

### 1.1 현재 구조가 view를 볼 수 없는 이유

`back_dev_home/_logging/feature_map.py`의 `route_to_feature(path)`가 기능
분류의 **유일한** 입력입니다. 즉 기능 slug는 전적으로 API 경로에서 파생됩니다.

그런데 Skewvoir의 view 전환은 HTTP 요청을 전혀 발생시키지 않습니다.

- `components/ebeam/skewvoir/Workspace.vue`는 이미 적재된 데이터 위에서
  `v-if`로 view를 교체합니다.
- `composables/useSkewvoirAnalysis.ts`의 모든 fetch는 `selection.msr`과
  `activeParam`에만 반응하며 `activeKind`에는 반응하지 않습니다.

따라서 기존 `/api/msr-file` 요청에 view를 태깅하는 방식은 성립하지 않습니다.
선택(selection)이 바뀌는 순간 활성화되어 있던 view가 모든 사용량을 가져가고,
그 뒤에 진입한 view는 한 건도 기록되지 않기 때문입니다.

### 1.2 `msr-images`가 노출되는 이유

`feature_map.py`는 `/api/msr-image`(단수)를 `skewvoir`로 매핑합니다. 그러나
실제 목록·warm 경로는 `msr_image/routes.py`의 `@bp.get("/msr-images")` 등
**복수형**입니다. 접두사 판정이 `path == prefix or path.startswith(prefix + "/")`
이므로 `/api/msr-images`는 두 조건 모두에 걸리지 않고, 미등록 경로 fallback이
첫 경로 segment인 `msr-images`를 그대로 slug로 반환합니다.

또한 `policy.py`의 `_BACKGROUND_CHILD_PREFIXES`는 `/api/msr-images/<job_id>`
같은 하위 경로만 background로 처리하므로, warm job이 반복 호출하는
`/api/msr-images` 자체는 weight 1로 집계되어 순위를 끌어올립니다.

## 2. 목표와 비목표

**목표**

- Skewvoir 6개 view의 사용량을 사용 통계 페이지에 노출합니다.
- `msr-images`를 기능 순위에서 제거합니다.
- 기존 `skewvoir` slug의 누적 시계열 연속성을 보존합니다.

**비목표**

- 다른 페이지의 내부 탭까지 포괄하는 범용 sub-view 차원은 만들지 않습니다.
  Skewvoir 전용으로 한정합니다.
- 경로 기반 기능 분류 체계 자체는 교체하지 않습니다.
- 개인 패널(`/activity/me`)은 변경하지 않습니다.

## 3. 설계

### 3.1 Beacon endpoint

view 전환이 요청을 만들지 않으므로, **로그에 남는 것만이 목적인** 엔드포인트를
하나 추가합니다.

```python
# back_dev_home/activity/routes.py
@bp.post("/skewvoir/view/<kind>")
def skewvoir_view_beacon(kind: str):
    ...  # 검증 후 204, 본문 없음, 저장소 쓰기 없음
```

핸들러는 실질적인 일을 하지 않습니다. `_logging/activity.py`의
`after_request`가 이미 모든 요청에 `feature`와 `activity_kind`를 붙여
기록하므로, beacon은 그 미들웨어에 분류할 대상을 제공할 뿐입니다. 새로운
쓰기 경로도, 새로운 저장소도, 새로운 office adapter도 필요하지 않습니다.

`kind`는 `SKEWVOIR_VIEW_MODES`의 6개 값으로 화이트리스트 검증합니다. 목록에
없는 값은 400을 반환하며, 400은 `classify_activity`에서 `operation`/weight 0이
되므로 임의의 slug가 색인에 유입되지 않습니다.

**경로 위치:** `activity` blueprint가 소유하되 경로는 `/api/skewvoir/...`로
둡니다. `policy.py`의 `_OPERATION_PREFIXES`에 `/api/activity`가 포함되어 있어
`/api/activity/...` 아래에 두면 weight 0이 강제되고, 이를 피하려면 예외 규칙을
추가해야 하기 때문입니다.

### 3.2 새 `activity_kind` 값 `"view"`

`_logging/policy.py`의 `ActivityKind` Literal에 `"view"`를 추가하고,
`classify_activity`가 beacon 경로를 `ActivityDecision("view", 0)`로 분류합니다.

이 한 가지 결정이 "Skewvoir 아래에 중첩" 요구사항을 자동으로 충족시킵니다.
기존 집계는 모두 `activity_kind`로 필터링하기 때문입니다.

- `_activity_filters()`는 `["entry", "feature"]`만 통과시킵니다.
- 기능 순위는 여기서 다시 `activity_kind == "feature"`로 좁힙니다.

따라서 `"view"`로 표시된 문서는 **기존의 모든 질의에 보이지 않습니다.**
`skewvoir`의 총계는 현재 값 그대로 유지되고, 6개 view row는 이를 명시적으로
요청하는 신규 집계에만 나타납니다. weight가 0이므로 요청 수와 DAU에도
영향이 없습니다.

### 3.3 OpenSearch mapping 변경이 필요 없는 이유

view 값은 별도 필드가 아니라 **기능 slug 안에** 인코딩합니다.

| view kind | slug |
| --- | --- |
| `dashboard` | `skewvoir_dashboard` |
| `position-stack` | `skewvoir_position_stack` |
| `fdc` | `skewvoir_fdc` |
| `time-series` | `skewvoir_time_series` |
| `correlation` | `skewvoir_correlation` |
| `gallery` | `skewvoir_gallery` |

`feature`와 `activity_kind`는 이미 keyword로 매핑되어 있으므로 색인 매핑을
건드리지 않습니다. 이는 중요한 제약을 회피합니다.
`ops_index_mgmt/skewnono_logging.py`는 `flask_modules`에서 복사된 vendored
파일이며 upstream과 byte 단위로 동일해야 하므로, 새 필드를 추가하면 두 저장소를
함께 수정해야 합니다.

`_KNOWN_EXTRA_KEYS`(`_logging/opensearch_handler.py`) 역시 변경이 없습니다.
새로 추가되는 것은 기존 키의 새로운 **값**이지 새로운 키가 아니기 때문입니다.

### 3.4 집계: user × view × day 중복 제거

한 사람이 같은 날 같은 view를 몇 번 오가든 1로 집계합니다. 비교 작업 중의
view 왕복이 순위를 왜곡하지 않도록 하기 위함입니다.

**미들웨어 게이트 (`_logging/activity.py`)**

현재 `after_request`는 `extra["activity_weight"] == 1`일 때만
`record_request`를 호출합니다. `"view"`는 weight 0이므로 이 조건을 함께
넓히지 않으면 **home 측 view 데이터가 전부 조용히 유실됩니다.**

```python
if extra["activity_weight"] == 1 or extra["activity_kind"] == "view":
    record_request(...)
```

weight를 1로 올려 게이트를 통과시키는 대안은 채택하지 않습니다. weight는
"사람의 가중 요청 1건"을 뜻하고 view beacon은 그 정의에 맞지 않으며, 색인된
`activity_weight`를 사용하는 기존·향후 질의를 오염시키기 때문입니다.

**Home (`activity/providers/mock.py`)**

`record_request`의 도입부는 현재 `activity_kind not in {"entry", "feature"}`
이면 즉시 반환하므로 `"view"`를 허용 집합에 추가해야 합니다. 단, `"view"`는
`state.daily`(요청 수)·`last_seen`·FAB 버킷을 갱신하기 전에 분기하여
`daily_views`만 갱신하고 반환합니다. 그렇지 않으면 weight 0이라는 결정이
mock 안에서 무효화됩니다.

`_UserState`에 `daily_views: dict[date, set[str]]`를 추가합니다. 이는 같은
파일에 이미 존재하는 `daily_fabs` 패턴을 그대로 따릅니다. `record_request`는
`activity_kind == "view"`인 경우 해당 날짜 set에 slug를 추가하고 즉시
반환합니다. 요청 수·기능 카운터·FAB 카운터는 건드리지 않습니다.
`_prune_old_days`의 순회 대상에 새 버킷을 포함시킵니다.

집계는 전체 사용자에 대해 창 내 각 날짜의 set 크기를 합산합니다.

**Office (`activity/providers/opensearch_reader.py`)**

`activity_kind == "view"` 필터 아래에서
`terms(feature)` → `date_histogram(KST 일 단위)` → `cardinality(user_id)`로
집계한 뒤, 일별 cardinality를 Python에서 합산합니다. `cardinality`는 이미
`get_summary`와 `_fab_window`에서 사용하는 확립된 형태입니다. 버킷 수는
최대 6 view × 30일이므로 비용이 문제되지 않습니다.

### 3.5 계약(contract) 변경

`activity/contracts.py`의 `SummaryResponse`에 두 필드를 추가합니다.

```python
class SummaryResponse(TypedDict):
    ...
    skewvoir_views_7d: list[FeatureCount]
    skewvoir_views_30d: list[FeatureCount]
```

`FeatureCount`를 재사용합니다. `feature`에는 view slug가, `count`에는 중복
제거된 user-day 수가 들어갑니다. 새 타입을 만들지 않는 이유는 프런트엔드의
`ActivityFeatureBarList.vue`를 **수정 없이** 재사용하기 위해서입니다.

`/api/activity/summary`는 식별된 모든 사용자에게 열려 있으므로(`routes.py`에서
`@require_admin`은 `/users*`에만 적용) 신규 엔드포인트가 필요하지 않습니다.

### 3.6 프런트엔드

**Beacon 발신** — `composables/useSkewvoirViewBeacon.ts`(신규)가
`activeKind`를 watch 하여 POST를 발신합니다.

- 선택(selection)이 존재할 때만 발신합니다. `Workspace.vue`는 선택이 없으면
  빈 상태를 렌더링하며, 빈 view는 사용이 아닙니다.
- 세션 내 `Set`으로 (view, 날짜) 중복을 제거하여 불필요한 트래픽을 막습니다.
  새로고침하면 set이 초기화되지만 서버 측 중복 제거가 최종 권위이므로
  집계 결과는 달라지지 않습니다.
- 실패는 무시합니다(fire-and-forget). 계측 실패가 분석 화면을 방해해서는
  안 됩니다.

**패널** — `pages/activity.vue`에 "Skewvoir 워크스페이스" 카드를 추가하고
`ActivityFeatureBarList`에 `skewvoir_views_7d`를 전달합니다. 기존 7d/30d
토글이 있다면 동일한 방식을 따릅니다.

**라벨** — `utils/activity.ts`의 `FEATURE_LABELS`에 6개 항목을 추가합니다.
추가하지 않으면 fallback이 "Skewvoir Dashboard"처럼 출력합니다.

| slug | 라벨 |
| --- | --- |
| `skewvoir_dashboard` | 측정 개요 |
| `skewvoir_position_stack` | 위치 비교 |
| `skewvoir_fdc` | FDC 분석 |
| `skewvoir_time_series` | Time-Series |
| `skewvoir_correlation` | 상관 / 분포 |
| `skewvoir_gallery` | 이미지 갤러리 |

### 3.7 `msr-images` 정리

같은 변경에 포함합니다.

- `feature_map.py`에 `("/api/msr-images", "skewvoir")` 별칭을 추가합니다.
  기존 slug를 개명하지 않고 별칭을 더하는 방식이므로 시계열이 갈라지지
  않습니다.
- `policy.py`의 background 판정에 `/api/msr-images` 자체를 포함시킵니다.
  warm job이 주기적으로 호출하는 기계 트래픽이므로 사람 지표에 포함되어서는
  안 됩니다.

## 4. 데이터 흐름

```text
사용자가 위치 비교 탭 클릭
  → activeKind 변경 (URL ?view=position-stack)
  → useSkewvoirViewBeacon: 세션 set 확인 → 미발신이면
    POST /api/skewvoir/view/position-stack
  → routes.py: kind 검증 → 204
  → after_request 미들웨어
      feature = "skewvoir_position_stack"
      activity_kind = "view", weight = 0
      → 로그 문서 1건 (office: OpenSearch)
      → record_request (home: daily_views set 에 추가)
  → /activity/summary 가 activity_kind="view" 집계를 읽어
    "Skewvoir 워크스페이스" 패널에 표시
```

## 5. 오류 처리

- beacon의 `kind`가 화이트리스트에 없으면 400. 400은 기존 규칙에 의해
  `operation`/weight 0이므로 오염이 발생하지 않습니다.
- `record_request` 실패는 이미 `_note_record_request_failure`로 흡수되며
  요청을 실패시키지 않습니다. 새 분기도 같은 보호를 받습니다.
- 프런트엔드 beacon 실패는 무시합니다.
- `/api/*`는 5초당 20요청으로 제한되지만, beacon은 세션 내 view당 1회이므로
  실사용에서 한계에 근접하지 않습니다.

## 6. 테스트

| 대상 | 내용 |
| --- | --- |
| `_logging/tests/test_policy.py` | beacon 경로 → `("view", 0)`; `/api/msr-images` → background; 400 beacon → `operation` |
| `_logging/tests/test_activity_middleware.py` | beacon 요청이 `feature=skewvoir_*`, `activity_kind="view"`로 로그 문서를 남기고 요청 수를 늘리지 않음 |
| `activity/tests` (contract) | `SummaryResponse`에 신규 두 필드 존재; 같은 user·view·day 반복 발신이 1로 집계; 서로 다른 날은 2로 집계 |
| `tests/test_activity_home.py` | `skewvoir` 총계·DAU·요청 수가 beacon으로 변하지 않음(회귀 방지) |
| `_logging/tests/test_activity_middleware.py` | weight 0인 beacon이 `record_request`에 **도달**함 — §3.4의 게이트 확장 회귀 방지 |
| `app/utils/activity.test.ts` | 6개 라벨이 fallback이 아닌 지정 값으로 해석됨 |

브라우저 검증은 `verify` 스킬로 수동 수행합니다. view를 순차 전환한 뒤
사용 통계 패널에 6행이 나타나는지, `msr-images` 행이 사라졌는지 확인합니다.

## 7. 문서

- `docs/datatables/skewnono_logging.txt`에 `activity_kind`의 신규 값 `view`와
  `feature`의 `skewvoir_*` slug 규약을 기재합니다.
- `back_dev_home/activity/MIGRATION.md`에 office adapter가 구현해야 할
  view 집계를 추가합니다.
- 사무실 DB에서 확인되지 않은 가정은 `OFFICE-VERIFY`로 표시합니다.

## 8. 구현 순서

1. `policy.py` + `feature_map.py`: `"view"` kind, beacon 분류, `msr-images`
   별칭·background. 테스트 선행.
2. `activity/routes.py`: beacon endpoint.
3. `contracts.py` + `providers/mock.py`: `daily_views`, summary 집계.
4. `providers/opensearch_reader.py` + `office_example.py`: 사무실 집계.
5. 프런트엔드: beacon composable, 라벨, 패널.
6. 문서 갱신, `npm run lint:md`.

여러 파일을 건드리므로 `git worktree`에서 작업한 뒤 `main`으로 ff-only
병합하고 worktree를 즉시 제거합니다.
