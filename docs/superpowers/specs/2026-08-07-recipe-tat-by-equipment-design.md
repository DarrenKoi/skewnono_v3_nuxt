# Recipe TAT 장비별 뷰 — 설계

- 작성일: 2026-08-07
- 상태: 설계 확정, 구현 전
- 범위: Recipe TAT 화면에 `디바이스별` 옆으로 `장비별`(eqp_id 기준) 뷰를
  추가하고, 장비 간 비교와 관리 소홀 장비 탐지를 지원합니다. 여기에
  필요한 mock 장비 플릿 정합성 수정을 함께 포함합니다.

## 1. 배경

Recipe TAT은 오늘 두 가지 시점만 제공합니다.

- `전체 요약` — 선택된 fab 합집합에서 레시피별 TAT 랭킹
- `디바이스별` — lot_cd 하나를 골라 같은 대시보드를 그 디바이스로 재조회

두 시점 모두 **레시피가 주어**입니다. 현업이 필요로 하는 나머지 축, 즉
"어느 **장비**가 얼마나 일하고 있는가"는 볼 방법이 없습니다. 구체적으로
답이 필요한 질문은 세 가지입니다.

1. 이 장비는 어떤 레시피를 도는가
2. 어느 장비에 측정이 몰려 있고, 어느 장비가 놀고 있는가
3. 같은 일을 하는데 유독 오래 걸리는 장비가 있는가

측정 이력(`meas_hist`)에는 이미 `eqp_id`가 실려 있고, office OpenSearch 문서도
`eqp_id`를 갖고 있습니다(`docs/datatables/meas_hist.txt`). 지금은 랭킹 행의
`sample_eqp_ids` 예시 목록으로만 쓰이고 있어서, 새 집계 축을 추가하는 일이지
새 데이터를 구하는 일이 아닙니다.

## 2. 결정 요약

| 항목 | 결정 | 근거 |
| --- | --- | --- |
| 비교 방식 | 선택 없이 **전 장비 플릿 표**를 먼저 보여주고, 거기서 최대 5대를 체크하면 트렌드가 겹쳐 그려지고 레시피 구성이 장비별 열로 나뉩니다. | "무거운 장비 / 방치된 장비"를 한눈에 보는 것이 1순위이고, 비교는 그 표에서 의심 장비를 고른 뒤의 후속 동작입니다(user-confirmed 2026-08-07). |
| 방치 신호 | 저사용 · 느림 · 레시피 편중 세 가지 (user-confirmed 2026-08-07). | |
| 측정 0건 장비 | **표에 넣지 않습니다.** | sem_list 명부 조인이 필요해 office 어댑터에 Redis 의존이 추가됩니다. 이번 범위 밖(user-confirmed 2026-08-07). |
| 느림 지표 | 단순 평균 TAT이 아니라 **레시피 구성으로 정규화한 지수**(`tat_index`). | 3절 참고. 단순 평균은 장비 상태가 아니라 레시피 구성 차이를 재는 지표입니다. |
| 사용량 기준 | 실행 **횟수**가 아니라 **측정 점유 시간**. | 가동률은 "얼마나 바빴는가"이지 "몇 번 돌았는가"가 아닙니다. 긴 레시피를 도는 장비는 실행 횟수가 적어도 놀고 있지 않습니다(user-confirmed 2026-08-07). |
| API | 새 엔드포인트 2개. 기존 4개(`ranking`/`summary`/`daily-trend`/`devices`)는 **손대지 않습니다.** | 4절 참고. |
| 임계값 위치 | 비율·**분위수** 계산은 백엔드, 배지 판정은 프론트엔드 한 파일. | 3.5절. 실 분포를 집에서 볼 수 없으므로 임계값을 한 곳에 모으고 분위수를 함께 내려보내 사무실에서 한 번에 조정합니다. |
| 임계값 상태 | 전부 **OFFICE-VERIFY** — 집에서 정한 숫자는 자리표시자입니다. | 실 플릿은 가동률이 대부분 90% 이상으로 촘촘히 몰려 있어서 85%만 되어도 이상 신호일 수 있습니다(user-confirmed 2026-08-07). mock으로는 이 폭을 알 수 없습니다. |
| mock 장비 플릿 | **전면 수정.** sem_list를 장비 명부로 삼고, 생성 순서를 장비→lot으로 뒤집습니다. | 6절 참고. 현재 mock은 문서화된 규칙을 어기고 있고, 그대로 두면 느림 신호를 집에서 검증할 수 없습니다(user-confirmed 2026-08-07). |
| 컴포넌트 배치 | `RecipeTatView.vue`의 기존 본문은 **건드리지 않고** 모드 분기만 추가. 장비별은 새 컴포넌트 3개. | 이미 729줄이라 여기에 얹으면 1100줄이 됩니다. 동작 중인 두 뷰의 회귀 위험을 0으로 둡니다. |

## 3. 지표 정의

### 3.1 `tat_index` — 레시피 구성으로 정규화한 소요 시간

장비를 `avg_meastime`으로 줄세우면 **반드시 틀립니다.** QC만 도는 장비는
저절로 "빠른 장비"가 되고 ADI를 많이 도는 장비는 "느린 장비"가 됩니다.
장비 상태가 아니라 일감의 종류를 잰 것입니다.

역학의 간접표준화와 같은 방식으로 풉니다. 조회 범위(tool_type + fab + 기간)
안에서:

```text
base(r)  = 레시피 r의 플릿 평균 meastime
           = Σ_t total_meastime(t, r) / Σ_t meas_counts(t, r)

expected(t) = Σ_r  meas_counts(t, r) × base(r)      # 이 장비의 일감이면 이만큼 걸려야 함
actual(t)   = Σ_r  total_meastime(t, r)             # 실제로 이만큼 걸렸음

tat_index(t) = actual(t) / expected(t)
```

읽는 법: `1.00` = 플릿 평균 수준, `1.25` = **같은 일**을 25% 더 오래 함.

성질 두 가지를 명시해 둡니다.

- **표본 하한.** `meas_counts(t) < TAT_INDEX_MIN_SAMPLE`(기본 12, OFFICE-VERIFY)이면
  `tat_index`는 `null`입니다. 3건짜리 장비의 지수는 신호가 아니라 잡음이고,
  잡음에 경고 배지를 다는 순간 화면 전체의 신뢰가 무너집니다. 프론트엔드는
  `null`을 `—`로 렌더링하고 배지를 달지 않습니다.
- **단일 장비 전용 레시피는 보수적으로 작동합니다.** 어떤 레시피를 장비
  한 대만 돌았다면 `base(r)`가 그 장비의 평균과 같아져 그 항은 정확히 1.0을
  기여합니다. 즉 비교 정보가 없는 일감은 지수를 1.0 쪽으로 희석시킬 뿐,
  없는 경보를 만들어내지 않습니다. 의도된 성질입니다.

### 3.2 나머지 신호

| 지표 | 정의 | 의미 |
| --- | --- | --- |
| `occupancy` | `total_meastime ÷ 조회 기간 총 초` | 절대값. 0.62 = 기간의 62%를 측정에 씀 |
| `usage_ratio` | `total_meastime ÷ 플릿 중앙값 total_meastime` | 상대값. 0.8 = 또래의 80%만 바빴음 |
| `recipe_count` | 이 장비가 돈 distinct `full_name` 수 | 커버리지 |
| `top_recipe_share` | 1위 레시피의 TAT ÷ 이 장비 총 TAT | 편중도 |

**실행 횟수가 아니라 측정 시간이 기준입니다.** 가동률은 "얼마나 바빴는가"이지
"몇 번 돌았는가"가 아닙니다. ADI 같은 긴 레시피를 도는 장비는 실행 횟수가
적어도 놀고 있지 않습니다. `exec_count`는 표에 계속 표시하되 신호 판정에는
쓰지 않습니다.

**`occupancy`가 무엇이 아닌지 명확히 해둡니다.** 이 값은 `meas_hist`의
`meastime` 합에서 나오므로 **측정 점유율**이지 MES가 보고하는 장비 가동률이
아닙니다. 로딩·언로딩·대기·PM이 빠져 있어서 실제 가동률보다 낮게 읽힙니다.
두 숫자를 같은 것으로 보고 임계값을 옮겨오면 안 됩니다 — 3.5절의 사무실
확인 절차가 이 때문에 필요합니다.

`occupancy`(절대)와 `usage_ratio`(상대)를 **둘 다** 내려보냅니다. 상대값만
있으면 플릿 전체가 놀고 있어도 "다들 정상"이라고 말하고, 절대값만 있으면
측정 점유율과 실 가동률의 격차만큼 통째로 어긋납니다. 어느 쪽이 신호를
싣고 있는지는 사무실 데이터를 봐야 압니다.

또래 집단(peer group)은 **조회 범위 그 자체**입니다 — 사용자가 이미
사이드바에서 fab을, 탭에서 tool_type을 골랐으므로 그 안의 장비들이 곧
비교 대상입니다. 모델별·fab별로 더 잘게 나누지 않습니다: 하위 집단이
2~3대까지 작아지면 중앙값이 통계가 아니라 우연이 됩니다.

### 3.3 빈 범위 처리

조회 범위에 측정이 하나도 없으면 `equipments`는 빈 목록, `fleet`의 모든
수치는 0, `percentiles`는 빈 dict입니다. `usage_ratio`는 중앙값이 0일 때
0.0으로 둡니다(목록에 오른 장비는 `total_meastime`이 1 이상이라 실제로는
도달하지 않는 경로지만, 0으로 나누지 않도록 명시적으로 막습니다).
`occupancy`는 `window_seconds`가 0이면 0.0입니다.

프론트엔드는 기존 `전체 요약` 뷰와 같은 "측정 없음" 빈 상태를 재사용하고,
`percentiles`가 비어 있으면 배지를 하나도 달지 않습니다 — 3.4절의 판정이
분위수를 AND 조건으로 요구하므로 이건 자동으로 성립하지만, 테스트로
고정해 둡니다.

### 3.4 배지 판정 — 분위수 ∧ 절대 임계값

집에서는 실 플릿의 분포 폭을 알 수 없습니다. 현업 확인에 따르면 장비 가동률은
대부분 90% 이상으로 촘촘히 몰려 있어서 **85%만 되어도 이상 신호**일 수
있습니다. 즉 mock을 보고 고른 절대 임계값은 거의 확실히 틀립니다.

절대 임계값 하나에만 기대지도, 분위수 하나에만 기대지도 않습니다.

- 절대 임계값만 쓰면 → 상수가 실 분포와 어긋나는 순간 전부 정상이거나
  전부 경고가 됩니다.
- 분위수만 쓰면 → 플릿이 완전히 건강해도 **항상 하위 10%를 경고**합니다.
  "제일 낮은 장비"와 "문제 있는 장비"는 다릅니다.

그래서 **둘을 AND로 묶습니다.** 꼬리에 있으면서 동시에 절대 기준을 넘긴
장비만 배지를 답니다. 분위수가 잘못된 상수를 막아주고, 절대 기준이 건강한
플릿에서의 헛경보를 막아줍니다.

`front-dev-home/app/utils/equipmentSignals.ts` 순수 함수 + 단위 테스트.

| 배지 | 조건 |
| --- | --- |
| `저사용` | `usage_ratio <= fleet.percentiles.usage_ratio.p10` **AND** `usage_ratio < USAGE_FLOOR` |
| `느림` | `tat_index !== null` **AND** `tat_index >= …tat_index.p90` **AND** `tat_index > TAT_CEIL` |
| `빠름` | `tat_index !== null && tat_index <= …tat_index.p10 && tat_index < TAT_FLOOR` (중립 표시) |
| `편중` | `recipe_count <= …recipe_count.p10` **AND** `top_recipe_share >= SHARE_CEIL` |

절대 상수의 **초기값은 자리표시자입니다.** 전부 `OFFICE-VERIFY`로 표시하고
한 파일에 모아둡니다.

```ts
// OFFICE-VERIFY — 사무실 실 분포 확인 전까지는 전부 자리표시자입니다.
// 조정 절차는 3.5절. 값이 확정되면 이 주석을 `office 확인 YYYY-MM-DD`로 바꿉니다.
export const USAGE_FLOOR = 0.85   // 플릿이 촘촘하다는 현업 확인 반영 (0.35 → 0.85)
export const TAT_CEIL    = 1.10
export const TAT_FLOOR   = 0.92
export const SHARE_CEIL  = 0.50
```

배지가 잘못 조정되어 있어도 **표는 항상 원 수치를 보여줍니다.** 배지는
눈길을 유도하는 장치일 뿐이고, 판단 근거는 열에 그대로 남습니다.

### 3.5 사무실 확인 절차 (OFFICE-VERIFY)

> **정정 (구현 후 추가).** 아래 절차의 1번(fab 없이 호출)과 4번(상수 네 개를
> 한꺼번에 도장)은 구현 과정에서 틀린 것으로 드러났습니다. fab을 섞어 조회하면
> 배지가 장비가 아니라 fab을 줄세우고, `TAT_CEIL`은 분위수만으로 검증되지
> 않습니다. **사무실에서는 이 문서가 아니라
> `back_dev_home/ebeam/hitachi/recipe_tat/MIGRATION.md`의 절차를 따르십시오.**
> 이 문서는 착수 시점의 설계 기록으로 그대로 남깁니다.

임계값 조정에 필요한 정보를 응답이 이미 싣고 있으므로, 사무실에서 별도
분석 없이 한 번의 호출로 끝납니다.

1. `GET /cdsem/recipe-tat/equipments?start_date=…&end_date=…` 를 fab 없이
   한 번 호출합니다.
2. `fleet.percentiles`의 `usage_ratio` / `tat_index` / `occupancy` /
   `recipe_count` p10·p25·p50·p75·p90을 읽습니다.
3. 실 분포가 촘촘하면(예: `usage_ratio` p10이 0.93) 절대 상수를 그 안쪽으로
   좁힙니다. 넓으면 반대로 넓힙니다.
4. `equipmentSignals.ts`의 상수 네 개만 고치고 `OFFICE-VERIFY` 주석을
   `office 확인 YYYY-MM-DD`로 바꿉니다. 백엔드·계약 변경은 없습니다.
5. `occupancy`의 절대 수준을 MES 가동률과 나란히 놓고 둘의 격차를
   `docs/datatables/meas_hist.txt`에 기록합니다 — 3.2절이 경고한 그
   격차의 실측값입니다.

`fleet.percentiles`를 계약에 넣은 이유가 이것입니다. 이게 없으면 사무실에서
임계값을 맞추는 일이 raw 데이터를 따로 뽑아 분석하는 별도 과제가 됩니다.

## 4. API

### 4.1 새 엔드포인트 2개

```http
GET /<tool_slug>/recipe-tat/equipments
    ?fab_name=R3,M16B&start_date=&end_date=

GET /<tool_slug>/recipe-tat/equipment-compare
    ?fab_name=…&start_date=&end_date=&eqp_id=ECXDX123,ECDX456
```

기존 `/ranking`·`/daily-trend`에 `eqp_id` 파라미터를 붙이는 대안을 택하지
않은 이유:

- 5대 선택 시 요청이 **10건**이 됩니다. `/api/*`는 5초에 20건 제한이라
  체크박스 클릭 한 번이 예산의 절반을 씁니다.
- 레시피 비교표는 선택 장비들의 레시피 **합집합에 0을 채운** 형태여야
  합니다. 서버에서 한 번 만드는 편이 클라이언트에서 5개 응답을 조인하는
  것보다 단순하고, 정렬 기준도 하나로 유지됩니다.
- 검증이 끝난 기존 경로와 office 어댑터가 무손상으로 남습니다.

### 4.2 계약 (`recipe_tat/contracts.py` 추가분)

```python
TAT_INDEX_MIN_SAMPLE = 12      # 이 미만이면 tat_index = None. OFFICE-VERIFY
MAX_COMPARE_EQPS = 5           # equipment-compare가 받는 장비 수 상한

class EquipmentRow(TypedDict):
    eqp_id: str
    fab_name: str
    eqp_model_cd: str
    exec_count: int                # 표시용. 신호 판정에는 쓰지 않음(3.2)
    total_meastime: int
    avg_meastime: float
    recipe_count: int
    top_recipe: str | None
    top_recipe_share: float
    tat_index: float | None        # 3.1 참고. 표본 미달이면 None
    occupancy: float               # total_meastime / 조회 기간 총 초
    usage_ratio: float             # total_meastime / 플릿 중앙값

class FleetReference(TypedDict):
    tool_count: int
    total_executions: int
    total_meastime: int
    window_seconds: int            # occupancy 분모. 기간 검증용으로 에코
    median_total_meastime: float
    median_recipe_count: float
    min_sample: int                # TAT_INDEX_MIN_SAMPLE 에코
    # 배지 임계값을 사무실에서 조정하기 위한 분포 요약(3.5절).
    # 키: "usage_ratio" | "tat_index" | "occupancy" | "recipe_count"
    # 값: {"p10","p25","p50","p75","p90"}. tat_index는 None인 장비를 제외하고
    # 계산하며, 대상 장비가 없으면 빈 dict.
    percentiles: dict[str, dict[str, float]]

class EquipmentsPayload(TypedDict):
    tool_type: ToolType
    fab_names: list[str]
    start_date: str | None
    end_date: str | None
    fleet: FleetReference
    equipments: list[EquipmentRow]        # total_meastime 내림차순

class EquipmentTrendSeries(TypedDict):
    eqp_id: str
    points: list[DailyTrendPoint]         # 기존 타입 재사용, 빈 날 0 채움

class EquipmentRecipeCell(TypedDict):
    eqp_id: str
    meas_counts: int
    total_meastime: int
    avg_meastime: float

class EquipmentRecipeRow(TypedDict):
    class_name: str
    recipe_name: str
    full_name: str
    total_meastime: int                   # 선택 장비 전체 합
    cells: list[EquipmentRecipeCell]      # 선택 장비 수만큼, 미실행은 0

class EquipmentComparePayload(TypedDict):
    tool_type: ToolType
    fab_names: list[str]
    start_date: str | None
    end_date: str | None
    eqp_ids: list[str]                    # 실제로 사용된 목록 (상한 적용 후)
    trends: list[EquipmentTrendSeries]
    recipes: list[EquipmentRecipeRow]     # total_meastime 내림차순
```

provider가 봉투(scope 에코)까지 포함한 payload를 반환합니다 — `get_summary`와
같은 방식입니다. `fleet` 블록은 route가 계산할 수 없으므로 provider가 채워야
하고, 그렇다면 봉투도 provider가 만드는 편이 route를 단순하게 둡니다.

`eqp_id` 파싱은 `_analytics_routes.py`의 `AnalyticsRequestScope`에
`eqp_ids: tuple[str, ...]` 필드를 추가해 처리합니다(쉼표 목록, 공백 제거,
`MAX_COMPARE_EQPS`에서 절단). fail_issue도 같은 헬퍼를 쓰지만 이 필드를
읽지 않으므로 무해합니다. **절단은 조용히 하지 않고** 응답의 `eqp_ids`
에코로 드러냅니다.

### 4.3 office 어댑터 방향 (`office_example.py`)

두 엔드포인트 모두 composite 집계 한 번씩이면 끝납니다.

- `/equipments` — `[eqp_id, fab_name, eqp_model_cd, full_name]` 4-source
  composite + `sum(meastime)`. 버킷 수는 대략 (장비 수 × 레시피 수)이고,
  `fab_name`과 `eqp_model_cd`는 `eqp_id`에 함수 종속이라 곱해지지 않습니다.
  나머지(`base(r)`, 중앙값, 지수)는 파이썬에서 파생합니다.
- `/equipment-compare` — 선택 `eqp_id` terms 필터를 건 뒤
  (a) `terms(eqp_id) → date_histogram(day, extended_bounds)`,
  (b) `[eqp_id, full_name]` composite + `sum(meastime)`.

공유 모듈 `_office_meas_hist.py`의 `composite_buckets()`가 지금 소스 하나
(`{"group": {"terms": {"field": field}}}`)만 만듭니다. **하위호환으로 다중
소스를 받도록 확장**합니다 — 기존 `field: str` 호출 시그니처는 그대로
동작해야 합니다. 사무실의 `office.py`는 gitignore된 복사본이라, 시그니처를
깨면 아직 복사하지 않은 다른 feature의 어댑터까지 부팅에서 죽습니다.

`vendor_nm`은 계약에 넣지 않습니다. office 문서에 그 컬럼이 없고
(`meas_hist.txt` 주의사항 2), CD/HV-SEM은 모두 Hitachi라 정보량도 없습니다.

## 5. 프론트엔드

### 5.1 컴포넌트

`RecipeTatView.vue`(729줄)의 기존 본문은 그대로 둡니다. 모드 토글에 항목 하나,
템플릿에 `v-else-if` 분기 하나만 추가하고 나머지는 새 파일로 나갑니다.

```text
components/ebeam/RecipeTatEquipmentView.vue     오케스트레이터 — fetch, 선택 상태
components/ebeam/RecipeTatFleetTable.vue        플릿 표 — 검색/정렬/체크박스/배지
components/ebeam/RecipeTatEquipmentCompare.vue  트렌드 오버레이 + 레시피 매트릭스
utils/equipmentSignals.ts                       배지 판정 순수 함수 + 테스트
```

자동 임포트 태그는 경로 접두사가 붙어 `<EbeamRecipeTatFleetTable>`입니다.
이걸 틀리면 정적 검사 신호 없이 **빈 화면만** 나오므로 브라우저 확인이
검증의 필수 단계입니다.

### 5.2 화면

**플릿 표** (선택 없음 = 기본 상태)

열: `☐ | eqp_id | fab | model | 실행수 | 총 TAT | 점유율 | 평균 | 레시피수 |
TAT index | 신호`. 기본 정렬 총 TAT 내림차순, 정렬 가능 열은 실행수·총TAT·
점유율·평균·레시피수·TAT index. eqp_id/model 검색. 체크박스는 최대 5대,
초과 시 나머지가 비활성화됩니다.

`점유율`은 `occupancy`를 백분율로 렌더링하고, 헤더 툴팁에 3.2절의 단서를
답니다 — *"측정 시간 기준입니다. 로딩·대기·PM이 빠져 있어 MES 가동률보다
낮게 읽힙니다."* 이 문장이 없으면 사용자가 62%를 보고 장비가 놀고 있다고
읽습니다. `TAT index`가 `null`인 행은 `—`로 표시하고 정렬 시 맨 뒤로
보냅니다.

**비교 패널** (1대 이상 선택 시)

1대만 골라도 열립니다 — "이 장비가 무슨 레시피를 도는가"가 원 요청의 첫
질문이기 때문입니다.

1. 일별 TAT 트렌드 — 장비당 라인 1개. **`areaStyle`을 쓰지 않습니다**:
   여러 시리즈에 채움을 주면 hover 시 blur가 채움을 지워서 화면이 깨진 것처럼
   보입니다.
2. 레시피 매트릭스 — 행 = `full_name`(선택 장비들의 합집합, 총 TAT 내림차순),
   열 = 장비별 실행수/총 TAT. 1대 선택이면 그냥 그 장비의 레시피 목록입니다.
3. 선택 요약 칩 — 실행수·총 TAT·레시피수. 플릿 표 행에서 계산하므로 추가
   요청이 없습니다.

차트는 `useEchart`를 씁니다. **차트 옵션이 커서 상태에 의존해서는 안 됩니다**
(`notMerge` 재빌드 규약).

### 5.3 캐시 키와 선택 초기화

```text
recipe-tat-equipments:{toolType}:{fabs}:{start}:{end}
recipe-tat-compare:{toolType}:{fabs}:{start}:{end}:{정렬된 eqp_ids}
```

`디바이스별`의 `resetKey` 패턴을 따라, 조회 범위(fab/기간/tool_type)가 바뀌면
장비 선택을 비웁니다. 범위 밖 장비를 선택한 채로 두면 빈 비교 패널이 남습니다.

## 6. mock 장비 플릿 수정

장비별 뷰를 붙이면 즉시 드러날 결함 네 가지가 있습니다.

| # | 결함 | 근거 |
| --- | --- | --- |
| 1 | eqp_id가 **날조된 형식** (`CG63-04`) | 다른 모든 화면은 sem_list 형식(`ECXDX123`)을 씁니다. `_tool_specs.py`: *"sem_list is the roster of record… never parse the id itself."* `meas_hist.txt` 규칙 1: *"eqp_id…는 sem-list mock data에서 고른 장비 row를 복사합니다."* 현재 mock이 문서화된 규칙을 어기고 있습니다. |
| 2 | eqp_id에 **fab 귀속이 없음** | `_build_eqp_id()`가 모델 코드만 보고 1~24를 굴려서, 같은 `CG63-04`가 M11A·M14B·R3에 동시 존재합니다. 플릿 표에서 장비 한 대가 여러 fab에 걸쳐 나타납니다. |
| 3 | eqp_id와 **meastime이 무상관** | `meastime`은 레시피 baseline × fab 배수 × jitter로만 만들어집니다. 장비가 식에 없으므로 `tat_index`는 1.00 주변 순수 잡음이 되고, 느림 신호를 집에서 검증할 방법이 사라집니다. |
| 4 | **fab 어휘 드리프트** | sem_list는 `M10, M11, M14, M15, M16, R3`, recipe_tat은 `M11, M12, M14, M15, M16, R3`. M10과 M12가 어긋나 있습니다. 지금은 아무도 두 mock을 조인하지 않아 드러나지 않았을 뿐입니다. |

### 6.1 생성 순서를 뒤집습니다

현재는 *lot → fac_id → fab_name → 장비(날조)* 순입니다. 물리적으로는 장비가
먼저입니다 — 측정은 어떤 fab의 어떤 장비에서 일어나고, lot이 거기 들어옵니다.

```text
1. tool_type 결정 (양쪽 균등)
2. 활성 플릿에서 장비 추출 (workload 가중)
   → eqp_id, fab_name, fac_id, eqp_model_cd  (전부 sem_list row에서 옴)
3. 그 장비의 fac_id에 맞는 lot 추출 (없으면 전체 lot으로 폴백)
4. 그 fab의 class mix에서 레시피 추출, 단 편중 장비는 자기 class에 고정
5. meastime = baseline × fab 배수 × 장비 speed × jitter
```

효과:

- `FAB_NAMES_BY_FAC` 하드코딩 표가 **사라집니다.** fab_name이 sem_list row에서
  직접 오므로 결함 4가 구조적으로 재발할 수 없습니다.
- `_build_eqp_id()`가 사라집니다 (결함 1·2).
- 장비별 고정 스칼라가 결함 3을 해결합니다.

### 6.2 장비별 고정 스칼라

`msr_file`이 MSR별 health 스칼라로 FDC 텔레메트리를 만드는 것과 같은 수법입니다.
장비마다 시드 고정으로 한 번 뽑고 재사용합니다.

| 스칼라 | 분포 | 만들어내는 화면 상태 |
| --- | --- | --- |
| `speed` | 대부분 `U(0.96, 1.04)`, 2대를 `1.12~1.20`에 고정 | `느림` 배지 |
| `workload` | 대부분 `U(0.92, 1.08)`, 2대를 `0.70~0.80`, 1대를 `0.30` | `저사용` 배지 + 표본 미달로 `tat_index = null` |
| `recipe_lock` | 칸의 3번째 장비를 **레시피** 2개에 고정 | `편중` 배지 |

편중을 class가 아니라 레시피 단위로 좁히는 이유: class 하나에도 레시피가
7~8개 있어서 class만 고정하면 `recipe_count`가 여전히 7~8이고
`top_recipe_share`는 0.15 언저리라 편중으로 보이지 않습니다.

**폭이 좁은 것이 핵심입니다.** 실 플릿은 가동률이 대부분 90% 이상으로 몰려
있다는 현업 확인이 있었습니다. 정상 장비를 `U(0.92, 1.08)`처럼 촘촘하게 두어야
mock이 "건강한 플릿은 편차가 크다"는 거짓을 가르치지 않고, 3.4절의 분위수 ∧
절대 임계값 조합도 실제와 비슷한 조건에서 시험됩니다. 초판 초안의
`0.15`(약 6.7배 격차)는 이 점에서 틀린 값이었습니다.

`0.30`짜리 장비 한 대만은 **의도적으로 과장한 극단 사례**입니다. 실 데이터에
그런 장비가 있다는 주장이 아니라, 표본 미달 경로(`tat_index = null`)를
UI에서 실제로 밟아보기 위한 장치입니다. docstring에 그렇게 적습니다.

낮은 `workload` 장비가 표본 하한에 걸려 `tat_index`가 `null`이 되는 것도
부작용이 아니라 **의도한 것**입니다 — mock이 UI의 모든 상태(정상/느림/저사용/
편중/표본미달)를 실제로 만들어내야 홈에서 검증이 가능합니다.

### 6.3 데이터 밀도와 조회 기간

현재 밀도는 쓸 수 없는 수준입니다. 실측하면 `cd-sem / M14A / 최근 14일` 조회에
걸리는 측정이 **전 장비 합쳐 7건**입니다. 장비별로 나누면 트렌드는커녕 표조차
의미가 없습니다.

여기에 더 긴 기간도 볼 수 있어야 한다는 요구가 겹칩니다(user-confirmed
2026-08-07). 두 요구는 같은 방향입니다 — 기간을 늘리려면 이력 창을 넓혀야 하고,
넓힌 창에서 기본 조회 밀도를 유지하려면 행 수를 그만큼 더 늘려야 합니다.

| 상수 | 현재 | 변경 | 근거 |
| --- | --- | --- | --- |
| `HISTORY_WINDOW_DAYS` | 120 | **180** | 90일 프리셋에 2배 여유 |
| 날짜 프리셋 | Today/7/14/30 | **+60/90** | `DateRangePopover`의 `DEFAULT_PRESETS`. 소비처는 RecipeTat·FailIssue 둘뿐이고 skewvoir는 자체 프리셋을 넘깁니다 |
| `TOTAL_MEAS_ROWS` | 6,000 | **55,000** | 아래 계산 |
| `TAT_INDEX_MIN_SAMPLE` | — | **12** | 20이면 기본 조회에서 절반이 `—`로 비어 보입니다. OFFICE-VERIFY |
| 활성 장비 (tool_type × fab_name당) | — | **5** | fab 1~2개 선택 시 비교 대상 5~10대 |

```text
목표: 기본 조회(fab 1개 · 14일)에서 장비당 25건 → 표본 하한 12를 넉넉히 넘김

필요 총 row = 25건 × 5장비 × 17 fab_name × (180일 / 14일) × 2 tool_type
            ≈ 55,000

검산: 27,500 cd-sem ÷ 180일 = 153건/일 ÷ 17 fab = 9건/일/fab ÷ 5장비
     = 1.8건/일/장비 × 14일 = 25건 ✓   (90일 조회 시 162건 ✓)
```

fab_name 17개 = `R3, R4` + `M10/M11/M14/M15/M16` × `A/B/C`.

**비용은 추정이 아니라 실측입니다** (2026-08-07, 이 저장소 mock 기준):

| row 수 | 생성 시간 | 메모리 |
| --- | --- | --- |
| 6,000 (현재) | 0.10s | 5.1MB |
| 30,000 | 0.50s | 25.3MB |
| 60,000 | 0.98s | 50.5MB |

행당 842 bytes로 정확히 선형이므로 55,000행은 **약 46MB, 생성 0.9초**입니다.
생성은 `lru_cache`로 프로세스당 1회입니다. `_filter_rows`의 스캔은 6,000행에
0.9ms로 측정되었으므로 55,000행에서 약 8ms이고, 이 함수도 `lru_cache(256)`이라
조회 조합당 한 번만 냅니다.

밀도에 관한 주의 하나: 이 숫자들은 **집계를 제대로 돌려보기 위한 최소치**이지
사무실 측정 물량에 대한 주장이 아닙니다. 실제 CD-SEM은 이보다 훨씬 많이
측정합니다. docstring에 그렇게 적습니다.

### 6.4 파급

- `fail_issue`가 같은 row를 읽습니다(`recipe_tat.providers.mock`에서
  `get_meas_hist`를 임포트) — 개선이 그대로 전파됩니다. 회귀 확인 대상입니다.
- `sample_eqp_ids`는 두 feature의 계약에 들어 있지만 형식을 검사하는 테스트는
  없고(길이 ≤ 5만 검사), 프론트엔드는 렌더링하지 않습니다.
- 날짜 프리셋에 60/90일을 더하면 `FailIssueView`도 함께 넓어집니다. 같은
  meas_hist row를 읽으므로 밀도 개선의 수혜자이기도 합니다. skewvoir
  `FilterBar`는 자체 프리셋을 넘기므로 영향 없습니다.
- CLAUDE.md 규칙에 따라 `docs/datatables/meas_hist.txt`와 mock docstring을
  같은 커밋에서 갱신합니다. 담을 내용:
  - sem_list를 장비 명부로 삼는다는 사실(규칙 1이 이미 요구하던 것)
  - 장비별 스칼라가 흉내내는 것은 실 데이터의 **값**이 아니라 **편차가
    존재한다는 사실**이며, 정상 장비의 폭을 좁게 둔 근거(현업 확인:
    가동률 대부분 90% 이상)
  - 이력 창 **180일** — 규칙 6이 "최근 60일"이라고 적고 있으므로 이 줄을
    함께 고칩니다. 장비별 뷰가 90일 조회를 지원하려면 60일로는 부족합니다.
  - mock 측정 물량은 집계 검증용 최소치이지 사무실 물량이 아니라는 단서
- `equipmentSignals.ts`의 임계값 네 개는 `OFFICE-VERIFY` 표시로 들어갑니다
  (3.4·3.5절).

### 6.5 구현 전 확인 사항

- `device_statistics`의 `_lot_index`가 sem_list의 6개 fac_id를 모두 덮는지.
  비는 fac이 있으면 폴백 경로가 실제로 쓰이므로 docstring에 남깁니다.
- 기존 테스트가 `TOTAL_MEAS_ROWS`·`HISTORY_WINDOW_DAYS`·eqp_id 형식을
  단언하는지.
- sem_list의 `_generate_rows()`가 tool_type × fab_name 조합마다 5대 이상을
  만드는지. 부족한 칸이 있으면 그 칸의 활성 장비 수를 실제 보유분으로
  낮춥니다(없는 장비를 지어내지 않습니다).
- 55,000행 생성이 pytest 수집 시간에 미치는 영향. 현재 전체 스위트가
  약 72초이고 device-statistics가 그 대부분입니다. recipe_tat/fail_issue
  테스트가 첫 호출에서 0.9초를 한 번 더 무는 정도여야 합니다.

## 7. 테스트

**백엔드** (`recipe_tat/tests/test_contract.py` 확장)

- `/equipments` — 계약 키 존재, `total_meastime` 내림차순, `exec_count`
  합계가 `/summary`의 `total_executions`와 일치, `tat_index`가 표본 미달
  장비에서 `None`, 표본 충족 장비에서 양수
- `tat_index`의 정의 검증 — 모든 장비가 같은 레시피 구성을 갖는 인공
  입력에서는 지수가 `avg_meastime` 비율과 일치해야 합니다
- `occupancy` — `total_meastime / fleet.window_seconds`와 일치하고
  `window_seconds`가 요청 기간(포함 일수 × 86400)과 일치
- `usage_ratio` — 중앙값 장비가 1.0 부근, 그리고 **실행 횟수가 아니라
  측정 시간 기준**임을 고정: 실행이 적지만 긴 레시피를 도는 인공 장비가
  실행이 많고 짧은 장비보다 높은 `usage_ratio`를 가져야 합니다
- `percentiles` — 각 키가 p10..p90 단조 증가, `tat_index` 분위수가 `None`
  장비를 제외하고 계산됨, 빈 범위에서 빈 dict
- `/equipment-compare` — `eqp_id` 쉼표 파싱, `MAX_COMPARE_EQPS` 절단이
  `eqp_ids` 에코에 반영, 모든 `recipes[].cells` 길이가 선택 장비 수와 동일
  (미실행 장비는 0), 트렌드가 요청 기간 전체를 0으로 채움
- 잘못된 `tool_slug` → 400
- mock 플릿 정합성 — 모든 row의 `(eqp_id, fab_name, eqp_model_cd)`가
  sem_list row와 일치하고, 한 `eqp_id`가 두 fab에 나타나지 않음
- **mock 밀도 회귀 가드** — 기본 조회(fab 1개 · 14일 · cd-sem)에서 장비당
  중앙 실행 수가 `TAT_INDEX_MIN_SAMPLE` 이상. 이 테스트가 없으면 나중에
  누가 행 수를 줄였을 때 표가 조용히 `—`로 채워집니다
- **mock이 모든 UI 상태를 만들어내는지** — 기본 조회 안에 `느림` 후보,
  `저사용` 후보, `편중` 후보, `tat_index is None` 장비가 각각 1대 이상

**프론트엔드**

- `equipmentSignals.ts` 배지 판정 단위 테스트 (`node --test`):
  - `tat_index === null` → 배지 없음
  - 분위수 꼬리지만 절대 기준 미달 → 배지 없음 (건강한 촘촘한 플릿)
  - 절대 기준 초과지만 분위수 꼬리 아님 → 배지 없음
  - 둘 다 충족 → 배지
  - `percentiles`가 빈 dict → 배지 없음

**전체**

`.venv/bin/python -m pytest -q` · `npm test` · `npm run typecheck` ·
`npm run lint` · `npm run lint:md`, 그리고 브라우저에서 세 모드 전환 ·
체크박스 상한 · 배지 · 오버레이 hover · **90일 프리셋** 확인.

## 8. 범위 밖

- 측정 0건 장비 표시 (sem_list 명부 조인) — 2절 참고
- 장비 상세 페이지로의 딥링크
- office 어댑터의 실제 구현/검증 — 템플릿(`office_example.py`)까지만
  작성하고, 실행 검증은 사무실에서 합니다

### 8.1 범위 밖이 아닌 것 — HV-SEM

`recipe_tat/providers/mock.py`의 docstring이 *"no HV-SEM frontend currently
calls these endpoints"*라고 적어 두었지만 **사실이 아닙니다**:
`pages/ebeam/hv-sem/[fab]/recipe-status.vue`가 `RecipeStatusView`를
`tool-type="hv-sem"`으로 마운트하고 있습니다. 장비별은 슬러그만 다른 같은
코드 경로이므로 추가 작업은 없지만, HV-SEM에서도 확인해야 하고 6절에서
docstring을 다시 쓸 때 이 문장을 함께 바로잡습니다.
