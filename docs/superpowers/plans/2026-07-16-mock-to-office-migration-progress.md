# Mock→Office 마이그레이션 진행 현황 (T1–T18 전부 완료)

작성일: 2026-07-16. **업데이트: 오후 6시 세션에서 T11–T18과 최종 전체 리뷰까지
모두 완료했습니다.** T1–T10은 이전 세션에서 완료했고, 이번에 나머지를 이어서
마무리했습니다. 결과: 19개 백엔드 기능 전부가 `SKEWNONO_<기능>_PROVIDER` 환경변수로
mock↔office 전환 가능하며, 최종 리뷰는 "머지 준비 완료(Critical/Important 없음)"
입니다. 백엔드 전체 테스트 69/69 통과. **아직 push하지 않았습니다**(아래 미해결
이슈의 1.6GB blob 정리가 선행되어야 하며, 이는 사용자 결정 사항입니다).

- 플랜: `docs/superpowers/plans/2026-07-16-mock-to-office-migration.md`
- 스펙: `docs/superpowers/specs/2026-07-16-mock-to-office-migration-design.md`
- 실행 원장(git-ignored): `.superpowers/sdd/progress.md` — 태스크별 커밋/리뷰 기록
- 실행 방식: superpowers:subagent-driven-development (태스크별 구현 서브에이전트 + 리뷰 게이트)

## 완료된 작업 (T1–T10, 전부 리뷰 승인)

| 태스크 | 내용 | 커밋 |
| --- | --- | --- |
| T1 | 패리티 스냅샷 하니스 `_parity_snapshot/` (23 엔드포인트, 748KB 골든) | 916733a, 0fa335c, c8d5fe5 |
| T2 | 공용 계약 검증기 `_core/contract_check.py` (15 테스트) | 43ed92f, 9baad2b |
| T3 | `activity` 분리 (모범 예제) | c445b5a, b7c95d4, b0d8cb4 |
| T4 | `admin_logs` 분리 | 8a7ed12, 83a48d5 |
| T5 | `announcements` 분리 | 34c7748, 7d9ad12 |
| T6 | `health` 분리 | a8d7c3e, 5eb2a0a |
| T7 | `api_tokens` 분리 (인증 경로 2개 함수 포함 5개 스위치) | c5fe43b, e03f039, b77fd45, f9355d2 |
| T8 | `access_control` 분리 (미들웨어 강제 경로 포함 6개 스위치) | 6dec204, ec071b8 |
| T9 | `device_statistics` 분리 + recipe_tat `_lot_index` 리포인트 | 30a5d33, 0015c15 |
| T10 | `pm_planning` 분리 (기존 contracts.py 보존) | 8694cec, 2cb0cbd |

중단 시점 테스트 상태: 백엔드 63개 + 패리티 23개 전부 통과. 모든 커밋은 `main`에
있으며 push하지 않았습니다.

## 세션 중 확정된 규칙 (이후 태스크에 그대로 적용할 것)

1. **패리티는 반드시 전체 스위트로만 실행합니다.** `activity`가 하니스 자신의
   요청을 기록하므로 `-k` 부분 실행은 순서 의존으로 깨집니다. 커밋 전:
   `.venv/bin/python -m back_dev_home._parity_snapshot.capture` →
   `.venv/bin/pytest back_dev_home/_parity_snapshot -q`.
2. **저장소 결합 규칙:** 같은 스토어를 쓰는 런타임 함수(인증·강제 경로 등)는
   CRUD와 함께 반드시 스위치합니다. mock 전용으로 남기는 것은 데모 시딩·테스트
   헬퍼뿐입니다. (T7에서 발견, T8부터 선제 적용)
3. **계약 테스트는 자급자족이어야 합니다.** 다른 테스트 파일의 실행 순서에
   의존하지 않고, 필요한 상태는 테스트 안에서 만들고 try/finally로 정리합니다.
4. 변동 필드(`generated_at`, `checked_at`, `timestamp`, `last_seen`,
   `first_seen`)는 하니스가 스크럽합니다. 256KiB 초과 응답은 sha256으로
   고정합니다.
5. 커밋은 기능 폴더 경로만 `git add` 합니다(동시 세션 WIP 보호). push 금지.

## ⚠️ 미해결 이슈

- **git 이력에 1.6GB 골든 blob이 남아 있습니다.** 초기 T1 커밋(916733a)이
  대용량 골든을 참조합니다(현재 트리는 748KB로 정리됨). **push 전에 이력
  정리가 필요합니다.** 이 세션에서 rewrite 시도는 권한 정책으로 중단되었고,
  동시 세션 커밋이 위에 쌓여 있어 단순 amend는 불가합니다.
- 로컬 `main`이 `origin/main`과 분기되어 있습니다(로컬 다수 커밋 + 원격 전용
  커밋 존재). push 전 정리가 필요합니다.

## 완료된 작업 (T11–T18, 전부 리뷰 승인)

| 태스크 | 내용 | 커밋 |
| --- | --- | --- |
| T11 | `recipe_search` 분리 (로컬 ToolType→contracts 이동+재수출) | a2d9dda, f12c76e |
| T12 | `lateral_recipe` 분리 (1개 함수) | 25c1491, 935dea8, 7298af7 |
| T13 | 백필: sem_list, hardware, skew, storage | c4add20 |
| T14 | 백필: meas_hist·recipe_tat·fail_issue(14a) + afm(14b, 파생) | 1d0a625, e5dfb18, c6bd06d |
| T15 | 백필: msr_file (병렬 contracts + 별도 게이트, mock-pin 유지) | 98b42c7 |
| T16 | `docs/office-migration/STATUS.md` 한글 체크리스트 (19행) | cb069f8 |
| T17 | 하니스 삭제 + 전체 검증 + 라이브 확인 + bogus 스모크 | 9d6dbf8, 987760d |
| T18 | `.claude/skills/home-to-office/` 컨벤션 감사 스킬 | 3b874b9 |
| 최종 | 전체 브랜치 리뷰(머지 준비 완료) + Minor 정리 | f9bb780 |

## 최종 상태

- 19개 기능 전부: `data.py` 스위치 + `contracts.py` + `tests/test_contract.py` +
  `MIGRATION.md` 구비. STATUS.md·home-to-office 스킬 반영. 임시 패리티 하니스 제거.
- 백엔드 전체 테스트 69/69 통과. office 네거티브 게이트로 스위치가 office 어댑터에
  도달함을 확인.
- 최종 리뷰(opus): 머지 준비 완료 — Critical/Important 없음. 실행 가능한 Minor는
  모두 수정, 나머지는 사소한 문서/스타일로 수용.
- 상세 이력은 `.superpowers/sdd/progress.md` 원장의 migration 섹션 참고.

## 미해결 (사용자 결정 필요)

- **push하지 않음.** 로컬 main이 origin/main보다 64 커밋 앞서고 2 커밋 뒤처져
  있으며, 이력에 ~1.6GB golden blob(커밋 916733a)이 남아 있습니다. push 전
  이력 정리(사용자 승인 rewrite/squash)가 필요합니다.
