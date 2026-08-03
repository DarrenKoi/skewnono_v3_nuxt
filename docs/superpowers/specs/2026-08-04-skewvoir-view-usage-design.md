# Skewvoir 워크스페이스 view 사용량 계측 설계

- **작성일:** 2026-08-04
- **상태:** 승인된 설계, 구현 계획 작성 전 문서 검토 대기
- **적용 범위:** `back_dev_home/_logging`, `back_dev_home/activity`,
  `front-dev-home/app/composables`, `front-dev-home/app/pages/activity.vue`,
  `docs/datatables/skewnono_logging.txt`, `docs/api-contracts/`

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

Skewvoir의 view 전환은 **대부분** HTTP 요청을 발생시키지 않습니다.
`components/ebeam/skewvoir/Workspace.vue`는 이미 적재된 데이터 위에서 `v-if`로
view를 교체하며, `composables/useSkewvoirAnalysis.ts`의 주요 fetch는
`selection.msr`과 `activeParam`에 반응합니다.

다만 "`activeKind`에 반응하는 fetch가 전혀 없다"는 것은 사실이 아니므로 근거를
정확히 적어 둡니다. `useSkewvoirAnalysis.ts:363`의
`wantSet = computed(() => shouldLoadSet(ws.scope.value, ws.activeKind.value))`는
`activeKind`를 읽으며 `setKey`(`:407`)와 `fetchMsrFiles` watch(`:411`)로
이어집니다. 따라서 `scope=set`에서 dashboard → position-stack 전환은 실제로
`POST /api/msr-files`를 발생시킵니다.

그럼에도 기존 요청에 view를 태깅하는 방식은 성립하지 않습니다.

- `scope=single`에서는 view 전환이 어떤 요청도 만들지 않습니다.
- `scope=set`이라도 `setKey`는 dashboard 이외의 다섯 view에서 동일하므로
  position-stack → time-series → correlation 이동은 아무 요청도 만들지
  않습니다(`utils/skewvoirAnalysis/curatedSet.ts:35`).
- 선택(selection)이 바뀌는 순간 활성화되어 있던 view가 모든 사용량을 가져갑니다.

즉 기존 트래픽에 올라타는 방식은 **어떤 view가 계측되는지가 scope와 이동
순서에 의존**하게 되어, 순위가 사용량이 아니라 탐색 경로를 반영합니다.

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
  Skewvoir 전용으로 한정합니다. 다만 §9에 정리한 slug 문법 덕분에 나중에
  일반화하는 길은 막지 않습니다.
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
    if kind not in SKEWVOIR_VIEW_KINDS:
        return error_json("unknown_view", f"unknown view {kind!r}", 400)
    return "", 204
```

핸들러는 실질적인 일을 하지 않습니다. `_logging/activity.py`의
`after_request`가 이미 모든 요청에 `feature`와 `activity_kind`를 붙여
기록하므로, beacon은 그 미들웨어에 분류할 대상을 제공할 뿐입니다. 새로운
쓰기 경로도, 새로운 저장소도, 새로운 office adapter도 필요하지 않습니다.

`kind` 화이트리스트 검증은 라우트에 둡니다. 400은 `classify_activity`의 첫
가드에서 `operation`/weight 0이 되므로 임의의 slug가 색인에 유입되지 않습니다.

**경로를 `/api/skewvoir/...`에 두는 이유.** `classify_activity`
(`policy.py:51-62`)의 **첫 번째** `if`가 `_OPERATION_PREFIXES`를 포함한 모든
가드(식별자 없음, API 토큰, `OPTIONS`/`HEAD`, `status >= 400`)를 한 번에
처리하고 즉시 반환합니다.

- `/api/activity/view/<kind>`에 두면 `/api/activity`가 operation prefix이므로,
  view 분기를 **가드보다 앞에** 놓아야 합니다. 그러면 익명 요청이나 400
  응답까지 `view`로 분류되어 §5가 의존하는 "400 → operation" 성질이 깨집니다.
- `/api/skewvoir/...`는 어떤 operation prefix에도 걸리지 않으므로, view 분기를
  기존 `_BACKGROUND_EXACT` 검사 **옆**(가드 통과 후)에 자연스럽게 놓을 수
  있습니다.

즉 이 선택은 예외 규칙을 피하려는 것이 아니라 — 어느 쪽이든 `policy.py`에
분기 하나는 추가됩니다 — **그 분기가 가드 뒤에 오도록** 하기 위한 것입니다.

**감수하는 비용:** `/api/skewvoir/*`는 `back_dev_home/` 아래에 대응 폴더가 없는
최상위 API namespace가 되며, feature-sliced 레이아웃과 어긋나 보입니다. 다만
폴더와 경로 namespace가 다른 사례는 이미 있습니다(`api_tokens` →
`/account/api-tokens`, `access_control` → `/admin/access`). 또한 경로 문자열이
`activity/routes.py`·`policy.py`·`feature_map.py` 세 곳에 나타나므로, §6의
테스트가 정확한 경로를 고정해야 합니다. 그렇지 않으면 "activity blueprint가
소유하니 `/api/activity` 아래로 옮기자"는 정리 작업이 기능 전체를 조용히
weight 0으로 만듭니다.

### 3.2 새 `activity_kind` 값 `"view"`

`_logging/policy.py`의 `ActivityKind` Literal에 `"view"`를 추가하고,
`classify_activity`가 beacon 경로를 `ActivityDecision("view", 0)`로 분류합니다.

**정확히 무엇을 사는가.** 기존 질의로부터의 격리는 사실 `weight = 0`만으로도
달성됩니다. `_activity_filters()`(`opensearch_reader.py:38-46`)는
`activity_weight: 1`과 `activity_kind in ["entry","feature"]`를 **둘 다**
걸기 때문에, 어느 한쪽만으로도 view 문서는 제외됩니다. 따라서 새 kind는
격리 장치가 아니라 **색인 가독성**을 위한 선택입니다. beacon 문서가
`operation`(운영 잡음)이 아니라 `view`(의도된 계측)로 스스로를 설명하고,
`/admin-logs`에서 필터 한 줄로 분리됩니다.

**그 대가:** `ActivityKind` Literal 확장, `docs/datatables` 신규 값 문서화,
`docs/api-contracts/usage-events.yaml`의 enum 갱신, office 질의의 필터 한 줄.
격리가 아니라 가독성을 위해 이 네 곳을 지불한다는 점을 명시해 둡니다.

### 3.3 기록 대상 kind의 단일 정의

"어떤 kind가 사용량 저장소에 기록되는가"는 현재 세 곳에 흩어져 있습니다.

| 위치 | 현재 표현 |
| --- | --- |
| `policy.py:67-69` | `entry`/`feature`에만 weight 1 부여 |
| `_logging/activity.py:179` | `if extra["activity_weight"] == 1` |
| `activity/providers/mock.py:147` | `if activity_kind not in {"entry","feature"}` |

즉 오늘의 `weight == 1` 게이트는 이미 `kind in {"entry","feature"}`의 우회
표현입니다. 여기에 `or kind == "view"`를 덧붙이면 하나의 집합을 숫자 대리값과
문자열 특례의 논리합으로 적게 되고, 세 곳이 서로 어긋나면 **테스트 실패 없이
데이터가 사라집니다.**

집합을 `policy.py`에 한 번만 정의하고 두 소비자가 import 합니다.

```python
# policy.py
RECORDED_KINDS: frozenset[ActivityKind] = frozenset({"entry", "feature", "view"})
```

- `_logging/activity.py:179` → `if extra["activity_kind"] in RECORDED_KINDS:`
- `activity/providers/mock.py:147` → 같은 상수로 판정

weight를 1로 올려 게이트를 통과시키는 대안은 채택하지 않습니다. weight는
"사람의 가중 요청 1건"을 뜻하고, `opensearch_reader.py:41`의
`{"term": {"activity_weight": 1}}`과 `activity/tests/test_office_template.py:95`의
계약 테스트가 그 의미에 의존하기 때문입니다.

### 3.4 slug 문법과 단일 출처

view 값은 별도 필드가 아니라 **기능 slug 안에** 인코딩하되, **콜론**을
구분자로 씁니다.

| view kind | slug |
| --- | --- |
| `dashboard` | `skewvoir:dashboard` |
| `position-stack` | `skewvoir:position-stack` |
| `fdc` | `skewvoir:fdc` |
| `time-series` | `skewvoir:time-series` |
| `correlation` | `skewvoir:correlation` |
| `gallery` | `skewvoir:gallery` |

**밑줄이 아니라 콜론인 이유.** 기존 페이지 slug는 이미 밑줄을 포함합니다
(`device_statistics`, `recipe_search`, `meas_hist`, `admin_logs` …). 따라서
`skewvoir_dashboard`는 페이지 slug와 문자 단위로 구별되지 않으며, "페이지"와
"페이지+view"를 나누는 것은 오직 `activity_kind` 필터뿐입니다. 그 필터를 빼고
`terms(feature)`를 도는 질의 하나가 두 문법을 되돌릴 수 없이 섞습니다.
`/admin-logs`는 이미 자유 입력 `feature` 필터를 노출합니다
(`admin_logs/query.py:128`).

`feature_map.py:8-9`가 기록된 slug의 개명을 금지하므로 이 문법은 365일 색인에
첫 문서가 들어가는 순간 영구히 고정됩니다. 콜론은 지금은 한 글자 비용이지만,
나중에 진짜 `sub_view` 필드로 옮길 때 모든 문서를 기계적으로 분해할 수 있게
해 줍니다.

**단일 출처.** slug 목록은 `_logging/feature_map.py`가 소유합니다. 이 모듈은
"무엇이 개별 기능인지 결정하는 유일한 장소"라고 스스로 선언하고 있으며, 다른
모듈을 import 하지 않는 leaf 모듈입니다(`_logging/__init__.py`는 비어 있으므로
`activity/providers`에서 import 해도 순환이 생기지 않습니다).

```python
# feature_map.py
SKEWVOIR_VIEW_KINDS = (
    "dashboard", "position-stack", "fdc",
    "time-series", "correlation", "gallery",
)
SKEWVOIR_VIEW_SLUGS = {kind: f"skewvoir:{kind}" for kind in SKEWVOIR_VIEW_KINDS}

_FEATURE_RULES = (
    tuple(
        (f"/api/skewvoir/view/{kind}", slug)
        for kind, slug in SKEWVOIR_VIEW_SLUGS.items()
    )
    + ...  # 기존 규칙
)
```

**이 규칙 생성이 빠지면 설계가 조용히 작동하지 않습니다.** `_FEATURE_RULES`는
정적 prefix 매칭이고 fallback은 첫 경로 segment를 돌려주므로,
`/api/skewvoir/view/position-stack`은 규칙 없이는 slug `skewvoir`로 붕괴하여
여섯 view가 한 행으로 합쳐집니다. 응답은 204이고 오류도 없습니다.

`routes.py`의 화이트리스트는 `SKEWVOIR_VIEW_KINDS`를 import 하므로, 파이썬
쪽 열거는 한 곳뿐입니다.

`_KNOWN_EXTRA_KEYS`(`_logging/opensearch_handler.py`)와 색인 매핑은 변경하지
않습니다. 추가되는 것은 기존 키의 새로운 **값**이지 새로운 키가 아니기
때문입니다. 이는 중요한 제약을 회피합니다.
`ops_index_mgmt/skewnono_logging.py`는 `flask_modules`에서 복사된 vendored
파일이며 `"dynamic": "false"`가 설정되어 있어, 새 필드는 매핑을 고치지 않는 한
집계 불가능한 채로 `_source`에만 남습니다.

### 3.5 집계: user × view × day 중복 제거

한 사람이 같은 날 같은 view를 몇 번 오가든 1로 집계합니다.

**미들웨어 게이트 (`_logging/activity.py`)**

§3.3의 `RECORDED_KINDS` 판정으로 교체합니다. `"view"`는 weight 0이므로 현재의
`activity_weight == 1` 조건으로는 `record_request`에 **도달하지 못하고 home
데이터가 전부 조용히 유실됩니다.**

office adapter의 `record_request`는 의도된 no-op이므로
(`activity/providers/office_example.py:16-19`), 이 게이트 확장이 실제로 구하는
것은 **home mock 데이터뿐**입니다. 공유 미들웨어를 건드리는 변경치고 위험은
home에 한정된다는 뜻입니다.

**Home (`activity/providers/mock.py`)**

`_UserState`에 `daily_views: dict[date, set[str]]`를 추가합니다. 같은 파일에
이미 있는 `daily_fabs` 패턴을 그대로 따릅니다.

`record_request`는 `activity_kind == "view"`일 때 `state.daily`(요청 수)·
`last_seen`·FAB 버킷을 갱신하기 **전에** 분기하여 `daily_views`만 갱신하고
반환합니다. 그렇지 않으면 weight 0이라는 결정이 mock 안에서 무효화됩니다.

단, `_prune_old_days`는 현재 그 갱신들 **뒤**(`mock.py:166`)에서 호출되므로,
조기 반환하는 view 분기 안에서도 `_prune_old_days(state, today)`를 직접
호출해야 합니다. 그러지 않으면 `daily_views`의 유계성이 "이 사용자가 다른
weight 1 요청도 보낸다"는 우연에 의존하게 됩니다.

읽기 측 합산은 `get_summary`가 이미 `_users`를 한 번 순회하며 두 창을 계산하는
루프(`mock.py:227-245`) 안에 접습니다. 두 번째 전체 스캔이나 창 경계 재계산은
만들지 않습니다. dict → 순위 `list[FeatureCount]` 변환은 기존
`_top_features()`(`mock.py:73-78`)를 재사용하여 `(-count, feature)` 정렬을
다른 패널과 일치시킵니다.

**Office (`activity/providers/opensearch_reader.py`)**

view 집계는 `get_summary`의 기존 질의에 **하위 집계로 붙일 수 없습니다.**
`_activity_filters()`가 최상위 `query`로 쓰이며(`:315`) `activity_weight: 1`과
`activity_kind` 화이트리스트를 걸기 때문에, 집계는 부모 질의를 넓힐 수
없습니다. 이 사실을 놓치면 **office는 빈 결과를 돌려주는데 mock 테스트는 전부
통과하는** 상태가 됩니다.

따라서 `get_summary`는 두 번째 `_search`를 발행합니다.

```text
query:  activity_kind == "view" AND @timestamp >= now-30d
aggs:   terms(feature)                     # 최대 6 버킷
          -> date_histogram(day, KST)      # 30 버킷
               -> cardinality(user_id, precision_threshold=1000)
```

- **창 두 개를 한 집계로 얻습니다.** 정의상 7일 값은 30일 histogram의 마지막
  7개 버킷 합이므로, 별도 7일 집계를 만들지 않고 Python에서 잘라 씁니다
  (180 버킷, 별도 집계 시 222 버킷).
- **`precision_threshold`는 1000을 씁니다.** 기존
  `CARDINALITY_PRECISION = 40000`(`:25`)은 fleet 전체 DAU/WAU/MAU용입니다.
  (view, 일) 버킷 하나의 distinct `user_id`는 DAU를 넘을 수 없으므로 1000이면
  사실상 정확하며, 40000을 180개 버킷에 그대로 물려주는 것은 질의 heap
  낭비입니다.

기존 질의를 넓히는 대신 두 번째 검색을 택한 이유는, `_activity_filters()`가
`_history_query`·`get_users_list`·`_fab_window`에서도 쓰이는 공유 함수라
그것을 손대면 영향 범위가 요약 밖으로 번지기 때문입니다. round trip 하나의
비용은 명시적으로 감수합니다.

### 3.6 계약(contract) 변경

`activity/contracts.py`에 전용 타입을 추가하고 `SummaryResponse`를 넓힙니다.

```python
class ViewUsageCount(TypedDict):
    feature: str   # "skewvoir:dashboard"
    count: int     # 중복 제거된 user-day 수

class SummaryResponse(TypedDict):
    ...
    skewvoir_views_7d: list[ViewUsageCount]
    skewvoir_views_30d: list[ViewUsageCount]
```

`FeatureCount`를 그대로 재사용하지 않는 이유는 단위가 다르기 때문입니다.
`docs/api-contracts/activity.yaml:41-44`는 `FeatureCount.count`를 "해당 기간의
feature request 문서 수"로 정의합니다. view 값은 중복 제거된 user-day이며
자릿수가 한두 자리로 작습니다. 필드 구조가 동일하므로 TypeScript에서는
`ActivityFeatureBarList.vue`에 **수정 없이** 전달할 수 있고, 타입만 분리됩니다.
패널에는 "명·일" 단위 표기를 함께 둡니다. `FeatureBarList`는 막대 폭을
리스트별로 정규화하므로, 단위 표기가 없으면 요청 수 패널과 나란히 놓였을 때
두 숫자가 비교 가능한 것처럼 보입니다.

`/api/activity/summary`는 식별된 모든 사용자에게 열려 있으므로(`routes.py`에서
`@require_admin`은 `/users*`에만 적용) 신규 엔드포인트가 필요하지 않습니다.

### 3.7 프런트엔드

**Beacon 발신** — `composables/useSkewvoirViewBeacon.ts`(신규)가 `activeKind`를
watch 하여 POST를 발신합니다.

- 선택(selection)이 존재할 때만 발신합니다. `Workspace.vue`는 선택이 없으면
  빈 상태를 렌더링하며, 빈 view는 사용이 아닙니다.
- URL은 `utils/apiPath.ts`의 `joinApiPath`로 만듭니다. 27개 composable이 이미
  이를 쓰며, 맨 경로를 쓰면 `config.public.apiBase`가 비어 있지 않은 배포에서
  깨집니다.
- **중복 제거 상태는 모듈 레벨**에 둡니다. 검색 랜딩과 분석 화면은 서로 다른
  라우트이므로 composable 스코프에 두면 검색으로 돌아갈 때마다 초기화되어,
  하루 6건이면 될 트래픽이 오가는 횟수만큼 배가됩니다.
  `useMsrFileApi.ts:145`의 모듈 레벨 `inFlight`와 같은 방식입니다.
  자료구조는 `Map<kind, dateString>`으로 두어 자정을 넘겨도 재발신됩니다.
- watch 콜백에서 즉시 쏘지 않고 다음 idle에 미룹니다. beacon은 선택 변경과 같은
  tick에 발생할 수 있고, `/api/*`는 사용자당 **전역** 20요청/5초를
  공유하므로(`back_dev_home/__init__.py:72-78`) 같은 순간의 `msr-file` 요청이
  429를 맞으면 `useMsrFileApi.ts:180`의 700 ms 백오프가 view 전환을 눈에 띄게
  느리게 만듭니다.
- 실패는 무시합니다(fire-and-forget).

**패널** — `pages/activity.vue`에 "Skewvoir 워크스페이스" 카드를 추가하고,
`fabWindowKey`와 같은 방식으로 자체 `viewWindowKey` ref를 두되 공유
`windowTabs` 배열(`activity.vue:666-669`)을 재사용합니다. 기존 `windowKey`를
그대로 쓰면 무관한 두 패널이 결합됩니다.

**라벨** — `utils/activity.ts`의 여섯 라벨은 손으로 적지 않고
`SKEWVOIR_VIEW_MODES`(`useSkewvoirWorkspace.ts:36`)에서 파생합니다. 그 상수의
`label` 값이 이미 측정 개요·위치 비교·… 와 **바이트 단위로 동일**하므로,
복사하면 좌측 rail 이름을 바꾸는 순간 통계 페이지가 UI와 어긋나고 §8의 테스트는
복사본을 검증하므로 통과합니다.

```ts
const SKEWVOIR_VIEW_LABELS = Object.fromEntries(
  SKEWVOIR_VIEW_MODES.map(m => [`skewvoir:${m.kind}`, m.label])
)
```

`activityFeatureLabel`의 fallback은 `_`로만 분해하므로, 라벨 조회에 실패한
`skewvoir:*` 값이 그대로 노출되지 않도록 fallback도 콜론을 인식하게 합니다.

### 3.8 `msr-images` 정리

같은 변경에 포함합니다.

- `feature_map.py`에 `("/api/msr-images", "skewvoir")` 별칭을 추가합니다.
  이 별칭은 지표를 위한 것이 아닙니다 — 아래 background 처리만으로도 모든
  순위에서 빠지기 때문입니다. 별칭의 실제 이득은 `/admin-logs`와 원시 로그
  조회에서 쓰레기 slug 대신 `skewvoir`가 보이는 것입니다. 기존 slug를 개명하지
  않고 별칭을 더하는 방식이므로 시계열이 갈라지지 않습니다.
- `policy.py`의 background 판정에 `/api/msr-images` 자체를 포함시킵니다.
  이때 `_BACKGROUND_CHILD_PREFIXES`(`:26`)와 그에 딸린 두 번째 분기(`:63-65`)는
  **삭제합니다.** 그 구조는 부모를 제외하고 자식만 잡기 위해 존재했는데, 부모도
  background가 되면 존재 이유가 사라집니다. 이미 있는 `_at_or_below()`(`:38`)로
  한 튜플에서 판정합니다. `/api/msr-image`(단수)는 복수형을 삼키지 않도록
  exact 판정에 남깁니다.
- 이 변경은 warm job의 `POST`뿐 아니라 사람이 갤러리를 열 때의
  `GET /api/msr-images`(`msr_image/routes.py:49`)도 함께 weight 0으로
  내립니다. 갤러리 사용량은 이제 `skewvoir:gallery` beacon이 추적하므로
  의도된 결과입니다.

## 4. 데이터 흐름

```text
사용자가 위치 비교 탭 클릭
  → activeKind 변경 (URL ?view=position-stack)
  → useSkewvoirViewBeacon: 모듈 레벨 Map 확인 → 오늘 미발신이면 idle 시점에
    POST /api/skewvoir/view/position-stack
  → routes.py: kind 화이트리스트 검증 → 204
  → after_request 미들웨어
      feature = "skewvoir:position-stack"   (feature_map 규칙)
      activity_kind = "view", weight = 0
      → 로그 문서 1건 (office: OpenSearch)
      → RECORDED_KINDS 게이트 통과 → record_request
        (home: daily_views set 갱신 + prune / office: no-op)
  → /activity/summary 가 두 번째 _search 로 view 집계를 읽어
    "Skewvoir 워크스페이스" 패널에 표시
```

## 5. 오류 처리

- beacon의 `kind`가 화이트리스트에 없으면 400. 400은 `classify_activity`의 첫
  가드에서 `operation`/weight 0이 되므로 색인 오염이 없습니다.
- **두 번째 `_search` 실패는 요약 전체를 실패시키지 않습니다.** view 집계가
  실패하면 `skewvoir_views_*`를 빈 리스트로 두고 나머지 요약을 반환하며,
  `routes.py`의 기존 `_query` 래퍼가 잡는 503은 첫 번째 검색 실패에만
  적용됩니다. 계측 패널 하나 때문에 DAU·기능 순위가 사라져서는 안 됩니다.
- `record_request` 실패는 이미 `_note_record_request_failure`로 흡수되며 요청을
  실패시키지 않습니다. 새 분기도 같은 보호를 받습니다.
- 프런트엔드 beacon 실패는 무시합니다.

## 6. 테스트

| 대상 | 내용 |
| --- | --- |
| `_logging/tests/test_policy.py` | beacon 경로 → `("view", 0)`; 400 beacon → `operation`; `/api/msr-images` → background; `RECORDED_KINDS`가 weight 1인 모든 kind를 포함 |
| `_logging/tests/test_feature_map.py` | 여섯 경로가 각각 `skewvoir:<kind>`로 해석됨 — 규칙 누락 시 `skewvoir`로 붕괴하는 것을 잡는 유일한 방어선 |
| `_logging/tests/test_activity_middleware.py` | beacon이 정확한 경로에서 `feature=skewvoir:*`·`kind="view"`로 로그되고 weight 0임에도 `record_request`에 **도달**함(§3.5 게이트 회귀 방지). 기존 `test_only_weighted_requests_become_usage_events`(`:194`)는 이름과 의도가 더 이상 맞지 않으므로 함께 개명 |
| `activity/tests` (contract) | `SummaryResponse` 신규 두 필드; 같은 user·view·day 반복은 1, 다른 날은 2; 7일 값이 30일 마지막 7버킷 합과 일치 |
| `tests/test_activity_home.py` | `skewvoir` 총계·DAU·요청 수가 beacon으로 변하지 않음; `daily_views`가 view 요청만으로도 prune 됨 |
| `app/utils/activity.test.ts` | 여섯 라벨이 `SKEWVOIR_VIEW_MODES`에서 파생됨(rail 라벨을 바꾸면 함께 바뀜) |

브라우저 검증은 `verify` 스킬로 수동 수행합니다. view를 순차 전환한 뒤 사용
통계 패널에 여섯 행이 나타나는지, `msr-images` 행이 사라졌는지 확인합니다.

## 7. 문서

- `docs/datatables/skewnono_logging.txt`: `activity_kind`의 신규 값 `view`,
  `feature`의 `skewvoir:<kind>` 문법. **그리고 `activity_weight`의 정의 수정** —
  현재 "활동 집계 대상이면 1"이라고 적혀 있으나, 이 변경 이후 weight 0 문서도
  집계 대상입니다. "요청량 지표 가중치"로 다시 씁니다. 이 문장을 고치지 않으면
  다음 사람이 `activity_weight=1`을 "집계되는 전부"로 읽고 view를 빠뜨립니다.
- `docs/api-contracts/usage-events.yaml`: `activity_kind` enum에 `view` 추가,
  `activity_weight` 설명 수정.
- `docs/api-contracts/activity.yaml`: `SummaryResponse` 신규 두 필드,
  `ViewUsageCount` 타입, `activity_filter` 설명 수정. beacon은 `base_path:
  /api/activity` 밖이므로 별도 절이나 주석으로 위치를 명시합니다.
- `back_dev_home/activity/MIGRATION.md`: office adapter가 구현해야 할 두 번째
  검색과 그 실패 정책.
- 사무실 DB에서 확인되지 않은 가정은 `OFFICE-VERIFY`로 표시합니다.

## 8. 구현 순서

1. `policy.py` + `feature_map.py`: `RECORDED_KINDS`, `"view"` kind, beacon 분류,
   slug 상수·규칙 생성, `msr-images` 별칭·background·`_at_or_below` 정리.
   테스트 선행.
2. `_logging/activity.py`: 게이트를 `RECORDED_KINDS`로 교체.
3. `activity/routes.py`: beacon endpoint.
4. `contracts.py` + `providers/mock.py`: `daily_views`, prune, `get_summary`
   루프 내 합산.
5. `providers/opensearch_reader.py`: 두 번째 검색과 창 분할.
   `office_example.py`는 `_reader.get_summary` 재수출이므로 **변경 불필요**.
6. 프런트엔드: beacon composable, 파생 라벨, 패널.
7. 문서 갱신, `npm run lint:md`.

여러 파일을 건드리므로 `git worktree`에서 작업한 뒤 `main`으로 ff-only 병합하고
worktree를 즉시 제거합니다.

## 9. 고려했으나 채택하지 않은 대안

| 대안 | 기각 이유 |
| --- | --- |
| 기존 Skewvoir 요청에 `?view=` 를 붙이고 `promote_request_fab_names`와 같은 경로로 승격 | §1.1 — view 전환이 요청을 만들지 않거나(`scope=single`), `setKey`가 같아 재요청이 없는 구간이 있어 계측이 이동 순서에 의존하게 됩니다. 새 엔드포인트가 없다는 이점보다 왜곡이 큽니다. |
| 새 `skewvoir_view` 로그 필드 | vendored `ops_index_mgmt/skewnono_logging.py`(`"dynamic": "false"`)와 `_KNOWN_EXTRA_KEYS`를 함께 고쳐야 하며, 사무실에서만 닿는 저장소와의 조율과 `PUT _mapping`이 필요합니다. |
| `feature`는 `skewvoir`로 두고 `terms(path)`로 집계 | 새 slug가 전혀 필요 없고 향후 beacon에 일반화되지만, home mock이 path를 알아야 하므로 swap surface인 `record_request(user_id, feature, activity_kind, fab_name_list)` 시그니처를 바꿔야 합니다(`data.py`·`mock.py`·`office_example.py`). 이번 범위에는 과합니다. |
| beacon 문서에 결정적 `_id`(`view:{user}:{feature}:{day}`)를 부여해 색인 단계에서 중복 제거 | 읽기에서 `cardinality`가 사라지고 색인 증가가 구조적으로 상한을 갖는 매력적인 방안이지만, 범용 로깅 핸들러(`opensearch_handler.py:278-305`)가 중복 제거를 알게 되는 것은 계층 위반입니다. §3.7의 모듈 레벨 중복 제거로 발신이 사용자당 하루 6건 이하가 되므로 색인 증가는 문제가 아닙니다. |
| beacon을 rate limiter에서 면제(`msr_image` 선례) | 면제된 POST가 색인에 문서를 무제한 쓸 수 있게 됩니다. idle 지연 발신 + 하루 6건 상한으로 충돌을 피하는 편이 안전합니다. |
| 범용 sub-view 차원 | 사용자가 Skewvoir 한정을 선택했습니다. §3.4의 콜론 문법이 나중의 일반화를 막지 않습니다(예: `skewvoir:time-series`의 3값 하위 lens `?tsview=`). |
