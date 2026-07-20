# 10. 백엔드 Provider 아키텍처 (mock ↔ office)

이 문서는 프론트엔드가 아니라 **`back_dev_home/`(Flask 백엔드)의 핵심 아키텍처**를 다룹니다. 백엔드 개발자에게는 가장 익숙한 영역이면서, 이 프로젝트에서 가장 많이 반복되는 패턴이므로 먼저 확실히 이해해 두는 것이 좋습니다.

한 줄 요약: **"한 벌의 라우트/계약을 두고, 데이터 소스(집의 mock ↔ 회사의 office)만 런타임에 갈아끼운다."** 이것이 CLAUDE.md가 말하는 "설정 변경만으로 Phase를 바꾼다"의 백엔드 구현입니다.

이 패턴은 소프트웨어 설계에서 **Ports & Adapters**(육각형 아키텍처)로 불립니다.

- **Port** = 라우트/계약이 기대하는 함수 시그니처 (`get_sem_list() -> list[SemListRow]`)
- **Adapter** = 그 시그니처를 실제 데이터 소스로 구현한 것 (`providers/mock.py`, `providers/office.py`)

## 1. 두 개의 독립된 축을 구분하라

가장 먼저 잡아야 할 개념. 이 시스템에는 **서로 다른 두 개의 축**이 있고, 일부러 분리되어 있습니다.

| 축 | 무엇을 결정하나 | 어떻게 선택되나 |
| --- | --- | --- |
| **배포 위치** (deployment location) | 집인가 / 사내 클라우드인가 | `is_cloud()` → `LocalIdentityProvider` vs `CloudIdentityProvider` |
| **데이터 소스** (data source) | mock dict인가 / 실제 Redis·OpenSearch인가 | `SKEWNONO_<FEATURE>_PROVIDER` 환경변수 |

`_runtime/data_provider.py`의 docstring이 이 원칙을 명시합니다: *"The deployment location and the data source are separate decisions."*

**왜 분리하나?** 회사 노트북에서 실제 Redis를 붙이지 않고 mock으로 UI만 확인하고 싶을 수도 있고, 반대로 집에서 인증 로직(cloud identity)을 테스트하고 싶을 수도 있습니다. 두 축이 엮여 있으면 이런 조합이 불가능합니다.

## 2. Provider 셀렉터 — `_runtime/data_provider.py`

데이터 소스 축의 심장. 전체가 35줄뿐입니다.

```python
DataProvider = Literal["mock", "office"]

_GLOBAL_ENV = "SKEWNONO_DATA_PROVIDER"
_VALID_PROVIDERS = frozenset({"mock", "office"})


def _feature_env_name(feature: str) -> str:
    normalized = feature.strip().upper().replace("-", "_")
    return f"SKEWNONO_{normalized}_PROVIDER"


def get_data_provider(feature: str) -> DataProvider:
    """Return a feature override, the global provider, or the home-safe default."""
    feature_env = _feature_env_name(feature)
    raw = os.environ.get(feature_env) or os.environ.get(_GLOBAL_ENV) or "mock"
    provider = raw.strip().lower()

    if provider not in _VALID_PROVIDERS:
        raise RuntimeError(
            f"Invalid data provider {raw!r} for {feature!r}. "
            f"Set {feature_env} or {_GLOBAL_ENV} to 'mock' or 'office'."
        )

    return cast(DataProvider, provider)
```

우선순위 (fallback 체인):

1. **기능별 override** — `SKEWNONO_SEM_LIST_PROVIDER` (기능마다 개별 제어)
2. **전역** — `SKEWNONO_DATA_PROVIDER` (한 방에 전부 전환)
3. **기본값** — `"mock"` (집에서 안전한 기본값. env를 아무것도 안 걸면 항상 mock)

**설계 관찰**:

- `"mock"`이 기본값이라 **집에서는 아무 설정 없이 그냥 돈다**. 실수로 office 의존성(redis 등)을 건드릴 일이 없습니다.
- 잘못된 값(`"redis"` 같은 오타)은 조용히 넘어가지 않고 `RuntimeError`로 **즉시 터집니다**. 애매한 fallback보다 큰 소리로 실패하는 편이 낫습니다.
- 기능별 override가 전역보다 우선하므로, "전부 office인데 sem_list만 mock으로 격리" 같은 세밀한 조합이 가능합니다.

## 3. 기능 하나의 해부 — `sem_list/`

feature-sliced 레이아웃. 각 기능 폴더는 아래 구조를 그대로 따릅니다.

```text
back_dev_home/sem_list/
├── __init__.py
├── contracts.py            # 안정적인 반환 계약 (SemListRow TypedDict)
├── data.py                 # ★ SWAP SURFACE (디스패처)
├── routes.py               # Blueprint. .data만 import
├── MIGRATION.md            # office 어댑터 구현 지침
├── __fixtures__/
├── tests/
└── providers/
    ├── __init__.py         # 일부러 아무 provider도 import 안 함
    ├── mock.py             # Phase 1 결정론적 어댑터
    └── office_example.py   # 추적되는 스켈레톤 (cp → office.py)
```

### 3.1 `routes.py` — Phase 간 절대 안 바뀌는 부분

```python
from flask import Blueprint, jsonify

from back_dev_home.sem_list.data import get_sem_list

bp = Blueprint("sem_list", __name__)


@bp.get("/sem-list")
def sem_list():
    rows = get_sem_list()
    return jsonify(rows)
```

라우트는 `.data`에서 `get_sem_list`만 가져옵니다. `providers/`를 직접 import하지 **않습니다.** 그래서 이 파일은 mock/office 어느 Phase에서도 **한 글자도 안 바뀝니다.** 교체는 전부 `data.py` 뒤에서 일어납니다.

### 3.2 `data.py` — 디스패처 (교체 지점)

```python
"""SWAP SURFACE for the SEM equipment list.

Routes import only this module. The selected adapter lives in
``providers/mock.py`` or ``providers/office.py`` and must return the shared
``SemListRow`` contract.
"""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.sem_list.contracts import SemListRow

__all__ = ["SemListRow", "get_sem_list"]


def get_sem_list() -> list[SemListRow]:
    if get_data_provider("sem_list") == "office":
        from back_dev_home.sem_list.providers.office import (
            get_sem_list as load_sem_list,
        )
    else:
        from back_dev_home.sem_list.providers.mock import (
            get_sem_list as load_sem_list,
        )

    return load_sem_list()
```

핵심 두 가지:

1. **`get_data_provider("sem_list")`로 축을 읽고** 분기합니다.
2. **함수 내부 지연 import** (`from ...providers.office import ...`가 함수 안에 있음). 이게 의도적입니다 — office 어댑터는 `redis`, `pandas`, `pyarrow` 같은 무거운 의존성을 쓰는데, 이걸 모듈 최상단에서 import하면 **집에서 mock만 돌릴 때도 그 패키지들이 설치돼 있어야** 합니다. 지연 import + 빈 `providers/__init__.py` 덕분에, office가 선택될 때만 그 코드에 도달하고, gitignore된 `office.py`가 집에는 아예 없어도 됩니다.

> **백엔드 관점 비유**: `data.py`는 Flask의 라우트와 실제 저장소 사이에 낀 **얇은 서비스 레이어**입니다. 라우트는 "장비 목록 줘"라고만 하고, 그게 in-memory dict에서 오는지 Redis에서 오는지는 이 레이어가 숨깁니다. 의존성 주입(DI)을 환경변수 + 지연 import로 가난하게 구현한 셈입니다.

### 3.3 `contracts.py` — 두 어댑터가 반드시 반환해야 하는 모양

```python
class SemListRow(TypedDict):
    fac_id: str
    eqp_id: str
    eqp_model_cd: str
    eqp_grp_id: str
    vendor_nm: Literal["HITACHI", "AMAT"]
    eqp_ip: str
    fab_name: str
    updt_dt: str
    available: Literal["On", "Off"]
    version: str
```

이것이 **Port의 타입 계약**입니다. mock이든 office든, 결국 `list[SemListRow]`를 돌려줘야 합니다. 프론트엔드의 `SemListRow` 인터페이스(TS)와 이 TypedDict가 서로 거울처럼 대응됩니다.

> "office가 mock을 닮게 만든다"는 말은 **데이터 값을 똑같이 만들라는 게 아니라 이 계약(shape)을 맞추라는 뜻**입니다. office는 실제 장비를, mock은 가짜 300대를 반환하지만, 둘 다 `SemListRow` 리스트여야 합니다.

### 3.4 `providers/mock.py` — 집(Phase 1) 어댑터

```python
def _generate_rows(n_rows: int = 300, seed: int = 42) -> list[SemListRow]:
    rng = random.Random(seed)
    now = datetime(2026, 4, 19, tzinfo=timezone.utc)
    rows: list[SemListRow] = []
    ...
        rows.append(SemListRow(
            fac_id=fac_id,
            eqp_id=eqp_id,
            ...
            version="" if rng.random() < 0.05 else f"{rng.randint(1, 3)}{rng.choice('AB')}"
        ))
    return rows


def get_sem_list() -> list[SemListRow]:
    return _generate_rows()
```

**`random.Random(42)`로 시드를 고정**한 것이 포인트입니다. mock은 매번 **똑같은 300대 fleet**을 만듭니다. 결정론적이라 프론트엔드 개발·테스트·스크린샷이 재현 가능합니다. (약 5%는 version을 빈 문자열로 두어 "버전 미상" 케이스도 UI가 처리하게 만듭니다.)

### 3.5 `providers/office_example.py` — 회사(Phase 2/3) 어댑터 스켈레톤

```python
def _attach_version(fleet: pd.DataFrame, versions: pd.DataFrame) -> pd.DataFrame:
    """LEFT-merge the version string onto the fleet by ``eqp_ip``."""
    ...
    right = versions[[_MERGE_KEY, "version"]].drop_duplicates(
        subset=[_MERGE_KEY], keep="last"
    )
    return fleet.merge(right, on=_MERGE_KEY, how="left")


def get_sem_list() -> list[SemListRow]:
    client = _redis_client()
    fleet = _load_dataframe(client, _REDIS_KEY)
    versions = _load_dataframe(client, _VERSION_KEY)
    fleet = _attach_version(fleet, versions)
    if fleet.empty:
        return []
    return _normalize(fleet)
```

office 어댑터는 **소스 포맷의 모든 지저분함을 흡수**합니다.

- Redis에 두 개의 키(`v3_df_sem_list` = fleet, `v3_df_sem_version` = `[eqp_ip, version]`)가 각각 **parquet으로 직렬화된 DataFrame**으로 저장돼 있음.
- parquet magic byte(`PAR1`) 감지, UTF-8 디코딩, `NaN → ""` 정규화, vendor/available 값 정규화.
- 두 DataFrame을 `eqp_ip` 기준 **LEFT 조인**해서 version을 붙임.

이 모든 걸 어댑터가 처리하고 나면, 라우트와 프론트엔드는 소스가 Redis + parquet + pandas였다는 사실을 **전혀 모릅니다.** 이것이 좋은 어댑터의 정의입니다 — 경계 안쪽의 복잡함이 밖으로 새지 않습니다.

> 이 `sem_list`가 이 프로젝트에서 **회사 쪽에서 실제로 라이브 검증된 첫 기능**입니다(2026-07-20).

## 4. `office_example.py` vs `office.py` 컨벤션

이 저장소는 **집과 회사가 직접 sync할 수 없습니다**(git 워크스페이스가 분리됨). 그래서 다음 규칙을 씁니다.

```gitignore
# providers/office_example.py -> providers/office.py, then implemented at the
# office. Never tracked, so `git pull` at the office can never conflict on it.
back_dev_home/**/providers/office.py
```

- `office_example.py` — **git에 추적되는 스켈레톤/템플릿**. 함수 시그니처와 구현 힌트가 들어 있음.
- `office.py` — **gitignore됨.** 회사에서 `cp office_example.py office.py` 한 뒤 그 안을 실제 구현으로 채움.

**왜 이렇게?** 만약 `office.py`가 추적된다면, 회사에서 실제 Redis 접속 코드를 짜 넣고 커밋한 뒤 집에서 `git pull` 할 때 **매번 충돌**합니다(또는 회사 비밀이 집 저장소로 흘러 들어옵니다). `office.py`를 ignore하면 `git pull`이 절대 이 파일에서 충돌하지 않고, 회사 전용 접속 로직이 공용 저장소에 노출되지 않습니다.

집 저장소에는 `office.py`가 아예 존재하지 않아도 됩니다. `data.py`의 지연 import는 env가 office를 고를 때만 그 줄에 도달하기 때문입니다.

## 5. `MIGRATION.md` — office 어댑터가 지켜야 할 규칙

각 기능 폴더의 `MIGRATION.md`가 회사에서 무엇을 해야 하는지 알려줍니다. `sem_list` 기준 요약:

1. **먼저 복사, 그다음 복사본만 수정** — `cp providers/office_example.py providers/office.py`.
2. **`providers/office.py`만 건드린다.** `routes.py`, `data.py`, `office_example.py`, `mock.py`, `contracts.py`, `tests/`는 절대 수정 금지.
3. **반환 전에 모든 결과를 `contracts.py` 모양으로 정규화한다.**
4. **완료 기준 = Verify 명령이 green.**

Verify 명령 (repo 루트에서):

```bash
.venv/bin/python -m back_dev_home.sem_list.providers.office
SKEWNONO_SEM_LIST_PROVIDER=office .venv/bin/pytest back_dev_home/sem_list
```

접속 정보는 `back_dev_home/.env`의 `REDIS_HOST`/`REDIS_PORT`/`REDIS_PASSWORD`에서 읽습니다.

## 6. 앱 팩토리 — `back_dev_home/__init__.py`

Blueprint를 **자동 발견**하는 방식이 인상적입니다. 각 기능의 `routes.py`를 손으로 등록하지 않습니다.

```python
def create_app() -> Flask:
    load_dotenv(Path(__file__).parent / ".env")
    app = Flask(__name__)
    app.secret_key = os.environ.get("SKEWNONO_SECRET_KEY", "dev-only-not-for-prod")

    CORS(
        app,
        resources={r"/api/*": {"origins": ["http://localhost:3100"]}},
        supports_credentials=True,
    )
    _install_json_error_handlers(app)

    provider = CloudIdentityProvider() if is_cloud() else LocalIdentityProvider()
    install_identity_middleware(app, provider)
    install_activity_logging(app)
    ...
    package_root = Path(__file__).parent
    for routes_file in sorted(package_root.rglob("routes.py")):
        rel_parts = routes_file.relative_to(package_root).parts[:-1]
        if any(part.startswith("_") for part in rel_parts):
            continue
        module_path = ".".join((__name__, *rel_parts))
        module = importlib.import_module(module_path)
        bp = getattr(module, "bp", None)
        if not isinstance(bp, Blueprint):
            raise RuntimeError(
                f"{module_path} has routes.py but does not export a Blueprint named 'bp'"
            )
        app.register_blueprint(bp, url_prefix="/api")
```

동작:

- `rglob("routes.py")`로 패키지 전체를 훑어 **모든 `routes.py`를 찾아** 그 안의 `bp` Blueprint를 `/api` 하위에 등록.
- 경로 조각이 `_`로 시작하는 폴더(`_auth`, `_runtime`, `_spa`, `_core` 등)는 **건너뜀** — 이들은 기능이 아니라 공용 인프라이므로.
- `bp`를 export하지 않으면 **큰 소리로 실패**(`RuntimeError`). "규칙을 안 지킨 기능"이 조용히 누락되지 않습니다.

**교훈**: 새 기능 추가 = 폴더 하나 만들고 그 안에 `routes.py`(+`bp`) 두면 끝. 중앙 등록 파일을 손댈 필요가 없습니다. 이것이 "대규모 리팩터링 없이 페이지/기능을 점진적으로 추가"라는 CLAUDE.md 목표의 실현입니다.

> `is_cloud()`로 identity provider를 고르는 부분이 §1에서 말한 **배포 위치 축**입니다. 데이터 소스 축(`get_data_provider`)과 완전히 별개로 동작합니다.

## 7. 교체 지점이 둘 이상인 기능

대부분의 기능은 교체 지점이 하나(`data.py`)지만, 일부는 여러 개입니다. `MIGRATION.md`를 항상 확인하세요.

### `chat` — 저장소 seam + LLM 게이트웨이 seam (독립된 두 축)

- **저장소 교체**: `chat/data.py`가 `get_data_provider("chat")`로 mock/office를 골라 스레드 CRUD(`create_thread`, `append_message`, `purge_expired` 등)를 디스패치. office 저장소는 아직 stub.
- **LLM 교체는 별도 축**: mock/office가 아니라 **env 기반 설정**입니다. `chat/config.py` — *"Swaps by env only — no code change per phase."* `chat/llm.py`는 *"Identical code across phases"*인 stateless OpenAI 호환 클라이언트. 게이트웨이는 `CHAT_BASE_URL`/`CHAT_API_KEY`/`CHAT_MODELS`(기본 `https://openrouter.ai/api/v1`)로 선택하고, egress는 `chat/guard.py`가 제한합니다.

### `msr_file` — 데이터 seam + 이미지 seam (하나의 디스패처 뒤 두 진입점)

- `msr_file/data.py`가 `get_msr_file`(상세/rows)과 `get_msr_image`(이미지 서빙) 두 함수를 같은 `_provider()`로 라우팅.
- 주의: **추적되는 `office_example.py`는 현재 미구현 stub**입니다(둘 다 `NotImplementedError`). 다만 docstring이 office 어댑터가 추가로 채워야 할 **정규 메타데이터 계약**(`site_layout_hash`, `recipe_revision`, `coordinate_transform_version`, `sequence_timestamp`)을 강제하며, **mock은 이 값들을 지어내면 안 됩니다**(`tests/test_contract.py`가 강제). 구체적 저장 백엔드(FTP/MinIO 등)는 회사 쪽 `office.py`에서 결정됩니다.

## 8. 현재 기능 목록

`data.py` 디스패처를 갖춘 기능(총 20개, 모두 `office_example.py` 보유):

- 최상위: `access_control`, `activity`, `admin_logs`, `afm`, `announcements`, `api_tokens`, `chat`, `health`, `meas_hist`, `msr_file`, `sem_list`
- `ebeam/` 아래: `ebeam/cdsem/device_statistics`, `ebeam/hitachi/{fail_issue, hardware, lateral_recipe, pm_planning, recipe_search, recipe_tat, skew, storage}`

## 9. 이 챕터의 큰 교훈

- **경계를 하나로 좁혀라.** 라우트·계약·테스트는 한 벌, 갈아끼우는 건 `providers/`의 어댑터 하나뿐.
- **두 개의 독립 축(배포 위치 / 데이터 소스)을 섞지 마라.** 각각 다른 스위치로 제어.
- **기본값은 가장 안전한 쪽(mock)으로.** 아무 설정 없이 집에서 그냥 돌아야 한다.
- **큰 소리로 실패하라.** 잘못된 provider 값, `bp` 누락은 조용히 넘기지 말고 즉시 RuntimeError.
- **어댑터가 소스의 지저분함을 흡수한다.** parquet·Redis·pandas가 경계 밖으로 새면 안 된다.
- **비밀/충돌 유발 파일은 gitignore하고, 추적되는 건 스켈레톤(`office_example.py`)만.**

## 10. 더 읽을거리

- 이 아키텍처의 이름: Ports & Adapters (Hexagonal Architecture, Alistair Cockburn)
- 각 기능의 `MIGRATION.md` — 회사에서 무엇을 채워야 하는지의 단일 진실 공급원
- 루트 `CLAUDE.md`의 "API Abstraction Layer" 절 — 이 문서의 상위 요약
