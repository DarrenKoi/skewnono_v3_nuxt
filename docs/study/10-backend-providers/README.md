# 10. Flask 백엔드와 Provider 경계

이 문서는 HTTP 요청이 백엔드 함수를 거쳐 데이터로 바뀌는 과정을 설명합니다. 프론트엔드 기초를 몰라도 Python 함수와 딕셔너리를 이해하면 시작할 수 있습니다. 먼저 [03-nuxt](../03-nuxt/README.md)의 API 요청·응답 흐름을 읽고, 다음에는 [13-testing](../13-testing/README.md)에서 경계를 검증합니다.

2026-10-03 기준 `backend/__init__.py`, `_runtime/{data_provider,site,office_registry}.py`, `sem_list/`와 provider 테스트를 확인했습니다. 원본 개발 환경은 Python 3.11.14, Flask 3.1.3입니다. `backend/requirements.txt`는 `Flask>=3.0` 같은 허용 범위를 적으며, 설치 버전을 고정한 lock 파일은 아닙니다. CI의 Python 3.14와 개발·회사 Python 3.11을 구분해야 합니다.


HTTP(Hypertext Transfer Protocol)는 요청·응답 규약, URL(Uniform Resource Locator)은 자원 주소, JSON(JavaScript Object Notation)은 텍스트 교환 형식입니다. API(Application Programming Interface)는 호출자와 제공자의 입출력 약속입니다. IP(Internet Protocol) 주소는 네트워크 호스트 주소입니다.

## 1. 기초: 서버는 요청을 함수에 연결합니다

브라우저가 `GET /api/sem-list`를 보내면 Flask는 URL과 HTTP 메서드에 맞는 함수를 찾습니다. 이 함수가 반환한 장비 목록을 JSON으로 보내면 브라우저가 표를 그립니다. JSON은 네트워크를 건너는 표현이고, Python 내부에서는 `list[dict]` 같은 값으로 다룹니다.

```text
브라우저 GET /api/sem-list
            |
            v
Flask routes.py: 입력 확인, 응답 상태, JSON
            |
            v
       data.py: 선택된 provider에 전달
            |
        +---+-------------------+
        |                       |
 providers/mock.py       providers/office.py
 가짜 장비 목록           회사 Redis 등의 실제 값
        |                       |
        +----- 같은 계약 -------+
                  |
          JSON -> 브라우저 표
```

집에서 회사 저장소에 접근하지 못해도 같은 URL과 같은 열 이름으로 UI를 개발할 수 있습니다. 회사에서는 데이터 어댑터를 준비하고 설정·파일 배치를 바꾸면 됩니다. 회사 운영은 사내 네트워크의 클라우드이며, 공개 인터넷 서비스 배포를 뜻하지 않습니다.

## 2. 용어: 어떤 파일이 무엇을 책임지는가

| 용어 | 초심자용 뜻 | 이 저장소의 예 |
| --- | --- | --- |
| Route / handler | 요청을 받을 주소와 그 요청을 처리하는 함수 | `sem_list/routes.py` |
| Blueprint | 관련 라우트를 묶고 앱에 등록할 묶음 | `Blueprint("sem_list", __name__)` |
| App factory | 설정과 라우트를 합쳐 Flask 앱을 만드는 함수 | `backend.create_app()` |
| Contract | 두 데이터 소스가 반환해야 하는 공통 모양 | `sem_list/contracts.py` |
| Dispatcher | 요청을 어느 구현에 전달할지 정하는 얇은 함수 | `sem_list/data.py` |
| Provider / adapter | 실제 데이터를 읽고 계약 모양으로 만드는 구현 | `providers/mock.py`, `office.py` |
| Mock | 개발·테스트용 재현 가능한 가짜 데이터 | 고정 시드로 만든 장비 목록 |
| Lazy import | 모듈을 처음부터 읽지 않고 필요한 함수 실행 때 읽는 방식 | `get_sem_list()` 안의 import |

이 구조는 Ports & Adapters와 연결해 이해할 수 있습니다. Port는 `get_sem_list() -> list[SemListRow]`라는 약속이고, adapter는 그 약속을 mock 또는 회사 저장소로 구현합니다. 이름을 외우는 것보다 “외부 저장소가 달라도 호출부는 같은 함수를 사용한다”는 경계를 이해하는 편이 중요합니다.

`TypedDict`는 딕셔너리 키·값 타입을 설명합니다. 실행 중 JSON을 자동 검증하거나 DB 값을 자동 정규화하지 않습니다. 어댑터의 정규화와 계약 테스트가 별도로 필요합니다.

## 3. 현재 구현: 선택부터 응답까지

### 3.1 배포 위치와 데이터 소스를 구분합니다

배포 위치 판단인 `is_cloud()`는 인증 provider 같은 실행 환경을 정합니다. 데이터 선택은 `_runtime/data_provider.py`가 담당합니다. 사이트 판별이 데이터 mode의 기본값에 영향을 주지만, 회사 위치에서 mock을 쓰는 것은 가능합니다.

데이터 선택은 **mode와 readiness** 두 질문으로 나뉩니다.

- Mode: 이 프로세스가 office 데이터를 사용하려는가입니다.
- Readiness: 해당 기능의 `providers/office.py`가 실제로 있는가입니다.

현재 선택 순서는 다음과 같습니다.

1. `SKEWNONO_<FEATURE>_PROVIDER`가 있으면 해당 기능을 명시적으로 선택합니다.
2. 기능 override가 없으면 `SKEWNONO_DATA_PROVIDER`로 mode를 정합니다.
3. 전역 mode도 없으면 `detect_site()`의 결과를 사용합니다. 회사는 office, 집·알 수 없는 호스트는 mock입니다.
4. office mode이고 해당 기능의 `office.py`가 있을 때 office가 선택됩니다. 그 외에는 mock입니다.

| 기능 override | 전역 mode | 해당 `office.py` | 결과 |
| --- | --- | --- | --- |
| 없음 | mock | 있음 또는 없음 | mock |
| 없음 | office | 있음 | office |
| 없음 | office | 없음 | mock |
| office | mock 또는 office | 있음 | office |
| office | mock 또는 office | 없음 | `RuntimeError` |
| mock | office | 있음 | mock |

**전역 `office`는 모든 기능의 office 사용을 강제하지 않습니다.** 기능별 준비 여부를 확인합니다. 반면 명시적인 기능 `office` 요청은 어댑터가 없을 때 mock으로 숨기지 않고 복사 명령을 담은 오류로 실패합니다. 전역 `mock`은 기능 override가 없는 기능들을 mock으로 돌리므로, 전체를 mock으로 확인하려면 남아 있는 기능별 `office` override도 점검해야 합니다.

사이트 확인 순서는 `SKEWNONO_SITE=home|office`, 사내 cloud 배포 경로, 호스트 이름입니다. 집 호스트, `pc` 접두사 회사 PC, `SKEWNONO_OFFICE_HOSTNAMES` 목록을 확인합니다. 모르는 호스트는 회사로 추측하지 않습니다. provider 오타와 잘못된 사이트 값은 오류입니다. 기능 이름 `sem-list`와 `sem_list`는 같은 정규 키로 해석됩니다.

부팅 때 `validate_env()`가 명시적 office 선택과 기능 간 의존성을 확인합니다. `storage`, `pm_planning`, `tttm`가 office인데 `sem_list`가 mock이면 부팅을 거부합니다. 실제 IP·장비 ID와 가짜 목록을 조인하면 HTTP 200이면서 빈 표가 나올 수 있기 때문입니다. 최종 선택과 이유는 부팅 로그 및 `/api/health/providers`에서 확인합니다. 세부 규칙은 [provider-selection](../../back-end/provider-selection.md)에 있습니다.

### 3.2 `sem_list`로 파일 경계를 읽습니다

```text
backend/sem_list/
├── __init__.py            # routes의 bp를 패키지에서 다시 노출
├── routes.py              # URL, 응답, 입력 경계
├── contracts.py           # SemListRow 등 공통 반환 타입
├── data.py                # 안정적인 dispatcher; 교체할 파일이 아님
├── MIGRATION.md           # 회사 연결·검증 절차
├── tests/
└── providers/
    ├── __init__.py
    ├── mock.py
    └── office_example.py  # git에 추적하는 템플릿
        office.py          # 회사 복사본; gitignore
```

라우트는 `data.py`의 함수를 사용합니다. `data.py`는 `get_data_provider("sem_list")`를 확인하고, 함수 내부에서 선택된 어댑터만 import합니다. 회사 어댑터가 집에 없어도 mock 경로가 그 모듈을 읽지 않습니다. 이는 office 전용 의존성을 불필요하게 실행하지 않는 경계이지, “모든 회사 관련 패키지가 requirements에서 빠져 있다”는 뜻은 아닙니다.

`SemListRow`는 `eqp_id`, `eqp_ip`, `vendor_nm`, `available`, `version` 등을 가집니다. `vendor_nm`은 `HITACHI|AMAT`, `available`은 `On|Off`, 버전 미상은 빈 문자열입니다. `updt_dt`는 이름만 보면 갱신 시각 같지만 현재 계약은 장비 최초 반입 시각입니다. 미연결 장비는 별도 `PendingToolRow`이며, 아직 존재하지 않는 `available`·`version`을 가짜로 채우지 않습니다.

mock은 고정 시드의 `random.Random`을 사용하여 다시 실행해도 같은 표본을 제공합니다. 계약이 같다는 것은 실제 장비 값·행 수까지 같다는 뜻이 아닙니다. mock 생성 규칙과 회사 자료에서 확인된 사실, 아직 가정인 `OFFICE-VERIFY`를 구분합니다.

회사 `sem_list` 템플릿은 Redis의 fleet와 version DataFrame을 읽어 `eqp_ip`로 LEFT 조인합니다. 오른쪽 버전 테이블의 중복 IP를 먼저 정리해서 장비 행이 증식하지 않게 합니다. 버전이 없어도 장비 자체는 남기고 빈 문자열로 정규화합니다. parquet 디코딩과 pandas 결측값 처리는 어댑터의 일입니다. 라우트와 브라우저는 Redis 직렬화 포맷을 알 필요가 없습니다.

### 3.3 Blueprint는 발견과 import를 모두 이해해야 합니다

`backend/__init__.py`는 `routes.py`를 재귀 검색합니다. 다만 실제 import 대상은 `backend.sem_list.routes`가 아니라 **부모 패키지 `backend.sem_list`**입니다. 이 패키지에서 `bp`를 가져와 `/api` 아래에 등록합니다. `backend/sem_list/__init__.py`가 다음 역할을 합니다.

```python
from backend.sem_list.routes import bp

__all__ = ["bp"]
```

따라서 새 기능에 `routes.py` 안의 `bp`만 만들고 패키지에서 내보내지 않으면 현재 factory가 등록하지 못합니다. `routes.py`는 발견 표식이고, 패키지의 `bp` export가 등록 계약입니다. 등록된 URL은 `/api` prefix와 라우트 경로의 조합입니다. Blueprint 이름은 Python endpoint 이름에 영향을 주며, 이름 자체가 URL을 만들지는 않습니다. [Flask 3.1 Blueprint 공식 설명](https://flask.palletsprojects.com/en/stable/blueprints/)과 저장소의 자동 발견 규칙을 구분합니다.

경로 조각이 `_`로 시작하는 공용 폴더는 자동 발견에서 제외합니다. 일반 기능의 import·`bp` 오류는 부팅 실패로 드러납니다. `backend/contrib/<slug>/`만 예외로 실패한 기능을 건너뛰고 `SKEWNONO_CONTRIB_FAILED` 및 로그에 기록합니다.

e-beam 기능은 `backend/ebeam/storage/`, `hardware/`, `tttm/`처럼 평평하게 배치합니다. 예전 vendor 중간 폴더를 기준으로 찾지 않습니다. tool family는 `providers/<family>/` 축이며, 기능 이름이 중복되면 registry가 거부합니다.

### 3.4 예외도 기존 경계를 먼저 읽습니다

`chat`은 일반 provider 환경변수 표의 사례가 아닙니다. 답변 경로는 `chat/answer/data.py`와 `rag_ready()`가 사내 `_rag` 체크아웃·인덱스 파일 준비 여부로 정합니다. readiness는 무거운 모델 모듈 import 성공을 검사하는 것과 다릅니다. 답변 엔진의 모델·프롬프트는 RAG 코드의 책임이고, 스레드 저장은 SQLite입니다.

`msr_file`은 상세 데이터와 이미지 진입점을 같은 dispatcher 뒤에 둡니다. `office_example.py`의 미구현 함수는 실제 연결 완료의 증거가 아닙니다. 회사 상세 메타데이터 계약을 mock이 지어내도 안 됩니다. 각 기능의 `MIGRATION.md`를 읽고 개별 연결 범위를 확인해야 합니다.

## 4. 선택 이유와 한계

라우트·계약을 한 벌만 유지하면 두 환경의 URL과 응답 차이가 줄어듭니다. 지연 import와 파일 준비 여부는 회사에서 기능을 하나씩 연결할 수 있게 합니다. `data.py`를 안정적으로 유지하고 실제 교체는 `providers/`에서 수행합니다.

`office_example.py`는 공유 가능한 구현 템플릿이고 `office.py`는 회사 복사본입니다. gitignore는 Git 충돌·노출 범위를 줄이지만 보안 정책 전체를 대신하지 않습니다. 템플릿이 바뀌어도 기존 복사본이 자동 갱신되지는 않습니다. 부팅 로그의 `STALE office.py`와 [어댑터 동기화 절차](../../back-end/provider-selection.md)를 확인해야 합니다.

이 경계가 보장하는 것은 선택·반환 모양입니다. 사내 Redis/OpenSearch 접근, 인증·권한, 최신 데이터, 실제 스키마는 집 mock 테스트만으로 증명하지 못합니다. 회사 DB 사실을 새로 알면 `docs/datatables/`의 해당 스키마와 mock 설명·생성 규칙 두 곳에 반영해야 합니다.

## 5. 흔한 실수와 읽는 순서

- 전역 office를 기능 전체 강제 전환으로 이해하면 준비하지 않은 기능이 mock인 이유를 놓칩니다. 선택 결과와 `reason`을 확인합니다.
- `office.py`가 있다는 사실을 연결 정상으로 해석하면 안 됩니다. 함수 실행과 실제 소스 검증이 별도로 필요합니다.
- routes에서 DB 드라이버를 직접 import하면 계약 뒤의 교체 경계가 깨집니다.
- 새 기능에서 패키지 `bp` export를 빠뜨리면 현재 자동 발견이 실패합니다.
- 템플릿 변경 뒤 회사 복사본을 그대로 두면 200 응답으로 오래된 동작이 남습니다.
- `TypedDict`만으로 런타임 검증이 된다고 생각하면 결측·중복·단위 문제를 놓칩니다.

문제가 생기면 `routes.py → data.py → get_data_provider() → 선택된 provider → contracts.py → tests/` 순서로 읽습니다. 호출부에서 땜질하기 전에 어느 경계에서 잘못된 값을 만들었는지 찾습니다.

## 6. 안전한 실습

실습은 저장소 루트에서 수행합니다. 회사 DB 호출이나 `office.py` 생성 없이 선택 규칙부터 확인합니다. 원본 개발 환경 `.venv`를 사용하며, 별도 worktree에는 `.venv`가 없을 수 있습니다.

```bash
SKEWNONO_DATA_PROVIDER=mock SKEWNONO_SEM_LIST_PROVIDER=mock \
  .venv/bin/python -c 'from backend._runtime.data_provider import get_data_provider; print(get_data_provider("sem-list"))'
```

기대 출력은 `mock`입니다. 두 환경변수는 이 명령 프로세스에만 적용됩니다. 기존 `.env`를 수정하거나 shell 전체에 `export`하지 않습니다.

```bash
.venv/bin/python -m pytest backend/_runtime/tests/test_site_provider.py -q
.venv/bin/python -m pytest backend/sem_list -q
```

첫 명령은 사이트·mode·선택 경계를, 둘째는 기능 계약을 확인합니다. 테스트가 임시 환경·가짜 client를 쓰는지 읽고 통과가 보장하는 범위를 설명해 봅니다. 다음 질문에 답하면 이 챕터의 핵심을 이해한 것입니다.

1. 전역 office인데 `sem_list/office.py`가 없다면 결과는 무엇입니까?
2. 기능 override가 office인데 파일이 없다면 앞 사례와 어떻게 다릅니까?
3. Blueprint가 routes에만 있고 패키지에서 보이지 않으면 왜 등록에 실패합니까?
4. LEFT 조인에서 버전 없는 장비를 제거하면 어떤 정보가 사라집니까?

회사 연결은 별도 단계입니다. 아래 명령은 학습 예시이며 집 실습에서 실행할 필요가 없습니다. 기존 회사 복사본을 무작정 덮어쓰지 않고 해당 `MIGRATION.md`와 동기화 절차를 먼저 확인합니다.

```bash
# 아직 복사본이 없는 회사 기능을 준비하는 경우
cp backend/sem_list/providers/office_example.py backend/sem_list/providers/office.py
SKEWNONO_SEM_LIST_PROVIDER=office .venv/bin/python -m pytest backend/sem_list -q
```

office 선택이 확인되더라도 테스트가 DB를 대체하면 실제 연결 증거는 아닙니다. 회사 서비스에서 실제 응답·로그·계약을 함께 확인합니다.
