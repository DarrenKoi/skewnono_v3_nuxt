# Provider 선택 규칙

이 문서는 `back_dev_home/<feature>/providers/{mock,office}.py` 중 무엇이 실제로 응답을
만드는지가 어떻게 결정되는지를 설명합니다. adapter 구현 규칙은
[`docs/back-end/office-data-adapters.md`](office-data-adapters.md), 환경 간 전달 절차는
[`docs/swap-strategy.md`](../swap-strategy.md)가 기준입니다.

## 1. 두 개의 독립된 질문

provider 선택은 하나의 스위치가 아니라 **서로 독립된 두 질문**의 논리곱입니다.

| 질문 | 의미 | 판정 주체 |
| --- | --- | --- |
| Mode | 이 프로세스가 사무실에 있는가 | `SKEWNONO_DATA_PROVIDER`(`mock`\|`office`), 없으면 site 감지 |
| Readiness | 이 피처의 adapter가 작성되었는가 | `<feature>/providers/office.py` 파일의 존재 여부 |

두 조건이 **모두** 참일 때만 해당 피처가 사무실 데이터를 제공합니다. 따라서
`cp office_example.py office.py` 명령 하나가 adapter를 만드는 행위이자 그것을 켜는
행위입니다. 별도로 관리해야 하는 활성화 목록은 존재하지 않습니다.

Readiness 판정은 `_runtime/office_registry.py`가, mode 판정은
`_runtime/data_provider.py`가 담당합니다.

## 2. Site 감지

Mode를 환경 변수로 지정하지 않으면 `_runtime/site.py`가 아래 순서로 판정합니다.

| 순서 | 신호 | 결과 |
| --- | --- | --- |
| 1 | `SKEWNONO_SITE` (`home`\|`office`) | 명시적 override |
| 2 | Phase 3 클라우드 배포 경로 (`is_cloud()`) | office |
| 3 | 호스트명 — `PC*` 접두사 또는 `SKEWNONO_OFFICE_HOSTNAMES` | office |
| 4 | 그 외 (홈 Mac mini, 미상 호스트) | home |

2단계가 경로 기반인 이유는 VM 호스트명이 바뀌어도 운영 환경이 mock으로 되돌아가지
않게 하기 위함입니다. 미상 호스트를 home으로 두는 이유는 사무실 인프라의 존재를
가정하지 않는 쪽이 안전하기 때문입니다.

## 3. 환경 변수 우선순위

- `SKEWNONO_<FEATURE>_PROVIDER` — 피처 하나를 양방향으로 override합니다.
  adapter가 없는데 `=office`로 지정하면 부팅을 거부합니다. 지킬 수 없는 실데이터
  약속을 새벽에 mock으로 응답하는 것보다 기동 실패가 낫기 때문입니다.
- `SKEWNONO_DATA_PROVIDER=mock` — 인스턴스 전체 kill switch입니다.

실제로 무엇이 선택되었는지는 `GET /api/health/providers` 또는 부팅 로그로 확인합니다.

## 4. `/api/health/providers`의 예외

라우트는 원칙적으로 `from .data import ...`만 사용하며 phase에 따라 분기하지
않습니다. 단 하나의 예외가 `/api/health/providers`이며, 이 엔드포인트는 `_runtime`을
직접 읽습니다. **스왑 메커니즘 자체를 보고하는 엔드포인트가 그 메커니즘을 거치면,
정작 그것을 조회해야 하는 상황에서 잘못된 값을 보고할 수 있기 때문입니다.**

## 5. 복사본이 낡는 문제

`office.py`는 gitignore 대상이며 `office_example.py`의 복사본입니다. 따라서
`git pull`로 템플릿이 갱신되어도 실행 중인 adapter는 옛 코드 그대로 200을 계속
응답합니다.

`_runtime/office_template.py`가 이를 감지하여 사무실 인스턴스의 부팅 로그에
`STALE office.py: <feature> (copy of <sha>)` 형태로 보고합니다. 갱신 명령은
다음과 같습니다.

```bash
python -m scripts.sync_office_adapters <feature>
```

사내 수정이 들어간 복사본은 `EDITED`로 분류되어 보고 대상에서 제외되며,
`--force` 없이는 덮어쓰지 않습니다.

## 6. 스왑 표면이 둘 이상인 피처

일부 피처는 데이터 provider 외에 추가 스왑 지점을 가집니다.

| 피처 | 추가 스왑 표면 |
| --- | --- |
| `chat` | 저장소와 LLM 설정 (환경 변수 기반) |
| `msr_file`, `msr_image` | FTP / MinIO 핸들러 |

해당 피처는 각자의 `MIGRATION.md`를 확인합니다.
