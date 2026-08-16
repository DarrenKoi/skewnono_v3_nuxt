# 댁(Home) ↔ 사무실(Office) 백엔드 스왑 전략

## 1. 개요

SKEWNONO은 두 개의 분리된 작업 환경을 오가며 개발됩니다.

| 환경 | 데이터 소스 | LLM | 역할 |
| --- | --- | --- | --- |
| 댁 (Home) | `back_dev_home/` 모의(Flask + 인메모리) | Claude Code | 프론트 + 모의 데이터 + 계약 작성 |
| 사무실 (Office) | OpenSearch / Redis / 사내 DB (실제) | 사내 로컬 LLM | 모의 → 실제 구현으로 스왑 |

두 환경은 직접 동기화되지 않습니다. 따라서 **명세 계층(spec layer)** 이 두 환경을 잇는 유일한 다리입니다. 본 문서는 그 명세 계층을 어떻게 구성하고, **어떻게 지속적으로 양방향 동기화** 하는지를 설명합니다.

핵심 아이디어: **모의 데이터는 사무실 LLM을 위한 타입 정의된 프롬프트(typed prompt)** 입니다. YAML 계약, `contracts.py`, mock adapter, 고정 JSON 픽스처가 모이면 사무실 LLM이 실제 OpenSearch 인덱스 스키마와 결합해 `providers/office.py`를 작성할 수 있습니다. adapter 구현 규칙과 `sem_list`용 프롬프트는 [`docs/back-end/office-data-adapters.md`](back-end/office-data-adapters.md)를 따릅니다.

## 2. 현재 스왑 준비 상태

### 2.1 프론트엔드 — 이미 스왑 가능 상태입니다

- `front-dev-home/nuxt.config.ts`는 `NUXT_API_TARGET`으로 `/api/*`를 Flask에 proxy합니다.
- 프론트엔드 컴포저블은 `NUXT_PUBLIC_API_BASE`와 `$fetch<T>()`를 사용합니다.
- Phase별 데이터 source 분기는 Flask 내부 provider 선택에만 둡니다.

**결론:** 사무실 전환은 `.env` 한 줄(`NUXT_API_TARGET`) 변경으로 충분합니다.

### 2.2 백엔드 — provider 전환은 시작되었지만 전체 적용 전입니다

2026-07-15 기준 route module은 19개입니다. 이 중 mock/office provider seam이 준비된
피처는 `sem_list`, `ebeam/storage`, `ebeam/hardware`,
`ebeam/tttm` 네 개입니다.

나머지 피처는 기존 `data.py`에서 mock 구현을 `providers/mock.py`로 이동하고,
`contracts.py`와 `providers/office.py`를 추가해야 합니다. 모든 폴더에 빈 office adapter를
한 번에 만들지 않고, 원본 schema와 계약이 준비된 피처부터 전환합니다.

### 2.3 이미 존재하는 명세 인프라

- `docs/api-contracts/` — HTTP YAML 계약과 작성 규칙이 있습니다.
- `docs/datatables/*.txt` — 사무실 측 원본 테이블 스키마(`meas_hist.txt`, `r3_device_grp.txt` 등)가 정리되어 있습니다.
- `back_dev_home/<feature>/__fixtures__/` — 대표 HTTP 응답 예시가 있습니다.
- `scripts/capture_fixtures.py`, `scripts/check_contract.py` — 기준 응답 캡처와 구조 비교 도구가 있습니다.

**원칙:** 새 규약을 만들지 말고, 위 구조의 **빈 칸을 채우는 방향** 으로 작업합니다.

## 3. 정리해야 할 공통 결함

| ID | 위치 | 문제 |
| --- | --- | --- |
| L1 | provider 전환 미적용 피처 | mock 구현, 공개 계약, office adapter가 아직 분리되지 않음 |
| L2 | 사무실 원본 명세 | source 이름, mapping, null/enum/timezone/dedup 규칙이 피처별로 불완전함 |
| L3 | 오류 응답 | 일반 source 예외가 공통 JSON 오류 형태와 HTTP 상태로 정규화되지 않음 |
| L4 | 사무실 의존성 | OpenSearch/MinIO는 `ops_store`/`minio_handler`를 사용하며 전체 dependency version 고정이 남음 (인증은 `LASTUSER` 쿠키만 사용하므로 외부 SSO 모듈 의존 없음) |
| L5 | 검증 범위 | `check_contract.py`는 첫 행 구조를 비교하지만 enum, 모든 행, 중복, truncation은 검증하지 않음 |

피처별 상세 체크리스트는 `docs/back-end/office-data-adapters.md`의 연결 명세 표를 사용합니다.

## 4. 양방향 워크플로 (핵심)

스왑은 일회성 작업이 아닙니다. 댁과 사무실 모두 시간에 따라 변하므로 **각 작업 세션이 명세 계층을 함께 갱신** 해야 합니다.

### 4.1 댁 → 사무실 (push)

매 댁 작업 세션은 다음을 함께 커밋합니다.

| 산출물 | 위치 | 갱신 시점 |
| --- | --- | --- |
| 프론트엔드 코드 | `front-dev-home/` | 기능 변경 시 |
| Python 계약 | `back_dev_home/<feature>/contracts.py` | 반환 키·타입 변경 시 |
| mock adapter | `back_dev_home/<feature>/providers/mock.py` | mock 동작 변경 시 |
| provider dispatcher | `back_dev_home/<feature>/data.py` | 공개 함수 또는 provider 선택 변경 시 |
| API 계약 YAML | `docs/api-contracts/<feature>.yaml` | 엔드포인트·필드 추가/변경 시 |
| 고정 픽스처 JSON | `back_dev_home/<feature>/__fixtures__/*.json` | 응답 형태 변경 시 재생성 |
| 원본 테이블 스키마 | `docs/datatables/<table>.txt` | 댁에서 변경할 일 거의 없음 |

규칙: **공개 계약이 바뀌면 같은 커밋에 `contracts.py`, mock adapter, YAML, 픽스처를 함께 갱신** 합니다. 그렇지 않으면 사무실 측에서 LLM 스왑이 깨집니다.

### 4.2 사무실 → 댁 (pull)

매 사무실 작업 세션은 다음을 댁으로 가져갈 변경에 포함합니다.

| 산출물 | 위치 | 갱신 시점 |
| --- | --- | --- |
| 사무실 측 인덱스/스키마 | `docs/datatables/<table>.txt` | 실 OpenSearch 매핑 변경·신규 발견 시 |
| 계약 변경 사항 | `docs/api-contracts/<feature>.yaml` | 실 데이터에서 새 필드/제약 발견 시 |
| 드리프트 기록 | `docs/datatables/<table>.txt` + 해당 기능의 `MIGRATION.md` | 픽스처 vs 실 데이터 차이를 발견했을 때 |
| 사무실 픽스처 (선택) | `back_dev_home/<feature>/__fixtures__/office/*.json` | 사외 유출 위험 없는 익명화 가능 시 |

### 4.3 사이클 한 바퀴 표준 절차

```text
[댁 세션 종료 시]
1. 기능 작업 + 모의 데이터 수정
2. python scripts/capture_fixtures.py        # 픽스처 재생성
3. docs/api-contracts/<feature>.yaml 갱신    # 변경 시
4. npm run lint:md                            # 마크다운 검증
5. git commit (코드 + 명세 한 묶음)

[사무실 세션 시작 시]
6. git pull
7. cd back_dev_home/<feature>
8. 사무실 LLM에 다음 자료 투입:
   - docs/api-contracts/<feature>.yaml
   - back_dev_home/<feature>/data.py
   - back_dev_home/<feature>/contracts.py
   - back_dev_home/<feature>/providers/mock.py
   - back_dev_home/<feature>/providers/office.py
   - back_dev_home/<feature>/__fixtures__/*.json
   - docs/datatables/<source>.txt
   - ops_store/ 또는 minio_handler/ 의 관련 interface 문서
   - (사무실 LLM만 보는) 실제 OpenSearch 매핑
9. providers/office.py 구현 → 실 Flask에 배치

[사무실 세션 종료 시]
10. PORT=5000 python -m scripts.check_contract  # 픽스처와 구조 일치 확인
11. 드리프트가 있으면 docs/datatables/ 와 mock.py 양쪽에 기록
12. 새 필드/제약은 docs/api-contracts/에 반영
13. git commit (사무실 분기 또는 patch 파일)

[댁 세션 시작 시]
14. 사무실 변경 가져오기 (분기 머지 또는 patch)
15. 사무실에서 발견한 계약 변경을 contracts.py와 mock adapter에 반영
16. 픽스처 재생성 → 사이클 재시작
```

### 4.4 사이클이 깨지는 신호

다음 상황은 명세 계층이 뒤처졌다는 경고입니다.

- 사무실 LLM이 "픽스처와 형태가 다릅니다"라고 자주 말함 → 댁 측이 YAML/픽스처를 함께 갱신하지 않음
- 사무실 측 신규 필드가 댁 모의에 없어 프론트엔드가 깨짐 → 사무실 → 댁 동기화 누락
- `check_contract.py` 가 새 키를 보고할 때마다 직접 손으로 YAML 수정 → 갱신 자동화 부족

## 5. 사무실 LLM 활용

### 5.1 잘 맡길 수 있는 일

1. **계약 → 실 쿼리 변환** — YAML + `contracts.py` + mock adapter + 픽스처 + 데이터테이블 + 사무실 인덱스 매핑을 입력으로 주고 `providers/office.py` 초안을 받습니다. 모의 계약이 곧 타입 정의된 프롬프트입니다.
2. **OpenSearch DSL 작성** — 집계 쿼리는 길고 오타가 잦으므로 LLM이 강점을 보입니다. 반환 TypedDict + 매핑 → DSL.
3. **실 응답 ↔ 픽스처 구조 비교** — office adapter 결과를 덤프하고 LLM에 "픽스처 대비 누락 키, 타입 변동, 신규 enum을 나열하라" 요청합니다.
4. **Redis 캐시 래퍼 초안** — 함수 시그니처 + 캐시 적중 목표를 주면 빠르게 작성합니다.
5. **드리프트 리포트 작성** — 변경 사항을 구조화된 마크다운으로 정리합니다.
6. **사외 유출 위험 없음** — 로컬 LLM이므로 인덱스 매핑·실 샘플 행을 사내망 밖으로 내보내지 않습니다.

### 5.2 맡기지 말 것

- 계약 자체의 발명 — 계약은 댁 측 작업의 결과물이며, LLM에게 위임하면 타입 정의된 프롬프트 속성이 사라집니다.
- 비즈니스 정합성 검증 — 데이터만 보고 판단할 수 없습니다. 계약 + 스모크 테스트가 검증의 기준입니다.

### 5.3 권장 프롬프트 템플릿

```text
당신은 SKEWNONO Office Flask의 데이터 액세스 계층 담당입니다.

[입력]
- 계약(YAML):       docs/api-contracts/<feature>.yaml
- 공개 interface:   back_dev_home/<feature>/data.py
- Python 계약:      back_dev_home/<feature>/contracts.py
- 댁 mock adapter:  back_dev_home/<feature>/providers/mock.py
- 사무실 adapter:   back_dev_home/<feature>/providers/office.py
- 기대 출력 예시:   back_dev_home/<feature>/__fixtures__/<endpoint>.json
- 원본 테이블 명세: docs/datatables/<source>.txt
- 사무실 매핑:      [붙여넣기 — OpenSearch 인덱스 매핑 / 테이블 DDL]

[작업]
1. providers/office.py에서 <feature>의 공개 interface를 사무실 데이터로 구현합니다.
2. 함수 시그니처와 TypedDict 반환 타입은 변경하지 않습니다.
3. 픽스처와 동일한 키, 타입, enum 값을 보장합니다.
4. recipe_tat 처럼 시간 윈도가 있는 피처는 wall-clock now() 가 아니라
   max(timestamp) 를 anchor 로 사용합니다.
5. 불명확한 원본 사실은 추측하지 않고 확인 필요 목록으로 출력합니다.
6. routes.py, data.py, contracts.py, mock adapter, frontend는 변경하지 않습니다.

[출력]
- 새 providers/office.py 전체
- office adapter unit test
- 사용한 OpenSearch 쿼리 / SQL 한 줄 설명
- 확인한 가정과 확인 필요 항목 목록
```

`sem_list` 구현에는 더 구체적인 프롬프트가 필요하므로
`docs/back-end/office-data-adapters.md`의 템플릿을 그대로 사용합니다.

## 6. 작업 항목

피처를 다음 상태 순서로 전환합니다.

1. YAML, `contracts.py`, fixture, 원본 schema를 완성합니다.
2. mock 구현을 `providers/mock.py`로 이동합니다.
3. `data.py`를 provider 선택과 공개 함수만 남기는 dispatcher로 바꿉니다.
4. 동일 interface의 `providers/office.py` stub을 추가합니다.
5. 사무실 mapping을 확인한 뒤 office adapter와 fake-client test를 구현합니다.
6. `sem_list` → 공통 연결/health → `storage` → read-only 피처 → 쓰기/관리 피처
   순으로 배치합니다.

현재 피처별 전환 현황과 공통 미결정 사항은
`docs/back-end/office-data-adapters.md`에서 관리합니다.

## 7. 검증

### 7.1 댁에서 (커밋 전)

1. Flask와 Nuxt 개발 서버 동작을 확인합니다.
2. `python scripts/capture_fixtures.py` 실행 → `__fixtures__/*.json` 갱신됩니다.
3. `python scripts/check_contract.py` — 댁 Flask 자체에 대해 통과하는 것이 기준선(baseline)입니다.
4. `npm run lint:md` 통과를 확인합니다.

### 7.2 사무실에서 (스왑 직후)

1. `python index.py` 가 사무실 설정으로 기동합니다.
2. `python scripts/check_contract.py` 가 통과합니다 (실패 시 키/타입 차이가 그대로 출력됩니다).
3. `.env` 의 `NUXT_API_TARGET` 을 사무실 호스트로 변경하고 Nuxt 가 정상 렌더되는지 확인합니다.
4. 차이가 있으면 `docs/datatables/<table>.txt` 와 해당 기능의 `providers/mock.py`
   양쪽에 기록한 뒤 댁으로 가져갑니다 (CLAUDE.md 의 "두 곳에 함께 기록" 규칙).

## 8. 한 줄 요약

**모의 데이터는 사무실 로컬 LLM을 위한 타입 정의된 프롬프트입니다.** YAML + `contracts.py` + mock adapter + 픽스처를 매 커밋에 함께 갱신하면, 댁과 사무실의 드리프트가 누적되지 않고 스왑이 기계적인 작업이 됩니다.
