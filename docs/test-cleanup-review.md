# 전체 테스트 정리 검토

검토일은 2026-10-05이며 기준 커밋은 `1ab073fb`입니다. 작업은 격리된
`/private/tmp/skewnono-test-cleanup`, `work/test-cleanup-20261005`에서 수행했습니다.
원본 작업 트리는 시작 시 깨끗했습니다. 제품 코드, vendored 코드, 별도 RAG
저장소는 수정하지 않았습니다.

결론은 동일한 입력·실행 경로·기대값을 이미 검증하는 테스트 3개만 삭제하는
것입니다. backend 2개와 frontend 1개이며 대체 테스트는 추가하지 않았습니다.
provider, 인증·권한, unknown/null, 캐시·동시성, 배포 및 office 전용 검증은
보존했습니다. assertion 변경, skip 추가, 수집 범위 축소는 없습니다.

## 검토 범위와 방법

`CLAUDE.md`, `AGENTS.md`, `backend/chat/AGENTS.md`, `pyproject.toml`,
`frontend/package.json`, `.github/workflows/ci.yml`을 확인했습니다.
Python 테스트 모듈 221개와 frontend 테스트 파일 164개 전체를 목록화했습니다.
Python 함수 정의는 2,982개이며 파라미터화 후 수집 항목은 3,891개입니다.
frontend는 등록된 테스트 1,904개입니다. 정의 수와 수집 수를 혼동하지 않습니다.

전체 테스트에 대한 AST 기반 입력 인자·호출·assertion·import 인덱스, 동일 본문
비교, fixture/helper 참조 검색을 출발점으로 삼았습니다. 같은 본문도 decorator,
fixture, 환경, 저장소 상태가 다르면 별개 검증입니다. frontend에서는 TypeScript
AST로 테스트 등록과 import를 목록화하고 동일 callback도 비교했습니다.
이 기계적 검토만으로 의미적 중복이 증명되지는 않으므로, 후보는 원본 테스트,
제품 함수, 실제 호출자, 남는 assertion을 직접 대조했습니다. 삭제 근거가 없는
나머지는 보존했습니다. 전체 실행 성공은 모든 가능한 회귀를 잡는다는 증거가
아니며, 의미만 유사한 모든 테스트 쌍을 동등하다고 판정한 것도 아닙니다.

제품 참조는 backend의 routes → dispatcher → mock/office template 및 공유
로직, frontend의 utility/composable → 컴포넌트·화면 사용처, scripts와 배포
경로까지 탐색했습니다. `test_scheduler.py`처럼 옛 파일명을 가진 테스트도
현재 `backend/_scheduler/tasks/image_cache.py`를 호출하므로 삭제하지 않았습니다.
제거된 기능만 검증한다고 입증된 테스트는 없습니다.

## 첫 번째 패스: 목록과 기준선

`python -m pytest --collect-only -q`로 양쪽 Python 테스트 루트를 수집했습니다.
`python -m pytest -q`, `python -m ruff check .`, frontend `npm test`,
`npm run typecheck`를 변경 전에 실행했습니다. 모두 통과했습니다.

다음 표는 파라미터화된 backend 수집 항목 기준이며 모든 영역의 후보 분류를
완료했습니다. 수집 중 모듈 자체가 skip된 office dispatch 파일은 항목 수와
별도로 기록합니다.

| 영역 | 전 → 후 수집 | 검토 결과와 보존하는 실패 시나리오 |
| --- | --- | --- |
| `tests/` | 929 → 929 | 유지합니다. home/office dispatch, 전체 API, rate limit, 환경 스크립트, pack/preflight 및 vendored 모듈의 소비자 계약입니다. |
| `_auth` | 137 → 137 | 유지합니다. token/cookie/declaration 우선순위, 관리자 출처, directory 장애·캐시·세션 및 접근 거절입니다. |
| `_core` | 26 → 26 | 유지합니다. bool/int 구분, Optional/union, 경로가 있는 계약 오류, OpenSearch escaping 및 좌표 parser입니다. |
| `_logging` | 303 → 303 | 유지합니다. page/API 분류, anonymous 제외, request context, 큐·재시도·alias와 공유 identity fixture입니다. |
| `_runtime` | 102 → 102 | 유지합니다. provider/readiness, env, registry 충돌, office 복사본 provenance 및 Redis 역직렬화입니다. 동일한 provider 검증 한 쌍은 보수적으로 보존합니다. |
| `_scheduler` | 98 → 98 | 유지합니다. uWSGI/reloader 선출, kill switch, timezone, lock 갱신·해제와 작업 등록·로그입니다. |
| `_spa` | 24 → 24 | 유지합니다. cloud 경로, SPA fallback, asset 제공과 로깅 제외 플래그의 계약입니다. |
| `access_control` | 49 → 49 | 유지합니다. 관리자 API, fail-closed 쓰기, 장애와 실제 차단의 구분 및 exception round-trip입니다. |
| `activity` | 77 → 77 | 유지합니다. anonymous의 모든 조회 경로 제외, 방문 기간·종류와 OpenSearch 부분 응답 거절입니다. |
| `admin_logs` | 25 → 25 | 유지합니다. 필터·정규화, 조회 기간 오류, 사용자 이름 조회 장애 및 token 정보입니다. |
| `afm` | 49 → 49 | 유지합니다. office 사실 기반 mock, ragged block, profile 부재, 이미지 원본·ZIP 및 날짜 안정성입니다. |
| `announcements` | 20 → 20 | 유지합니다. 시간대·활성 기간, malformed 입력, 장애와 코드 버그의 구분입니다. |
| `api_tokens` | 45 → 45 | 유지합니다. 소유권, secret 비저장, revoke, debounce, 장애 및 병렬 store 갱신입니다. |
| `chat` | 231 → 231 | 유지합니다. RAG 서명·오류·반환 계약, ownership, replay, history, scope, figure의 디스크/MinIO 분기입니다. |
| `ebeam` 공유 | 178 → 177 | `ZZ9000` 중복만 삭제합니다. 모델 분류, tool family/adapter, AMAT 거절, aggregation paging·truncation은 유지합니다. |
| `device_statistics` | 166 → 166 | 유지합니다. 모집단 조인, mother/region/order, unknown flag, bucket 및 snapshot 파일·날짜·retention입니다. 느린 4,000-lot 검증도 보존합니다. |
| `fail_issue` | 44 → 44 | 유지합니다. 표본 하한의 unknown index, Byar interval, recipe mix 보정·fleet 합계와 compare scope입니다. |
| `hardware` | 230 → 230 | 유지합니다. tab fallback, numeric string/null, 시간대, 원천 필드·정렬·cap, roster 및 FDC/MDC/SCE/BM-PM 계약입니다. |
| `lateral_recipe` | 18 → 18 | 유지합니다. measured/version join, readiness, roster family와 office 전용 데이터 검증입니다. |
| `live_alarm` | 110 → 109 | fresh meta의 동일 assertion 1개만 삭제합니다. 임계값, malformed event, roster, cache TTL·lock·backoff·Redis 검증은 유지합니다. |
| `pm_planning` | 10 → 10 | 유지합니다. roster·provider 및 fleet payload 계약입니다. root의 window route 검증도 별도로 유지합니다. |
| `recipe_search` | 399 → 399 | 유지합니다. IDP schema/order, locator, raw parser, filename·image variants, registry, FTP host 격리·cache 및 route 입력 검증입니다. |
| `recipe_tat` | 54 → 54 | 유지합니다. meastime/count 분모, recipe mix 보정, sample floor, 표본·scope·비교 및 office query입니다. |
| `storage` | 17 → 17 | 유지합니다. sem_list fab join, blank fallback, payload 및 family route 거절입니다. |
| `tttm` | 44 → 44 | 유지합니다. matrix·parameter·recipe evidence, unavailable/None, window 및 eqp subset입니다. |
| `health` | 42 → 42 | 유지합니다. admin gate, provider introspection, mock/office mode, job 및 service 상태입니다. |
| `meas_hist` | 70 → 70 | 유지합니다. id-only MSR, unknown identity, ratio, 부분 aggregation 거절 및 overlap/timezone window입니다. |
| `msr_file` | 139 → 139 | 유지합니다. office metadata, row/image/FDC invariant, artifact 오류·ZIP 충돌, program identity 및 좌표 round-trip입니다. |
| `msr_image` | 167 → 167 | 유지합니다. path 안전성, disk/MinIO cache·purge, Redis job, single-flight, preview·COND 및 FTP timeout/account입니다. |
| `sem_list` | 24 → 24 | 유지합니다. pending/reachable 집합, roster identity와 NaN/NaT/bytes 정규화입니다. |
| `short_links` | 64 → 64 | 유지합니다. hostile URL 거절, 충돌·TTL·idempotency, outage와 missing 구분 및 HTTP 계약입니다. |
| 합계 | 3,891 → 3,889 | 예정한 backend 중복 2개만 수집 목록에서 제거되었습니다. |

frontend 164개 파일도 모두 분류했습니다. 다음 영역의 테스트들은 해당 utility를
직접 실행하거나 composable/SFC 실행 harness를 사용하며 현재 화면에서 참조됩니다.
단순 선언·상수 assertion도 표시 규칙이나 판정 기준을 보호하면 보존했습니다.
Nuxt의 utility auto-import도 고려했습니다. 예를 들어 `afmSearch`,
`noticeFilter`, `asyncDataCache`는 명시적 import 문자열이 없어도 생성된
`.nuxt/imports.d.ts`와 화면·composable의 exported 함수 호출이 연결됩니다.

| frontend 영역 | 결과 | 보존하는 검증 |
| --- | --- | --- |
| `components/`, `composables/`, `data/` | 유지 | Sparkline·BoolPill·CondMarks 렌더링, identity cache 무효화, live alarm polling, paging, param-detail 요청 및 notice/history 데이터입니다. |
| activity·identity·navigation·공유 계약 | 유지 | anonymous·family·page partition, API path, fab·tool 이름/분류 및 공유 JSON parity입니다. |
| AFM | 유지 | numeric string/unknown, block association, export 충돌, summary·point·heatmap·histogram·trend입니다. |
| wafer·이미지·chart | 중복 1개 삭제, 나머지 유지 | offset·좌표 round-trip, null 위치, axis·tooltip, chart range/zoom/nearest, image retry/warm 및 렌더링 옵션입니다. |
| recipe·storage·검색·TTTM·PM | 유지 | selection·pair·export, IDP table, comparator, window·subset·limits, recent state, fleet 및 parameter PCA입니다. |
| device·rules·outlier·anomaly | 유지 | cap·mother/son, unknown 판정, bucket·분모, 최소 표본·기본 threshold, sort 및 export입니다. |
| hardware·equipment·FDC·SCE·BM-PM | 유지 | numeric parsing·null, 시간·시계열·장비 비교, parameter 색상 및 fleet 모델 coverage입니다. |
| `skewvoirAnalysis/` 및 MSR | 유지 | grain, measured/failure, health placeholder 사용 금지, route query, variant/cache, curated set 및 분석 정렬·통계입니다. |
| chat·공용 출력 | 유지 | citation·attachment chart, Markdown escaping, 날짜·HTML·Excel export 및 icon 존재입니다. |

## 두 번째 패스: 변경별 근거와 관련 실행

### live alarm의 fresh 상태 중복

삭제한 함수는 `backend/ebeam/live_alarm/tests/test_board.py`의
`test_fresh_meta_is_live`입니다. fixture나 decorator가 없으며 입력은
`board.feed_status_for(_meta(1000), known=True, now=1000)`이고 기대값은
`"live"`입니다. 같은 파일의 `test_feed_status_reads_fetched_at_not_polled_at`에
동일 입력·동일 함수·동일 기대값이 그대로 남습니다. 앞선 호출도 상태를 바꾸지
않는 순수 함수입니다(`backend/ebeam/live_alarm/board.py:45`).

남는 검증은 `fetched_at`를 정상적인 성공 시각으로 읽는지와 옛 `polled_at`를
fresh로 오인하지 않는지입니다. `test_exactly_at_threshold_is_still_live` 및
`test_one_second_past_threshold_is_stale`도 보존하므로 경계 실패를 잃지 않습니다.
제품 `payload()`가 이 함수를 사용하며 reader/refresh/cache 테스트는 변경하지
않았습니다.

### tool 분류의 동일 unknown 입력 중복

삭제한 함수는 `backend/ebeam/tests/test_tool_specs.py`의
`test_unknown_model_is_still_unclassified`입니다. 입력 `"ZZ9000"`, 실행 함수
`model_to_tool_type`, 기대값 `None`이며 fixture나 환경 변경이 없습니다.
`backend/ebeam/__fixtures__/tool_type_cases.json`의 동일 case와
`test_tool_type_parity.py::test_backend_classifier_matches_the_shared_fixture[ZZ9000]`
가 같은 함수에 같은 입력을 전달하고 `None`과 비교합니다. 삭제한 `is None`과
남는 `== None`은 이 함수의 `str | None` 반환 범위에서 같은 실패를 잡습니다.

`UNKNOWN`, `XG6300`, `T P3000`, 공백 등 다른 입력 검증은 그대로 남습니다.
frontend `toolTypeParity.test.ts`도 동일 fixture를 읽습니다. 제품 분류기는
roster, storage, lateral_recipe, live_alarm 및 hardware에서 실제 사용됩니다.
unknown을 임의의 family로 분류하는 회귀는 남는 테스트가 잡습니다.

### wafer 좌표의 기본 offset 중복

삭제한 frontend 테스트 이름은 `mmToDieIndex offset defaults to zero for
existing callers`입니다. `frontend/app/utils/waferGeometry.test.ts`에 있던
`mmToDieIndex(6.9, 6.818182) === 1` assertion은 같은 파일의
`mmToDieIndex rounds mm to the nearest die column/row` 안에 완전히 동일하게
남습니다. 양쪽 모두 fixture 없는 순수 함수 호출이며 세 번째 인자를 생략하므로
`waferGeometry.ts:106`의 `offsetMm = 0` 경로도 동일합니다.

남는 테스트에는 0·양수·음수의 두 인자 호출이 있고, 명시적인 offset 및 unknown
pitch/null, snap-to-die round-trip은 각각 별도 테스트로 보존합니다. 제품 호출자
`waferAxis.ts`와 이를 사용하는 map/axis 검증도 관련 실행에 포함했습니다.

관련 backend 실행은 다음 명령이며 **164 passed**입니다.

```bash
.venv/bin/python -m pytest backend/ebeam/live_alarm \
  backend/ebeam/tests/test_tool_specs.py \
  backend/ebeam/tests/test_tool_type_parity.py -q -ra
```

관련 frontend 실행은 다음 명령이며 **40 passed**입니다.

```bash
cd frontend
node --test app/utils/waferGeometry.test.ts app/utils/waferAxis.test.ts \
  app/utils/waferMapOptions.test.ts app/utils/toolType.test.ts \
  app/utils/toolTypeParity.test.ts
```

## 보존한 후보와 지원 코드

- `_runtime/tests/test_site_provider.py`의
  `test_validate_env_ignores_the_global_mode_var`와
  `test_both_on_office_is_the_supported_pairing`은 `wired` fixture, office 전역
  변수와 `validate_env()` 호출이 같습니다. 검출력은 겹치지만 provider 보호
  영역이며 전역 변수의 역할과 cross-feature pairing이라는 서로 다른 계약을
  명명합니다. 이번 정리에서는 두 검증을 보존했습니다.
- `test_amat_families_resolve_to_their_own_tool_types`의 세 입력은 공유 parity
  fixture와 겹칩니다. 밑줄 표기 `VERITY_SEM_5`의 독립적인 AMAT 계약 guard를
  유지했습니다. 대소문자·공백·새 모델 입력은 같지 않으므로 합치지 않았습니다.
- chat의 디스크 missing과 MinIO missing 테스트는 본문이 같지만 `minio`
  fixture가 RAG readiness와 저장소를 바꿉니다. 로컬 파일 부재와 `NoSuchKey`
  처리가 서로 다르므로 둘 다 필요합니다.
- `_logging`의 ops page와 unmapped e-beam page 테스트는 함수 본문이 같아도
  parameter 입력이 다릅니다. scheduler election도 uWSGI 유무가 다릅니다.
  선언되지 않은 설정과 빈 문자열 설정도 같은 입력으로 취급하지 않았습니다.
- live alarm의 cold-cache 및 TTL 내 재요청은 초기 호출과 재사용을 구분합니다.
  캐시·동시성 검증을 줄이지 않았습니다. snapshot 반복 생성도 overwrite,
  retention, payload, 날짜 등 assertion이 달라 속도를 이유로 삭제하지 않았습니다.
- source text/AST 검증 중 office-only parser import 금지, Windows cp949,
  stream reconfigure guard, SPA 로깅 플래그, 연구 무결성의 health/spm_dict 및
  per-run/per-sequence grain 금지는 환경·제품 계약입니다. 단순 구현 취향으로
  판정하지 않았습니다. health introspection과 dispatcher export/signature
  검증도 phase swap 보호를 위해 보존했습니다.
- `test_non_measurement_params.py`의 `_OUTLIER_MULTIPLIER`는 참조가 없는 상수입니다.
  그러나 관련 설명이 주장하는 중앙값×2 오검출 검증은 현재 6개 테스트가 직접
  계산하지 않습니다. 실제 assertion은 helper 위치·빈도, 1~3 point, 16 초과
  분포입니다. 이 불일치를 요구사항 폐기로 단정하지 않고 해당 파일은 보존했습니다.
  상수의 존재나 현재 suite 성공을 중앙값 회귀 보호의 증거로 표현하지 않습니다.
- 사용되지 않는 fixture는 확인되지 않았습니다. 이름 검색에 한 번만 등장하는
  fake의 method나 Flask route callback도 제품 호출·decorator로 실행되므로
  삭제하지 않았습니다. `fake_redis.py`는 refresh/reader/자체 테스트의 공용
  stateful 대역이고 `tests/_office_state.py`는 실제 office import와 readiness
  두 축을 모두 격리하는 필수 helper입니다.
- `__fixtures__`는 직접 import뿐 아니라 `capture_fixtures.fixture_path()`와
  `check_contract.py`의 endpoint catalog가 동적으로 소비합니다. chat corpus는
  mock provider가 읽습니다. 문자열 파일명 검색에 없다는 이유로 삭제하지
  않았으며 두 공유 JSON 계약도 그대로 유지했습니다.
- 빈 `tests/__init__.py`와 각 테스트 패키지 초기화 파일은 `prepend`의 repo-root
  import와 여러 `test_contract.py`의 이름 충돌 방지에 필요합니다.
  `testpaths = ["tests", "backend"]`, 별도 `_rag` ignore와 CI 명령을 보존했습니다.
  root conftest의 scheduler kill switch·AFM 날짜 고정, backend `.env` loading,
  runtime env/cache 초기화 및 logging 상태 복원도 모두 유지했습니다.

## Claude 협의와 최종 판단

`HERDR_ENV=1`을 확인한 뒤 실제 tab/pane 목록을 조회했습니다.
기존 `claude-review` 탭 `wZ:tK`의 Claude pane `wZ:p11`에 읽기 전용 검토를
요청했습니다. 첫 조회는 sandbox 권한으로 실패했지만 승인된 조회로 대상을
확인했습니다. 수정 권한은 위임하지 않았습니다.

기준 코드, worktree, 삭제 기준, 보호 영역, 남는 검증의 정확한 위치와 실패
시나리오를 요청했습니다. Claude도 `tests/`를 포함한 Python 테스트 모듈 221개와 TS 164개 파일을 정적으로
살펴 확실한 중복 후보를 제시했습니다. 이는 테스트 실행 증거가 아니며 실제
판정과 변경·검증은 실행 에이전트가 수행했습니다.

Claude가 제시한 fresh meta, offset 기본값, `ZZ9000` 후보 3개는 직접 코드와
assertion을 대조해 채택했습니다. AMAT 독립 guard, provider 중복쌍과 미사용
outlier 상수 후보는 보존했습니다. outlier 설명과 실제 assertion의 불일치는
위에 명시했습니다. 보호된 환경 계약과 여러 source-based guard의 보존 판단은
양쪽 검토에서 일치했습니다.

최종 diff를 다시 읽은 Claude는 세 삭제 모두 고유한 실패 시나리오를 잃지 않으며
보호 영역의 수집 설정·fixture에는 영향이 없다고 답했습니다. 보고서의
"backend 221개" 표현은 root `tests/`도 포함한 Python 모듈 수라는 지적을
받아 수정했습니다. Claude가 실행하지 않은 수집·테스트 결과는 실행 에이전트의
로그와 종료 코드로 확인했습니다. 분리된 테스트 이름에 따른 실패 위치의
구분은 줄어들지만 같은 실패가 남는 assertion에서 검출된다는 판단입니다.

## 세 번째 패스: 최종 diff·수집·전체 실행

최종 diff에서 테스트 삭제는 위 3개뿐입니다. backend 수집 node ID 집합의 차이는
`test_fresh_meta_is_live`, `test_unknown_model_is_still_unclassified` 두 개이며
추가 node ID는 없습니다. frontend는 164개 파일을 그대로 유지하며 테스트
등록 수가 1개 줄었습니다. 초기화 파일, fixture/helper, CI, 수집 설정은
변경하지 않았습니다.

| 실행 | 변경 전 | 변경 후 |
| --- | --- | --- |
| backend `--collect-only -q` | 3,891 collected | 3,889 collected |
| backend `ruff check .` | 통과 | 통과 |
| backend 전체 `pytest -q` (최종 `-ra` 추가) | 3,879 passed, 13 skipped, 11 subtests passed | 3,877 passed, 13 skipped, 11 subtests passed |
| frontend 전체 `npm test` | 1,904 passed, 0 skipped | 1,903 passed, 0 skipped |
| frontend `npm run typecheck` | 통과 | 통과 |
| Markdown lint | 해당 없음 | 전체 207개 문서, 0 issues |
| `git diff --check` | 깨끗한 기준선 | 통과 |

실행 환경은 macOS, CPython 3.11.14, Node 24.13.0입니다. 격리 worktree에서는
기존 설치의 `.venv`와 `node_modules`를 symlink로 재사용했으며 source·index는
분리했습니다. 의존성이나 lockfile은 변경하지 않았습니다. frontend Nuxt 타입은
해당 worktree에서 생성했습니다.

### skip와 미검증 환경

backend의 13 skips에는 `test_office_provider_dispatch.py`의 collection 단계
module skip 1개가 포함됩니다. 따라서 3,891 수집 항목에서 3,879 passed와
실행 단계 skip 12개가 나오며, summary에는 collection skip도 합산되어
13개로 표시됩니다. 이 차이는 누락이나 새 skip이 아닙니다.

기존 office adapter 부재·office 입력 미설정·office metadata 전용 테스트의
skip를 보존합니다. 집의 통과는 실제 Redis/OpenSearch, 장비 FTP, 사내 office.py,
Windows console, RAG checkout 및 사내 production 검증을 뜻하지 않습니다.
CPython 3.14 Linux CI도 이번 로컬 실행에서는 검증하지 않았습니다.
실제 사내 adapter가 필요한 테스트는 삭제하거나 home용으로 바꾸지 않았습니다.

이번 변경은 테스트만 삭제하므로 화면 제품 동작 변경은 없습니다. browser 및
production 서비스는 시작하지 않았습니다. 변경 전후 기존 실패와 새 실패는 모두 0건이며 skip 수는 동일합니다.
backend 실행 시간은 기준선 242.37초, 최종 240.70초입니다. 이 차이를
성능 개선으로 주장하지 않습니다. 모든 필수 명령의 종료 코드는 0입니다.

최종 skip 내역은 다음과 같습니다.

| 파일 | 개수 | 조건 |
| --- | --- | --- |
| `tests/test_office_provider_dispatch.py` | 1 | hardware·tttm의 gitignored office.py 부재에 따른 module collection skip입니다. |
| `tests/test_lateral_recipe_local.py` | 1 | office-local 환경 변수가 없습니다. |
| `tests/test_meas_hist_search_local.py` | 2 | office-local OpenSearch 환경 변수가 없습니다. |
| `tests/test_script_conventions.py` | 7 | repo package를 import하지 않는 스크립트는 sys.path bootstrap 검증 대상이 아닙니다. |
| `backend/msr_file/tests/test_contract_gate.py` | 1 | layout metadata는 office provider 전용입니다. |
| `backend/msr_file/tests/test_office_template.py` | 1 | 실제 office.py 복사본의 동기화 검증은 사내에서 수행합니다. |

전체 영역의 목록·분류, 변경별 남는 검증, 수집 차이와 세 번의 검증 패스를
완료했습니다. 불확실한 후보를 삭제하지 않았으며 로컬 성공과 사내 환경 증거를
분리했습니다.
