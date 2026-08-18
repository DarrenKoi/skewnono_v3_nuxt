# Provider 선택 규칙

이 문서는 `back_dev_home/<feature>/providers/{mock,office}.py` 중 무엇이 실제로 응답을
만드는지가 어떻게 결정되는지를 설명합니다. adapter 구현 규칙은
[`docs/back-end/office-data-adapters.md`](office-data-adapters.md), 환경 간 전달 절차는
[`docs/swap-strategy.md`](../swap-strategy.md)가 기준입니다. 새 장비 계열을 붙일 때의
폴더 규약과 절차는 [`vendor-onboarding.md`](vendor-onboarding.md)가 다룹니다.

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

## 4. `health/` introspection 엔드포인트의 예외

라우트는 원칙적으로 `from .data import ...`만 사용하며 phase에 따라 분기하지
않습니다. 예외는 `back_dev_home/health/`의 introspection 엔드포인트들이며, 이들은
`_runtime`을 직접 읽습니다. **스왑 메커니즘 자체를 보고하는 엔드포인트가 그
메커니즘을 거치면, 정작 그것을 조회해야 하는 상황에서 잘못된 값을 보고할 수 있기
때문입니다.**

| 엔드포인트 | 직접 읽는 대상 | 답하는 질문 |
| --- | --- | --- |
| `GET /api/health/providers` | `_runtime/data_provider.py` | 전체 feature가 각각 어느 adapter로, 왜 해석되었는가 |
| `GET /api/health/data-mode` | `_runtime/data_provider.py` | 지정한 feature 하나가 지금 생성된 데이터를 주는가 |
| `GET /api/health/deployment` | `_runtime/env.py` | 이 인스턴스가 Phase 3 클라우드 배포본인가 |

이 예외는 `health/`에 한정됩니다. 다른 feature의 `routes.py`가 `_runtime`을 직접
import한다면 그것은 예외가 아니라 위반입니다. 엔드포인트별 auth gate와 그 이유는
[`back_dev_home/health/MIGRATION.md`](../../back_dev_home/health/MIGRATION.md)의
표에 있습니다 — carve-out이라는 사실이 admin 전용을 뜻하지는 않습니다.

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

## 7. 피처 사이의 provider 의존

피처는 서로 독립적으로 해석되지만, 일부 office adapter는 **다른 피처의
dispatcher를 통해 그 피처의 데이터를 읽습니다.** 이 경우 두 피처의 provider가
같아야 합니다.

| 피처 | 의존 대상 | 이유 |
| --- | --- | --- |
| `pm_planning` | `sem_list` | 장비 명단을 `sem_list/roster.py`의 `fleet_rows()`로 받은 뒤 그 `eqp_id`로 meas_hist를 조회합니다 |
| `storage` | `sem_list` | office adapter가 모든 행을 `eqp_ip`로 live sem_list와 조인합니다 |
| `tttm` | `sem_list` | 위와 같습니다. 두 피처는 같은 roster 법칙을 씁니다 |

`storage=office` + `sem_list=mock` 조합은 **오류를 내지 않습니다.** 조인 양쪽의
`eqp_ip`가 서로 다른 출처라 한 건도 매칭되지 않고, 스토리지 표가 200 응답과 함께
빈 채로 렌더링됩니다. 로그에도 아무것도 남지 않습니다.

`pm_planning`과 `tttm`은 같은 실패가 한 단계 더 나쁩니다. mock roster의 `eqp_id`는
지어낸 값이므로 meas_hist에서 어떤 실행도 찾지 못하고, 두 페이지 모두 빈 장비 그룹을
200으로 돌려줍니다. 게다가 **pm-tune 화면은 두 응답을 `eqp_id`로 조인합니다** —
한쪽이 mock roster이고 다른 쪽이 실제 roster이면 교집합이 0이 되는데, 각 응답은
따로 보면 아무 문제가 없어 보입니다.

이 조합은 환경 변수 없이도 발생합니다. 사무실에서 `storage`의 adapter만 `cp`하고
`sem_list`의 것을 빠뜨리면, presence 감지가 각각을 독립적으로 해석하여 정확히 이
상태가 됩니다.

그래서 `_runtime/data_provider.py`의 `_OFFICE_DEPENDENCIES` 표가 이 쌍을 선언하고,
`validate_env()`가 **해석된 결과**를 기준으로 검사하여 부팅을 거부합니다. 에러
메시지는 어느 쌍이 어긋났는지와 `cp` 명령을 함께 출력합니다.

규칙이 adapter가 아니라 이 표에 있는 이유는 `office.py`가 gitignore 대상이기
때문입니다. adapter 안에만 있는 규칙은 기계 한 대에만 존재하는 규칙입니다.
