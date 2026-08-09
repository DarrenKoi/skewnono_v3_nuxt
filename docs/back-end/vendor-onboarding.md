# 신규 장비 계열 온보딩 규약

새 e-beam 장비 계열(VeritySEM, Provision, 그리고 앞으로 생길 것)을 기존
백엔드 feature 에 붙일 때 따르는 절차입니다. mock → office 전환이 지금까지와
**같은 방식으로** 이어지도록 구조와 순서를 고정하는 것이 목적입니다.

provider 가 무엇으로 해석되는지의 규칙은
[`provider-selection.md`](provider-selection.md), 어댑터 구현 지침은
[`office-data-adapters.md`](office-data-adapters.md) 가 기준이며 이 문서는
그 위에 **"축이 하나 더 생겼을 때"** 의 규약만 더합니다.

실행 절차만 필요하다면 `.claude/skills/add-vendor/` 스킬이 아래 §4 의
8단계를 체크리스트로 제공합니다. 규칙의 근거는 이 문서에만 있습니다.

각 규칙에 근거를 함께 적습니다. 근거 없는 규약은 다음 사람이 불편하다는
이유로 뒤집기 때문입니다.

## 1. Phase 0 에서 이미 끝난 것

새 계열을 붙이는 사람이 **다시 만들 필요가 없는 기반**입니다.

| 기반 | 위치 | 내용 |
| --- | --- | --- |
| 장비 레지스트리 | `back_dev_home/ebeam/_tool_specs.py` | 슬러그 ↔ tool_type ↔ 벤더 ↔ 어댑터 폴더의 단일 원천 (`SLUG_TO_TOOL_TYPE`, `TOOL_TYPE_TO_VENDOR`, `SLUG_TO_ADAPTER`) |
| CD/HV 전용 범위 | 같은 파일의 `SEM_TOOL_TYPES` | CD-SEM · HV-SEM 만 담는 집합. 이 범위를 뜻하려면 이 이름을 씁니다 |
| 분류기 일치 | `back_dev_home/ebeam/__fixtures__/tool_type_cases.json` | 백엔드와 프론트 분류기가 같은 fixture 를 읽어 서로 어긋날 수 없게 고정 |
| 레이아웃 | `back_dev_home/ebeam/<feature>/` | 중간 벤더 폴더 없이 평탄화 완료 |

세 가지를 특히 기억합니다.

- **`model_to_tool_type()` 의 `None` 은 이제 "미지"만 뜻합니다.** 예전에는
  "AMAT 장비"라는 뜻도 겸했기 때문에 "CD/HV 만"을 뜻하려는 코드가
  `model_to_tool_type(...) is not None` 이라고 썼습니다. 분류기가 AMAT 을
  해석하기 시작하면 그 표현은 **오류 없이 의미만 바뀝니다.** 그래서
  `in SEM_TOOL_TYPES` 로 의도를 이름에 박아 두었습니다. 새 계열을 추가하면서
  `is not None` 을 다시 쓰지 않습니다.
- **분류기는 두 벌(파이썬 · 타입스크립트)이지만 사례는 한 벌입니다.**
  새 계열의 모델 코드를 넣을 때는 접두사만 추가하지 말고
  `tool_type_cases.json` 에 사례를 함께 추가합니다. 그래야
  `back_dev_home/ebeam/tests/test_tool_type_parity.py` 와
  `front-dev-home/app/utils/toolTypeParity.test.ts` 가 함께 지켜 줍니다.
- **AMAT 계열은 슬러그 = tool_type = 프론트 라우트가 한 문자열입니다**
  (`veritysem`, `provision`). `cdsem` ↔ `cd-sem` 같은 이중 표기는 Hitachi
  레거시로만 남습니다. 새 계열에 하이픈 표기를 만들지 않습니다.

## 2. 계열은 feature 위 폴더가 될 수 없습니다

`back_dev_home/_runtime/office_registry.py` 의 `_discover()` 는 feature 를
**`feature_dir.name` 하나로만** 식별하고 전역 유일성을 강제합니다. 중복이
발견되면 다음 예외로 **부팅 자체가 실패합니다.**

```text
RuntimeError: Duplicate feature slug 'storage': ... and ...
Feature directory names must be globally unique —
SKEWNONO_STORAGE_PROVIDER can only name one of them.
```

즉 `ebeam/amat/storage/` 와 `ebeam/hitachi/storage/` 를 나란히 두는 배치는
지저분한 정도의 문제가 아니라 **앱이 뜨지 않는 배치**입니다. 근본 원인은
env override 입니다. `SKEWNONO_<SLUG>_PROVIDER` 라는 이름 하나가 가리킬 수
있는 대상은 하나뿐이므로, 슬러그가 겹치면 어느 쪽을 override 하려는 것인지
표현할 방법이 없습니다.

같은 이유로, 중간 폴더는 provider 해석에 **아무 역할도 하지 않습니다.**
경로가 어떻든 `SKEWNONO_STORAGE_PROVIDER` 는 `storage` 를 가리키고, 라우트도
`/api/<tool_slug>/storage` 처럼 슬러그를 경로 파라미터로 받습니다. 따라서
계열 축은 `providers/` **아래**로 표현해야 합니다.

## 3. 계열 축은 `providers/<family>/` 하위 폴더입니다

아직 이 모양을 쓰는 feature 는 없습니다. 아래는 **만드는 절차**입니다.

```text
ebeam/<feature>/providers/
├── mock.py              # 레지스트리가 발견하는 디스패처 (그대로 유지)
├── office_example.py    # 어댑터 디스패처 (그대로 유지)
├── hitachi/{mock,office_example}.py
├── veritysem/{mock,office_example}.py
└── provision/{mock,office_example}.py
```

### 3.1 기존 도구가 그대로 동작하는 이유

`back_dev_home/ebeam/hardware/providers/` 가 이미 `fdc/`, `bm_pm/`, `sce/`,
`sharpness/`, `mdc/`, `reso_center/`, `bsm/` 로 같은 모양을 씁니다. 따라서
다음이 **아무 변경 없이** 동작합니다.

| 대상 | 근거 |
| --- | --- |
| `.gitignore` | `back_dev_home/**/providers/**/office.py` 규칙이 이미 있습니다 |
| `sync_office_adapters` | `hardware/fdc` 형태의 중첩 인자를 이미 지원합니다 (경로 세그먼트 접미사 매칭) |
| `office_registry` | `**/providers/<filename>` 글롭이 `providers` 바로 아래만 잡으므로 하위 폴더를 **의도적으로** 제외합니다 |
| `/api/health/providers` | feature 레벨 해석만 하므로 영향이 없습니다 |

### 3.2 feature 레벨의 `mock.py` · `office_example.py` 는 반드시 남깁니다

레지스트리가 feature 를 발견하는 조건은 `providers/mock.py` 의 존재입니다.
이 파일을 계열 폴더로 옮기면 해당 feature 가 **레지스트리에서 사라지고**
`get_data_provider()` 와 `/api/health/providers` 가 함께 깨집니다. 계열 폴더가
생겨도 이 두 파일은 남아 **디스패처** 역할을 합니다.

### 3.3 하위 폴더의 단위는 벤더가 아니라 장비 패밀리입니다

| 폴더 | 덮는 계열 |
| --- | --- |
| `hitachi/` | `cdsem` + `hvsem` (예외) |
| `veritysem/` | `veritysem` |
| `provision/` | `provision` |

VeritySEM 과 Provision 은 **아예 다른 형태의 데이터를 가집니다**
(user-confirmed 2026-08-09). "둘 다 AMAT"이라는 사실은 한 어댑터에 묶을
근거가 되지 못합니다. 벤더는 `sem_list` 의 `vendor_nm` 과 화면 라벨에 쓰이는
표기이지, 데이터 형태를 결정하는 축이 아닙니다.

`hitachi/` 하나가 두 계열을 덮는 것은 규칙이 아니라 **우연입니다.** CD-SEM 과
HV-SEM 이 마침 겹치는 부분이 많아 하나로 처리할 수 있었을 뿐이며, 오피스 키는
이미 `v3_df_ppid_storage_cdsem` / `v3_df_ppid_storage_hvsem` 으로 갈라져
어댑터 안에서 분기합니다. 동작하는 코드이므로 그대로 두지만 **본보기가 아닙니다.**
두 계열이 갈라지면 그때 `hitachi/` 를 `cdsem/` · `hvsem/` 으로 쪼갭니다.

패밀리 단위가 주는 두 번째 이득은 **readiness 를 표현할 수 있다는 점**입니다.
`amat/office.py` 하나로는 "VeritySEM 은 연계됐고 Provision 은 아직"이라는
상태를 표현할 수 없어 둘 다 연계된 척하거나 둘 다 막는 것 중 하나밖에 못
합니다. 파일 존재가 곧 스위치라는 이 저장소의 규약은, 그 파일이 덮는 범위가
실제 연계 단위와 일치할 때만 정확합니다.

### 3.4 어댑터가 없으면 mock 폴백이 아니라 501 입니다

`hardware/providers/office_example.py` 의 `_tab()` 은 하위 폴더에 `office.py`
가 없으면 그 탭의 `mock.py` 로 폴백합니다. **새 계열은 이것을 따르지
않습니다.**

차이의 근거는 "없는 기간의 길이"입니다. 탭은 원래 존재하는 화면이고 미완인
기간이 짧습니다. 반면 새 계열은 어댑터가 없는 기간이 **몇 달 단위**입니다.
같은 폴백을 쓰면 사무실에서 조작된 mock 데이터를 진짜 사무실 데이터로 한 분기
내내 보여주게 됩니다.

`exc.name` 가드는 그대로 가져옵니다. "아직 만들지 않은 어댑터"와 "만들었는데
import 가 깨진 어댑터"를 구분하는 것이 이 패턴의 핵심이며, 이 구분이 없으면
배선된 어댑터의 import 실패가 조용히 mock 으로 강등됩니다.

```python
# back_dev_home/ebeam/_adapters.py — 아래 §3.5
from werkzeug.exceptions import NotImplemented as NotImplementedHTTP


class AdapterNotWired(NotImplementedHTTP):
    def __init__(self, feature: str, family: str) -> None:
        super().__init__(
            f"{feature} 의 {family} 계열은 아직 사무실 어댑터가 없습니다 "
            f"(providers/{family}/office.py 미작성)."
        )


# <feature>/providers/office_example.py
def _adapter(name: str):
    module = f"{__package__}.{name}.office"
    try:
        return import_module(module)
    except ModuleNotFoundError as exc:
        if exc.name != module:
            raise  # 어댑터 내부의 진짜 의존성 누락
    raise AdapterNotWired(_FEATURE, name)
```

`__init__` 이 문장을 조립하는 것은 장식이 아닙니다. `HTTPException` 은 첫 인자를
`description` 으로 받아 응답 본문에 그대로 싣기 때문에, `AdapterNotWired(name)`
로 던지면 501 본문이 `"veritysem"` 한 단어가 되어 무엇이 왜 없는지 알 수 없습니다.

**501 로 나가게 하려면 예외 타입을 골라야 합니다.** `back_dev_home/__init__.py`
의 JSON 에러 핸들러는 `HTTPException` 만 그 상태 코드로 내보내고, 정확히
`RuntimeError` 인 것만 503, 그 하위 클래스(`NotImplementedError` 포함)는 500
으로 처리합니다. 따라서 `AdapterNotWired` 는
`werkzeug.exceptions.NotImplemented` 를 상속시킵니다. 맨 `NotImplementedError`
를 던지면 500 이 되어 "미배선"이라는 정보가 사라집니다.

**이 정책은 `office_example.py` 쪽 디스패처만의 것입니다.** `providers/mock.py`
도 같은 이름의 `_adapter()` 를 갖지만, 계열별 `mock.py` 는 8단계 중 3단계에서
항상 먼저 만들어져 없을 수가 없습니다. 그래서 집(mock 모드)에서는 이 예외가
발생하지 않습니다.

### 3.5 `AdapterNotWired` 는 한 곳에만 정의합니다

정의 위치는 **`back_dev_home/ebeam/_adapters.py`** 입니다. `_office_meas_hist.py`
· `_office_search.py` 와 같은 자리이고, 밑줄 접두사가 blueprint 스캔에서 빠지게
해 줍니다. feature 마다 자기 것을 두면 상속 대상이 갈려 어떤 feature 는 501,
어떤 feature 는 500 을 답하게 됩니다. 이 파일은 **지금 만들지 않습니다** —
현재 저장소에는 정의도 사용처도 없으며, 첫 계열 어댑터를 붙이는 작업(§4 5단계)
에서 함께 만듭니다.

## 4. Phase 1 — feature × 계열마다 반복하는 8단계

**순서 자체가 규약입니다.** 계약이 확정되기 전에 mock 을 쓰면 계약이 mock 을
따라가고, 스키마를 적기 전에 mock 을 쓰면 그 mock 이 스키마의 원천 행세를
합니다.

| # | 단계 | 산출물 | 규칙 |
| --- | --- | --- | --- |
| 1 | 계약 확인 | `<feature>/contracts.py` | 계열별로 나누지 않습니다. 새 계열이 채우지 못하는 필드는 계약을 쪼개는 대신 null 규약(`""` / `None`)을 계약에 적습니다 |
| 2 | 스키마 기록 | `docs/datatables/<source>.txt` | 소스 이름과 스키마는 이 단계에서 확정합니다. 확인 전이면 전부 `OFFICE-VERIFY` 로 표기합니다 |
| 3 | mock 작성 | `providers/<family>/mock.py` | `sem_list` 의 해당 `vendor_nm` row 에서 **파생**합니다. 장비 목록을 독립 생성하지 않습니다 |
| 4 | 템플릿 작성 | `providers/<family>/office_example.py` | 추적되는 템플릿. 사무실에서 `cp` 할 대상입니다 |
| 5 | 디스패처 배선 | `providers/{mock,office_example}.py` 의 `_adapter()` | 두 파일 모두 feature 레벨에 남깁니다. **501 정책은 `office_example.py` 쪽만** — `mock.py` 는 3단계에서 이미 만든 `<family>/mock.py` 를 해석할 뿐입니다. 양쪽 다 `exc.name` 가드 유지 (§3.4) |
| 6 | 문서 갱신 | `<feature>/MIGRATION.md` | 엔드포인트 · 계약 · mock 동작 · 오피스 소스 4항목 |
| 7 | 테스트 | `tests/test_contract.py`, `tests/test_office_template.py` | 새 계열을 파라미터로 추가합니다 |
| 8 | 사무실 연결 | `cp office_example.py office.py` | 이 복사가 곧 스위치입니다. `GET /api/health/providers` 로 확인합니다 |

AMAT 계열의 오피스 키 이름과 스키마는 **아직 아무것도 알려지지 않았습니다.**
2단계에서 추측한 이름을 사실처럼 적지 말고 `OFFICE-VERIFY` 로 표기합니다.

## 5. 불변식 세 가지

### 5.1 명부는 하나입니다

어떤 계열의 어떤 feature 든 장비 identity 는 `sem_list` 에서만 옵니다.
`eqp_id` 나 모델 코드 목록을 파싱해 계열을 판정하는 코드는 금지입니다.

근거는 사고입니다. `back_dev_home/ebeam/_tool_specs.py` 의 모듈 docstring 에
기록되어 있듯, `eqp_models` 를 분류기로 쓴 결과 — 그 목록은 mock 이 그럴듯한
row 를 만들려고 지어낸 코드 모음입니다 — 목록에 없던 **실장비 8대가 조용히
사라졌습니다**(2026-07-24). 필터링되어 비워진 결과도 유효한 응답이므로 아무
오류도 나지 않았습니다. `eqp_prefixes` — **`eqp_id` 의 접두사** — 도 분류기가
아닙니다. `MCD` 하나가 CD-SEM · HV-SEM · VeritySEM · Provision 에 걸쳐 있어
장비 계열을 담고 있지 않기 때문입니다.

계열은 `sem_list` row 의 `eqp_model_cd` 를 `model_to_tool_type()` 에 넣어
판정합니다. 이 함수 역시 접두사로 판정하지만, 그 접두사는 `eqp_id` 가 아니라
**모델 코드의 시리즈 접두사**입니다(`_tool_specs.py` 의
`_TOOL_TYPE_BY_PREFIX` — `CG`/`GT`/`TP`/`VERITYSEM`/`PROVISION`). 두 접두사는
이름만 같을 뿐 다른 것이며, 금지되는 것은 앞의 것입니다.

### 5.2 사무실 DB 사실은 두 곳에 기록합니다

사무실 DB 에 대해 새로 알게 된 것 — 키 이름, 인덱스 alias, 필드, 값 규약,
커버리지, 함정 — 은 **같은 변경 안에서** 두 곳에 적습니다.

1. `docs/datatables/<source>.txt` — 스키마의 진실 원천
2. 해당 feature 의 `providers/<family>/mock.py` docstring

한쪽만 갱신하는 것이 피해야 할 실패 모양입니다. 문서는 어댑터를 쓸 때 읽히지만,
**모든 홈 세션이 실제로 실행하는 것은 `mock.py`** 입니다. 한쪽에만 있는 사실은
다음 홈 세션이 반박하는 사실입니다.

출처 표기는 `office 확인 YYYY-MM-DD` · `user-confirmed` · `OFFICE-VERIFY` 중
하나를 붙입니다. 추측은 피할 대상이 아니라 **표시할 대상**입니다.

### 5.3 없는 것은 없다고 말합니다

어댑터 미작성의 응답은 빈 배열도, mock 데이터도 아닌 **501** 입니다(§3.4).
빈 배열은 "그 계열에는 데이터가 없다"는 거짓말이고, mock 폴백은 "이것이 사무실
데이터다"라는 더 나쁜 거짓말입니다. 둘 다 오류를 내지 않으므로 리뷰에서
발견되지 않습니다.

## 6. 함께 읽는 문서

| 문서 | 내용 |
| --- | --- |
| [`provider-selection.md`](provider-selection.md) | mode × readiness, site 감지, 환경 변수 우선순위 |
| [`office-data-adapters.md`](office-data-adapters.md) | 어댑터 구현 규칙과 피처별 연결 명세 |
| [`../datatables/README.md`](../datatables/README.md) | 스키마 문서의 방향 규칙과 출처 표기 |
| [`2026-08-09-ebeam-vendor-onboarding-design.md`](../superpowers/specs/2026-08-09-ebeam-vendor-onboarding-design.md) | 이 규약의 설계 근거 전문 |
