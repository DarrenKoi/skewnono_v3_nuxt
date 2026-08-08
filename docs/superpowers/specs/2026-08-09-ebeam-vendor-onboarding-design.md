# E-Beam 벤더 온보딩 설계 (VeritySEM / Provision)

작성일: 2026-08-09

## 1. 배경과 목적

2027년 확장 계획에 따라 AMAT 계열 장비인 **VeritySEM** 과 **Provision** 을
연계해야 합니다. 지금까지 Hitachi 계열(CD-SEM / HV-SEM) 하나만 존재했기 때문에
"벤더"라는 축이 코드에 제대로 표현된 적이 없으며, 그 결과 벤더 폴더가 사실상
공용 라이브러리로 쓰이는 상태입니다.

이 문서는 **`ebeam/` 안에서 새 벤더를 붙이는 절차**를 규약으로 확정합니다.
목적은 기능 추가가 아니라, mock → office 전환이 지금까지와 동일한 방식으로
자연스럽게 이어지도록 구조와 순서를 고정하는 것입니다.

### 이 문서의 범위가 아닌 것

- **Thickness 계측 장비**는 e-beam 과 완전히 독립적으로 진행합니다.
  별도 폴더 구조를 가질 수 있으며, `sem_list` 명부도 공유하지 않습니다.
  별도 spec 으로 다룹니다.
- AMAT feature 의 실제 구현. 이 문서는 절차만 확정하며, 어떤 feature 를
  언제 붙일지는 소스가 확인되는 대로 단계적으로 결정합니다.
- `afm`, `skew`, `chat` 은 기존 방침대로 이 범위에서 제외합니다.

## 2. 확인된 현황

### 2.1 이미 준비된 것

| 계층 | 상태 |
| --- | --- |
| roster | `v3_df_sem_list` 에 VeritySEM / Provision 포함 (user-confirmed 2026-07-30), `vendor_nm='AMAT'` |
| 프론트 분류기 | `utils/toolType.ts` 가 AMAT 두 계열을 이미 반환 |
| 프론트 페이지 | `pages/ebeam/{verity-sem,provision}/[fab]/index.vue` 인벤토리 뷰 존재 |

즉 **장비 identity 계층은 이미 끝나 있습니다.** 남은 것은 각 feature 의
데이터를 어디서 읽느냐입니다.

### 2.2 사무실 데이터 위치

사용자 확인 결과, **roster 만 공통이고 나머지는 별도 소스**입니다.
실제로 storage 의 오피스 키 이름부터 벤더와 계열이 박혀 있습니다.

```text
v3_df_ppid_storage_cdsem
v3_df_ppid_storage_hvsem
v3_hitachi_sem_ppid_not_avail
```

따라서 AMAT 은 자기 키를 갖게 되며, 어댑터 분리가 자연스럽습니다.

### 2.3 벤더 폴더가 이미 벤더 폴더가 아니라는 사실

`ebeam/hitachi/` 내부를 다른 축의 코드가 import 하고 있습니다.

| 참조하는 쪽 | 참조 대상 |
| --- | --- |
| `meas_hist/contracts.py:7` | `ebeam.hitachi._tool_specs` |
| `meas_hist/providers/mock.py:52` | `ebeam.hitachi._tool_specs` |
| `meas_hist/providers/office_example.py:65` | `ebeam.hitachi._office_meas_hist` |
| `msr_file/providers/office_example.py:60` | `ebeam.hitachi._office_meas_hist` |
| `ebeam/cdsem/device_statistics/providers/office_example.py:149` | `ebeam.hitachi._office_search` |

record 형 feature 와 다른 벤더 폴더가 `hitachi/` 내부를 쓰고 있으므로, 이 폴더는
이름만 벤더일 뿐 실제로는 공용 SEM 계층입니다.

### 2.4 두 가지 feature 유형

| 유형 | 소속 | tool 축 표현 | 해당 feature |
| --- | --- | --- | --- |
| fleet 형 | `ebeam/` | URL path segment `<tool_slug>` | storage, hardware, skew, recipe_tat, recipe_search, pm_planning, fail_issue, lateral_recipe, live_alarm |
| 계열 고정형 | `ebeam/` | 없음 — 경로에 `/cdsem/` 이 하드코딩 | device_statistics |
| record 형 | 최상위 | 쿼리 파라미터 `tool_type` | msr_file, msr_image, meas_hist (= skewvoir) |

`device_statistics` 는 `/api/cdsem/device-statistics/…` 처럼 계열이 경로에
박혀 있어 슬러그 파라미터가 없습니다. 폴더는 `ebeam/device_statistics/` 로
평탄화하지만, **벤더 축을 붙일 대상이 아닙니다.** AMAT 에 대응하는 화면이
필요해지면 그때 별도로 판단합니다.

skewvoir 는 record 형이므로 `ebeam/` 재배치의 영향을 받지 않습니다. 다만
tool_type 도메인 확장에는 정면으로 영향을 받습니다(§5 참조).

## 3. 결정 사항 요약

| 항목 | 결정 |
| --- | --- |
| 백엔드 레이아웃 | `ebeam/<feature>/` 로 평탄화 (`hitachi/`, `cdsem/` 중간 폴더 제거) |
| 벤더 축 표현 | `<feature>/providers/<adapter>/` 하위 폴더. 단위는 벤더가 아니라 **어댑터가 담당하는 범위** — `hitachi/`(cdsem+hvsem), `veritysem/`, `provision/` |
| 개명 시점 | 즉시 실행 |
| AMAT tool_type | `veritysem`, `provision` (하이픈 없음) |
| `veritysem` 적용 범위 | 백엔드 슬러그 · tool_type · 프론트 라우트 · 활동 로그 슬러그 전부 |
| 어댑터 미작성 시 | 사무실 모드에서 **501 명시적 거절** (mock 폴백 금지) |
| 결과물 | `docs/back-end/vendor-onboarding.md` + `.claude/skills/add-vendor/` |

## 4. 설계 1 — 레이아웃

### 4.1 목표 구조

```text
back_dev_home/ebeam/
├── _tool_specs.py          # 벤더·슬러그·tool_type 단일 레지스트리
├── _office_meas_hist.py    # 공용 오피스 헬퍼
├── _office_search.py
├── _analytics.py
├── storage/
│   ├── contracts.py        # 벤더 무관 1개
│   ├── data.py             # 슬러그 → 벤더 해석 → 디스패치
│   ├── MIGRATION.md
│   ├── routes.py
│   ├── providers/
│   │   ├── mock.py             # 레지스트리가 발견하는 디스패처
│   │   ├── office_example.py   # 어댑터 디스패처
│   │   ├── hitachi/{mock,office_example}.py    # cdsem + hvsem
│   │   ├── veritysem/{mock,office_example}.py
│   │   └── provision/{mock,office_example}.py
│   └── tests/
├── hardware/               # 탭 하위 폴더 + 벤더 하위 폴더 (2축)
├── skew/  recipe_tat/  recipe_search/  pm_planning/
├── fail_issue/  lateral_recipe/  live_alarm/
└── device_statistics/      # ebeam/cdsem/ 에서 승격
```

### 4.2 평탄화가 안전한 이유

`_runtime/office_registry.py` 의 `_discover()` 는 feature 를
`feature_dir.name` **하나로만** 식별하고 전역 유일성을 강제합니다.
중복이 있으면 부팅 시 `RuntimeError: Duplicate feature slug` 가 납니다.

이 사실에서 두 가지가 따라 나옵니다.

1. 중간 폴더(`hitachi/`, `cdsem/`)는 provider 해석에 **아무 역할도 하지
   않습니다.** `SKEWNONO_STORAGE_PROVIDER` 는 경로와 무관하게 `storage` 를
   가리킵니다. 라우트 역시 `/api/<tool_slug>/storage` 로 벤더가 등장하지
   않습니다. 따라서 평탄화는 정보 손실이 없습니다.
2. 벤더를 **폴더 축으로 만드는 방식은 불가능합니다.** `ebeam/amat/storage` 와
   `ebeam/hitachi/storage` 는 슬러그가 충돌해 부팅이 실패합니다. 벤더는
   `providers/` 하위 축으로 표현해야 합니다.

### 4.3 벤더 하위 폴더가 기존 도구와 그대로 맞는 이유

`hardware/providers/` 가 이미 `fdc/`, `bm_pm/`, `sce/`, `sharpness/`,
`mdc/`, `reso_center/`, `bsm/` 하위 폴더 패턴을 쓰고 있습니다. 따라서 다음이
**변경 없이** 동작합니다.

| 대상 | 근거 |
| --- | --- |
| `.gitignore` | `back_dev_home/**/providers/**/office.py` 가 이미 존재 |
| `sync_office_adapters` | `hardware/fdc` 형식의 중첩 인자를 이미 지원 |
| `office_registry` | `**/providers/<filename>` 글롭이 하위 폴더를 의도적으로 제외 |
| `/api/health/providers` | feature 레벨 해석만 하므로 영향 없음 |

**중요**: feature 레벨의 `providers/mock.py` 와 `providers/office_example.py`
는 **반드시 남깁니다.** 레지스트리가 발견하는 것은 `providers/` 바로 아래의
`mock.py` 이므로, 이를 벤더 폴더로 옮기면 해당 feature 가 레지스트리에서
사라지고 `get_data_provider()` 와 헬스 엔드포인트가 깨집니다.

### 4.4 하위 폴더의 단위는 "어댑터가 담당하는 범위"

하위 폴더를 벤더로 자를지 tool family 로 자를지가 갈립니다. 결론은 **어느
쪽도 아니고, 하나의 오피스 어댑터가 덮는 범위**입니다.

| 폴더 | 덮는 계열 | 이유 |
| --- | --- | --- |
| `hitachi/` | `cdsem` + `hvsem` | 현재 어댑터가 이미 `tool_slug` 를 인자로 받아 두 계열을 서빙합니다. 오피스 키는 계열별로 갈라져 있지만(`v3_df_ppid_storage_cdsem` / `_hvsem`) 어댑터 안에서 분기합니다 |
| `veritysem/` | `veritysem` | 소스가 확인되지 않았고, 두 계열이 따로 확인될 가능성이 높습니다 |
| `provision/` | `provision` | 위와 같습니다 |

AMAT 을 `amat/` 하나로 묶지 않는 이유는 **readiness 표현** 때문입니다.
VeritySEM 소스는 확인됐는데 Provision 은 아직인 상황에서, `amat/office.py`
하나로는 "둘 다 연계된 척"하거나 "둘 다 막는 것" 중 하나밖에 못 합니다.
파일 존재가 곧 스위치라는 이 저장소의 규약(§6.2 8단계)은 그 파일이 덮는
범위가 실제 연계 단위와 일치할 때만 정확합니다.

나중에 두 계열이 같은 소스를 쓰는 것으로 확인되면 `amat/` 하나로 합칠 수
있습니다. `contracts.py` 가 공유되므로 합치는 비용은 낮습니다. 반대 방향
(하나를 둘로 쪼개기)이 더 비싸므로 쪼갠 상태에서 출발합니다.

두 축의 개수가 다르다는 점을 기억합니다 — 벤더는 2개(어댑터를 가르는 축),
tool family 는 4개(URL·명부를 가르는 축)입니다. 벤더를 feature 위에 두면 이
두 축이 한 경로에 뭉개집니다.

### 4.5 어댑터 디스패처

`hardware/providers/office_example.py` 의 `_tab()` 을 본뜨되, **폴백 정책만
다릅니다.**

```python
def _adapter(name: str):
    """providers/<adapter>/office.py 를 import 합니다.

    없으면 501 을 발생시킵니다. hardware 의 _tab() 은 mock 으로 폴백하지만,
    탭은 원래 존재하는 것이고 미완인 기간이 짧습니다. 신규 계열은 어댑터가
    없는 기간이 몇 달 단위이므로, 같은 폴백을 쓰면 사무실에서 조작된 mock
    데이터를 진짜처럼 몇 달간 보여주게 됩니다.

    name 은 tool_slug 에서 온 어댑터 이름입니다 — cdsem/hvsem -> "hitachi",
    veritysem -> "veritysem", provision -> "provision". 이 매핑은
    ebeam/_tool_specs.py 가 유일한 원천입니다.
    """
    module = f"{__package__}.{name}.office"
    try:
        return import_module(module)
    except ModuleNotFoundError as exc:
        if exc.name != module:
            raise  # 어댑터 내부의 진짜 의존성 누락
    raise AdapterNotWired(name)
```

`exc.name` 가드는 그대로 유지합니다. "아직 만들지 않은 어댑터"와 "만들었는데
import 가 깨진 어댑터"를 구분하는 것이 이 패턴의 핵심이며, 이 구분이 없으면
배선된 어댑터의 import 실패가 조용히 mock 으로 강등됩니다.

집(mock 모드)에서는 501 이 발생하지 않습니다. 벤더별 `mock.py` 는 항상
존재하기 때문입니다.

## 5. 설계 2 — tool_type 도메인 확장

### 5.1 레지스트리

`ebeam/_tool_specs.py` 가 슬러그 · tool_type · 벤더의 단일 원천이 됩니다.

| 슬러그 | tool_type | 벤더 | 어댑터 폴더 |
| --- | --- | --- | --- |
| `cdsem` | `cd-sem` | HITACHI | `hitachi/` |
| `hvsem` | `hv-sem` | HITACHI | `hitachi/` |
| `veritysem` | `veritysem` | AMAT | `veritysem/` |
| `provision` | `provision` | AMAT | `provision/` |

벤더(2개)와 어댑터 폴더(3개)의 개수가 다릅니다. 벤더는 `sem_list` 의
`vendor_nm` 과 화면 표기에 쓰이고, 어댑터 폴더는 오피스 연계 단위입니다.
둘을 같은 것으로 다루지 않습니다.

AMAT 계열은 **슬러그 = tool_type = 프론트 라우트가 한 문자열**입니다.
이중 표기(`cdsem` ↔ `cd-sem`)는 Hitachi 레거시로만 남습니다. 제품명이
VeritySEM / PROVision 이라는 한 단어이므로 하이픈을 넣을 이유가 없고,
표기가 하나면 라우트 ↔ tool_type 매핑 테이블이 생기지 않습니다.

`model_to_tool_type()` 이 AMAT 모델을 해석하도록 고칩니다. 현재는 `None` 을
반환하며, `meas_hist/providers/mock.py:269` 가 그 `None` 으로 row 를 걸러내고
있어 AMAT 장비가 측정 이력에서 통째로 사라집니다.

### 5.2 프론트 레지스트리 통합

현재 tool_type union 이 최소 5벌 따로 선언되어 있습니다.

| 위치 | 선언 |
| --- | --- |
| `stores/navigation.ts:5` | `ToolType` |
| `useLateralRecipeApi.ts:4` | `LateralRecipeToolType` |
| `useFailIssueApi.ts:3` | `FailIssueToolType` |
| `useRecipeSearchApi.ts:4` | `RecipeSearchToolType` |
| `useMeasHistApi.ts` | `MeasHistToolType` |

슬러그 매핑(`toolSlug()`, `TOOL_TO_BACKEND_SLUG`)도 composable 마다 자기
것을 들고 있습니다. `utils/toolType.ts` 를 유일한 원천으로 승격하고 나머지를
흡수합니다.

백엔드와의 일치는 **공유 fixture 계약 테스트**로 고정합니다.
`__fixtures__/tool_type_cases.json` 을 pytest 와 `node --test` 가 함께 읽어
같은 모델 코드에 대해 같은 tool_type 이 나오는지 검증합니다. 현재
`utils/toolType.ts` 주석이 백엔드와 불일치함을 자백하고 "별도 추적"으로
남겨둔 부채를 여기서 갚습니다.

### 5.3 침묵 실패 감사

새 tool_type 값이 "미지 → `None` → 전체"로 떨어지는 경로를 전수 정정합니다.
이 유형은 오류를 내지 않고 **틀린 결과를 그럴듯하게** 반환하므로 리뷰에서
발견되지 않습니다.

| 위치 | 증상 |
| --- | --- |
| `meas_hist/routes.py:15,20` | 미지 값이 `None` 이 되고, `None` 의 의미가 "필터 없음 = 전체" 이므로 **필터를 걸었는데 전 장비가 반환** |
| `meas_hist/providers/mock.py:269` | `model_to_tool_type() is not None` 필터가 AMAT row 를 **소거** |
| `useSkewvoirAnalysis.ts:75` | `ws.toolType === 'cd-sem' ? 'hv-sem' : 'cd-sem'` — tool_type 이 정확히 2개라는 전제. `veritysem` 이 오면 **엉뚱한 계열의 비교 데이터**를 나란히 렌더 |
| 프론트 union 5벌 · 슬러그 매핑 N벌 | 한 곳만 고치면 나머지가 조용히 어긋남 |

정정 원칙 3가지입니다.

1. **미지의 값은 거절합니다.** 파싱 실패와 미지정을 구분합니다. 전자는
   `400`, 후자만 `None`(= 전체)입니다.
2. **이분법을 금지합니다.** `A ? X : Y`, `if not A: B` 형태로 tool_type 을
   다루는 곳은 전부 레지스트리 조회로 바꿉니다.
3. **`None` 이 "전체"인 자리와 "알 수 없음"인 자리를 섞지 않습니다.**

### 5.4 `veritysem` 표기 변경의 파급

영향 파일은 12개 내외이며 기계적입니다.

`utils/toolType.ts`, `stores/navigation.ts`,
`pages/ebeam/verity-sem/` → `pages/ebeam/veritysem/`(2파일),
`nav/FeatureTabs.vue`, `nav/FabSidebar.vue`, `useToolData.ts`,
`tool-roster.vue`, `pendingToolMatrix.test.ts`, `toolType.test.ts`,
`pageIdentity.test.ts`, `activity.ts`, `_logging/feature_map.py` 와 그 테스트.
`docs/study/` 의 교재 예시도 함께 갱신합니다.

**활동 로그 슬러그는 append-only 규칙을 지킵니다.** OpenSearch
`usage_events` 에 `verity_sem` 이 이미 기록되어 있으므로 rename 하지 않습니다.
새 슬러그를 추가하고 `activity.ts` 의 `FEATURE_LABELS` 에서 기존
`verity_sem` 라벨은 **삭제하지 않고 남깁니다.** `cdsem` / `hvsem` /
`provision` 을 같은 방식으로 처리한 선례가 있습니다.

## 6. 설계 3 — 온보딩 워크플로

### 6.1 Phase 0 — 한 번만 수행하는 기반 정리

§4 와 §5 가 여기 해당합니다. 평탄화 개명, 레지스트리 승격, `veritysem`
도메인 확장, 침묵 실패 정정, 프론트 union 통합입니다. 이것이 끝나면 이후
feature 추가는 Phase 1 의 반복이 됩니다.

### 6.2 Phase 1 — feature × 벤더마다 반복

순서 자체가 규약입니다.

| # | 단계 | 산출물 | 규칙 |
| --- | --- | --- | --- |
| 1 | 계약 확인 | `<feature>/contracts.py` | 벤더별로 나누지 않습니다. AMAT 이 채우지 못하는 필드는 계약을 쪼개는 대신 null 규약(`""` / `None`)을 계약에 적습니다 |
| 2 | 스키마 기록 | `docs/datatables/<source>.txt` | 출처 표기 필수 — `office 확인 YYYY-MM-DD` / `user-confirmed` / `OFFICE-VERIFY` |
| 3 | mock 작성 | `providers/<adapter>/mock.py` | `sem_list` 의 `vendor_nm='AMAT'` row 에서 **파생**합니다. 독립 생성 금지 |
| 4 | 템플릿 작성 | `providers/<adapter>/office_example.py` | 추적되는 템플릿. 사무실에서 `cp` 할 대상 |
| 5 | 디스패처 배선 | `providers/{mock,office_example}.py` 의 `_adapter()` | 폴백 대신 501. `exc.name` 가드 유지 |
| 6 | 문서 갱신 | `<feature>/MIGRATION.md` | 엔드포인트 · 계약 · mock 동작 · 오피스 소스 4항목 |
| 7 | 테스트 | `tests/test_contract.py`, `test_office_template.py` | 어댑터를 파라미터로 추가 |
| 8 | 사무실 연결 | `cp office_example.py office.py` | 이 복사가 곧 스위치입니다. `/api/health/providers` 로 확인 |

### 6.3 불변식

1. **명부는 하나입니다.** 어떤 벤더의 어떤 feature 든 장비 identity 는
   `sem_list` 에서만 옵니다. `eqp_id` 를 파싱해 벤더나 계열을 판정하는 코드는
   금지입니다. `_tool_specs.py` 가 기록한 대로, prefix 를 분류기로 쓴 결과
   실장비 8대가 조용히 사라진 사고가 있었습니다.
2. **사실은 두 곳에 기록합니다.** 사무실 DB 에 대해 새로 알게 된 것은
   `docs/datatables/*.txt` 와 해당 `mock.py` docstring 양쪽에 적습니다.
   한쪽만 갱신하면 다음 홈 세션이 그것을 반박합니다.
3. **없는 것은 없다고 말합니다.** 어댑터 미작성은 빈 배열도 mock 도 아닌
   501 입니다.

## 7. 결과물

| 산출물 | 위치 | 내용 |
| --- | --- | --- |
| 규약 문서 | `docs/back-end/vendor-onboarding.md` | 한국어. §4~§6 의 규약. `provider-selection.md` 옆에 배치하고 상호 링크 |
| 실행 스킬 | `.claude/skills/add-vendor/` | §6.2 의 8단계를 체크리스트로. 규약은 문서를 참조해 중복을 피합니다 |
| 기존 스킬 갱신 | `.claude/skills/home-to-office/` | 벤더 하위 폴더도 감사 대상에 포함 |

## 8. 검증

| 대상 | 합격 기준 |
| --- | --- |
| Phase 0 리팩터링 | 순수 리팩터링이므로 **테스트 수가 줄지 않아야 합니다**. worktree 는 gitignored `office.py` 가 없어 skip 수가 다르므로, passed 만이 아니라 **passed + skipped 합계**로 비교합니다 |
| 분류기 일치 | 공유 fixture 계약 테스트가 pytest 와 `node --test` 양쪽에서 통과 |
| 침묵 실패 정정 | 미지 tool_type 요청이 `400` 을 반환하는 회귀 테스트 |
| 라우팅 | `/ebeam/veritysem/M14` 렌더 확인 |
| provider 해석 | `/api/health/providers` 응답에 feature 목록이 이전과 동일하게 나오는지 확인 |

## 9. 리스크

| 리스크 | 대응 |
| --- | --- |
| 개명이 409곳의 import 를 건드림 | 기계적 치환이며 한 번의 커밋으로 끝냅니다. 다중 파일 작업이므로 worktree 에서 수행합니다 |
| 사무실의 gitignored `office.py` 사본이 옛 경로를 import | 개명 후 사무실에서 `sync_office_adapters` 로 STALE 판정 후 재복사가 필요합니다. **개명 커밋의 전달 시 반드시 함께 안내합니다** |
| 동시 세션이 같은 작업 트리를 공유 | 명시적 pathspec 으로만 커밋합니다 |
| `veritysem` 표기 변경으로 기존 북마크 URL 이 깨짐 | 내부 도구이며 해당 페이지는 인벤토리 뷰 하나뿐이므로 리다이렉트는 두지 않습니다 |

## 10. 열린 항목

- AMAT feature 의 **1차 범위**는 확정하지 않았습니다. 공통분모부터
  단계적으로 진행하되, 각 feature 의 오피스 소스가 확인되는 시점에
  §6.2 를 적용합니다.
- AMAT 오피스 소스의 실제 키 이름과 스키마는 아직 알려지지 않았습니다.
  확인 전까지 `docs/datatables/` 항목은 `OFFICE-VERIFY` 로 표기합니다.
