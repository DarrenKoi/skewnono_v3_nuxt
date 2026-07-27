# OpenSearch 제품 활동·운영 로그 구현 완료 기록

- 작업일: 2026-07-27
- 브랜치: `main`
- 상태: Task 1~7 구현과 로컬 자동 검증을 완료했습니다.
- 미완료 범위: 회사 OpenSearch cluster 반영과 office 실데이터 smoke test입니다.

## 1. 완료 결과

제품 활동과 운영 로그를 별도 저장소로 나누지 않고 환경별 canonical
OpenSearch logging family에 기록하도록 구현했습니다.

```text
Flask request logging middleware
  -> OpenSearchBulkHandler
  -> ops_store.OSDoc.bulk()
  -> local:      skewnono_logging_local
  -> production: skewnono_logging

/api/activity/*
  -> activity office adapter
  -> ops_store.OSSearch aggregation

/api/admin/logs
  -> admin_logs office adapter
  -> ops_store.OSSearch query
```

writer와 두 reader는 모두 `SKEWNONO_LOG_ENV`를
`back_dev_home/_logging/target.py`에서 해석하므로 서로 다른 alias를 선택하는
drift를 막습니다. office reader는 OpenSearch 실패를 mock 또는 빈 성공 응답으로
숨기지 않고 안정적인 503 계약으로 반환합니다.

## 2. Task별 구현과 커밋

| Task | 주요 결과 | 커밋 |
| --- | --- | --- |
| 1 | local/production rollover family, 명시적 mapping, ISM policy, dry-run CLI를 구현했습니다. | `9bda219` |
| 2 | logging target과 activity 분류·FAB 정규화·query redaction 정책을 중앙화했습니다. | `dcf1126` |
| 3 | bounded queue, alias preflight, 멱등 bulk retry, drop 진단, 제한된 종료 flush를 구현했습니다. | `d3b942a` |
| 4 | 요청별 canonical activity 분류와 request ID, FAB context 승격, mock recorder parity를 구현했습니다. | `ec8c9d0` |
| 5 | OpenSearch 기반 개인·요약·사용자·FAB activity aggregation과 503 계약을 구현했습니다. | `49325c5` |
| 6 | `/admin/logs` 공통 query parser와 순수 mock, 선택 alias를 조회하는 office adapter를 구현했습니다. | `08e669b` |
| 7 | 403/503 UI 문구, activity 지표 문구, alias 표시, 환경 템플릿, API 계약과 office runbook을 갱신했습니다. | `068cf01` |

설계와 실행 계획은 다음 문서에 있습니다.

- `docs/superpowers/specs/2026-07-27-opensearch-logging-activity-design.md`
- `docs/superpowers/plans/2026-07-27-opensearch-logging-activity.md`

## 3. 저장소와 canonical 문서

| 환경 | Alias | 첫 backing index | Rollover 후 보존 |
| --- | --- | --- | --- |
| office PC localhost | `skewnono_logging_local` | `skewnono_logging_local-000001` | 30일 |
| company production cloud | `skewnono_logging` | `skewnono_logging-000001` | 365일 |

두 family는 20GB 또는 7일에 rollover합니다. mapping은 `dynamic: false`이며
request, exception, 사용자, 배포 환경, activity 분류, FAB context에 필요한 필드를
명시적으로 정의합니다. `event_id`를 OpenSearch `_id`로 사용하므로 같은 batch의
retry가 활동 문서를 중복 생성하지 않습니다.

요청·응답 body, Authorization header, cookie는 저장하지 않습니다. query string은
민감한 key 값을 `[REDACTED]`로 바꾸고 2,048자로 제한합니다.

## 4. Activity 의미

분류 우선순위는 다음과 같습니다. 먼저 일치한 단계가 최종 결과입니다.

| 순서 | Kind | Weight | 대표 조건 |
| --- | --- | --- | --- |
| 1 | `operation` | 0 | 익명·token·실패·비 API·activity/admin/health 요청입니다. |
| 2 | `background` | 0 | polling, prefetch, 자동 refresh 요청입니다. |
| 3 | `entry` | 1 | 인증된 사용자의 성공한 `sem_list` 진입 요청입니다. |
| 4 | `feature` | 1 | 그 밖의 인증된 사용자의 성공한 product API 요청입니다. |

Activity reader는 `event=request`, `activity_weight=1`,
`activity_kind in (entry, feature)` 문서만 active-user 지표에 사용합니다.
Top feature, favorite feature와 FAB page 순위에는 `feature`만 포함합니다.

- 문서는 UTC로 저장하고 날짜 경계는 `Asia/Seoul`을 사용합니다.
- WAU는 오늘을 포함한 trailing 7 KST 날짜입니다.
- MAU는 오늘을 포함한 trailing 30 KST 날짜입니다.
- `first_seen`은 계정 lifetime이 아니라 현재 alias의 보존 구간에서 가장 이른
  활동입니다.
- `/activity/fabs`의 `total`은 request 수가 아니라 distinct active user 수입니다.
- 여러 FAB context가 있는 문서는 각 FAB bucket에 포함됩니다.
- FAB context가 없으면 `"미지정"` bucket으로 집계합니다.

## 5. Admin logs와 UI

`admin_logs/providers/mock.py`는 자격 증명과 실행 위치에 관계없이 항상
deterministic 인메모리 데모만 반환합니다. office adapter만 선택된 alias를
OpenSearch에서 조회합니다.

공통 query module은 기존 시간 범위, pagination, level, event, method, user,
feature, path, status, free-text 검색 계약을 유지합니다. 잘못된 query는
`400 invalid_log_query`, 설정 또는 OpenSearch 실패는 내부 host나 예외를 노출하지
않는 `503 log_query_failed`입니다.

프론트에서는 다음 가용성 의미를 반영했습니다.

- `/activity`와 `/admin/logs`의 OpenSearch 503을 빈 데이터로 표시하지 않습니다.
- 403은 raw FetchError 대신 관리자 전용 페이지 안내로 표시합니다.
- 관리자 로그 제목은 환경 중립적인 `운영 로그`이며 실제 조회 alias를 표시합니다.
- FAB selector의 숫자는 `활성 N명`으로 표시하여 request 수와 구분합니다.
- WAU와 MAU 설명은 이번 주·이번 달이 아니라 최근 7일·최근 30일로 표시합니다.

## 6. 로컬 검증 결과

| 검증 | 결과 |
| --- | --- |
| 프론트 `npm test` | 860개 통과 |
| 프론트 `npm run typecheck` | 통과 |
| 프론트 `npm run lint` | 오류 0개, 기존 경고 2개 |
| 백엔드 `.venv/bin/python -m pytest tests back_dev_home -q` | 1,489개 통과, 8개 skip, subtest 7개 통과 |
| `uv run --no-project ruff check back_dev_home tests` | 통과 |
| `npm run lint:md` | 167개 Markdown 파일, 오류 0개 |
| API 계약 YAML 구문 검사 | 통과 |
| `git diff --check` | 통과 |

프론트 lint 경고는 변경하지 않은
`front-dev-home/app/components/ebeam/skewvoir/gallery/ImageViewer.vue`의
`eqp_ip`, `class_name` prop 이름 2건입니다.

실행 중인 Nuxt의 `/activity`가 HTTP 200을 반환하는 것은 확인했습니다. 다만 현재
Codex에 연결 가능한 브라우저 세션이 없어 실제 화면의 시각·상호작용 검증은
수행하지 못했습니다. 프론트 자동 테스트, typecheck와 lint로 코드 경계를
검증했으며 office 실데이터 화면 확인은 아래 절차에 남아 있습니다.

로컬 Homebrew Node 25는 `libllhttp.9.3.dylib` 불일치로 실행되지 않았습니다.
검증은 정상 설치된 NVM Node 24.13.0을 `PATH` 최우선으로 지정하여 수행했습니다.
시스템 설치나 저장소 dependency는 변경하지 않았습니다.

## 7. 회사에서 실행할 잔여 절차

다음 단계는 회사 네트워크와 공유 OpenSearch cluster를 사용하므로 이번 로컬
작업에서는 실행하지 않았습니다.

1. `OPENSEARCH_*` 자격 증명과 실행 위치에 맞는 `SKEWNONO_LOG_ENV`를 설정합니다.
2. tracked office adapter를 복사합니다.

   ```bash
   cp back_dev_home/activity/providers/office_example.py \
     back_dev_home/activity/providers/office.py
   cp back_dev_home/admin_logs/providers/office_example.py \
     back_dev_home/admin_logs/providers/office.py
   ```

3. 회사 네트워크에서 read-only dry-run 결과를 검토합니다.

   ```bash
   .venv/bin/python ops_index_mgmt/skewnono_logging.py \
     --environment all \
     --dry-run
   ```

4. 검토 후 멱등하지만 cluster를 변경하는 실제 반영 명령을 실행합니다.

   ```bash
   .venv/bin/python ops_index_mgmt/skewnono_logging.py \
     --environment all
   ```

5. 다음 write alias 연결을 확인합니다.

   ```text
   skewnono_logging_local-000001 → skewnono_logging_local
   skewnono_logging-000001       → skewnono_logging
   ```

6. office provider 계약 테스트를 실행합니다.

   ```bash
   SKEWNONO_ACTIVITY_PROVIDER=office \
   SKEWNONO_ADMIN_LOGS_PROVIDER=office \
   SKEWNONO_LOG_ENV=local \
     .venv/bin/python -m pytest \
       back_dev_home/activity \
       back_dev_home/admin_logs -q
   ```

7. Flask와 Nuxt를 실행하여 `/activity`와 `/admin/logs`의 실데이터, alias 표시,
   최근 7일·30일 지표, FAB distinct-user 의미를 확인합니다.
8. OpenSearch 연결을 의도적으로 차단하여 raw 내부 오류 대신
   `activity_query_failed`와 `log_query_failed` 503 및 가용성 안내가 표시되는지
   확인합니다.
9. 위 smoke test가 끝난 뒤에만 `docs/office-migration/STATUS.md`의 두 상태를
   `구현완료`에서 `office`로 변경하고 검증일을 기록합니다.

## 8. 기준 문서

- Canonical 문서 계약: `docs/api-contracts/usage-events.yaml`
- Activity HTTP 계약: `docs/api-contracts/activity.yaml`
- Office 공통 runbook: `docs/back-end/office-data-adapters.md`
- Activity 이전 절차: `back_dev_home/activity/MIGRATION.md`
- Admin logs 이전 절차: `back_dev_home/admin_logs/MIGRATION.md`
- 전환 상태: `docs/office-migration/STATUS.md`

작업 중 발견된 secret이나 실제 사내 host는 문서와 코드에 기록하지 않았습니다.
사용자가 관리하는 `.remember/open-jobs.md`와 `.remember/today-2026-07-27.md`
변경은 이 작업의 스테이징과 커밋에서 제외했습니다.
