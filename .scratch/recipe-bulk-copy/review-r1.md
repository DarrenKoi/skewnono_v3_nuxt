# handoff.md 검토 종합 r1 (2026-10-17)

Claude(`claude-r1.md`)와 Codex(`codex-r1.md`)가 독립적으로 검토한 뒤 대조했습니다.
새 전제: 대상 10대 이상, SKEWNONO는 2 CPU / 8 GiB, 별도 web app 할당 가능,
**운행 중인 서비스 무영향**이 최우선입니다.

## 합의 (둘 다 같은 결론)

1. **worker는 별도 web app에 둡니다.** uWSGI 안의 스레드(`chat`의 `_spawn_daemon`
   선례)는 00:05 reload·`max-requests` 재생성·동승 요청의 harakiri SIGKILL로 끊기고,
   같은 호스트 `attach-daemon`은 CPU·RAM을 그대로 나눠 쓰며 master reload에 같이
   죽습니다. SKEWNONO 증설만으로는 구조 문제가 안 풀립니다. 열린 질문 6은 이것으로
   닫고, handoff 64–65행의 SQLite 분기는 삭제합니다.
2. **두 앱의 결합은 Redis 키 공유뿐입니다.** SKEWNONO = 계획·승인·조회, worker =
   큐 소비·전송·상태 기록의 **유일한 쓰기자**. 앱 간 HTTP 호출은 두지 않습니다.
3. **상태 모델이 handoff에 없고, 이것이 가장 큰 공백입니다.** 단위는
   job → target → bundle → file. 상태는 file(`(job, target, path)`)에만 두고 bundle·
   target·job은 집계합니다. file 상태:
   `pending → in_progress → verified | blocked | failed | uncertain`.
4. **재시작 복구는 재전송이 아니라 실제 대조입니다.** 기동 시 `in_progress`는 전부
   `uncertain`으로 보고, 대상을 읽어 manifest 해시와 같으면 `verified`, 다르면
   `blocked`, 없으면 보호 조건 재확인 후 재시도. 조회 실패는 `uncertain` 유지.
   `put`의 temp+rename 덕분에 원래 이름의 반쪽 파일은 없으므로 이 재판정이 안전합니다.
5. **원본 스냅샷은 한 번 수집해 MinIO 불변 객체로 두고** Redis에는 참조·해시만
   둡니다. 별도 web app은 로컬 디스크가 재시작을 넘긴다는 보장이 없습니다.
   스냅샷 영속이 복구의 전제이고, 재개 때 원본을 다시 읽어 메우지 않습니다.
6. **디렉터리 rename은 "없던 묶음의 게시"에만 씁니다.** `<bundle>.sknn-tmp/`에 다
   올리고 검증한 뒤 최종 경로로 rename. 대상에 같은 폴더가 있으면 그 묶음은
   `blocked`로 끝(이미 확정한 덮어쓰기 차단과 같은 뜻). 기존 폴더를 backup으로 옮기고
   새 폴더를 넣는 두 번 rename은 원자적이지 않으므로 하지 않습니다. 묶음이 여러 루트에
   걸치면(경로 규칙 미확정) 이 방식이 안 되므로 경로 규칙 확정이 선행입니다.
7. **검증은 전수 재다운로드 + SHA-256** 유지. 서버 해시 확장 명령이 확인된 계열만
   그것으로 대체. SIZE·mtime·FTP 응답 코드는 증거가 아닙니다.
8. **장비당 제어 연결 1개 재사용, 파일 순차.** 병목은 RAM이 아니라 왕복 횟수와 장비
   세션 상한입니다. 같은 장비의 job은 직렬화.
9. **Phase 2(office Windows) proxy 쓰기 경로는 범위에서 뺍니다.** 집은 mock, 사무실
   검증은 클라우드 worker에 직접. handoff 97–98행과 124행의 "업로드 라우트" 모순은
   fleet `upload()`(덮어씀)와 탐색기 단일 클라이언트 라우트(쓰기 없음)를 구별해 한
   문장으로 고칩니다. fleet `upload`는 안전한 `put`의 대체물이 아닙니다.
10. **초기 실행자는 앱 관리자로 한정**하고 `grant.level`은 필요해질 때 넣습니다.

## 한쪽만 낸 것, 채택 여부

- Codex: **운전 중 자동 반영을 하지 않는 방식**이 경쟁 조건의 유일한 실질 해법입니다.
  비활성 경로(새 버전 폴더)에 staging만 하고, 활성화는 장비 담당자가 정비 시간에 합니다.
  장비가 staging 폴더를 읽는지, 레시피 선택이 경로 기준인지는 OFFICE-VERIFY. →
  **채택 권고.** 다만 UX가 두 단계가 되므로 사용자 확인이 필요합니다. "복사 = 바이트
  전달"과 "활성화 = 사람"으로 역할을 나누면 handoff 18행의 "운전 중 복사 가능"과
  "실행 중 파일 보호"가 동시에 성립합니다. 거부하면 Claude 안(쓰기 직전 재확인 +
  rename 직후 재확인 + 잔여 위험 문장 명시)이 차선입니다.
- Codex: lease 만료만으로 후임 worker를 띄우면 안 됩니다. 멈춘 전임이 FTP 쓰기를
  재개할 수 있고 FTP는 Redis 세대 번호를 모릅니다. → 채택. worker는 플랫폼 수준에서
  **프로세스 1개**로 고정(`processes=1` 또는 비-WSGI 상시 프로세스)하고, 다중이면
  `_scheduler/election.py` 선출을 재사용합니다. 출처 불명 `.part` 일괄 삭제 금지.
- Codex: Redis 영속성(AOF/fsync·eviction 정책)은 OFFICE-VERIFY. 미완료 job에 TTL 금지.
  → 채택. 승인 기록은 Redis에만 두므로 정책 확인이 먼저입니다.
- Codex: 장비 간 병렬은 **2에서 시작**해 측정 후 올립니다. Claude는 4–8을 냈으나
  세션 상한 미확인이므로 Codex 값을 채택합니다.
- Codex: 수집 전후 목록 비교는 탐지이지 증명이 아닙니다. → 동의. 최소 완화책으로
  유지하고 한계를 스펙에 적습니다.
- Claude: 알림은 새 인프라 대신 `announcements`(`/notices`) 저장소에 개인 대상
  알림 한 종류를 추가. CSV 내보내기·파일 단위 diff 보고·외부 알림·`BackgroundJobs`
  재사용은 v1에서 제외. → Codex 이견 없음, 채택.

## 이견

- Codex는 공유 Redis·MinIO·네트워크 경합까지 측정 못 하면 "무영향"을 판정할 수 없다고
  했습니다. Claude 판단: job 하나가 Redis에 쓰는 양은 파일 수백 × 장비 10대의 작은
  hash 갱신이 수 분에 걸친 것이라 기존 트래픽 대비 무시할 수준입니다. 기록은 하되
  설계 게이트로 두지 않습니다. 장비 FTP 세션 경합(msr_image·tool-files와 같은 장비)은
  실제 문제이므로 8번의 "장비당 연결 1개"와 병렬 2가 그 답입니다.
- Codex의 job 상태 `paused`는 YAGNI. 취소 플래그 하나를 worker가 파일 사이마다 봅니다.

## 다음 세션이 먼저 받아야 할 OFFICE-VERIFY 답안지 (설계 분기를 가르는 것만)

1. 별도 web app: 장비 FTP 대역 직접 도달? 장시간 단일 프로세스 허용? 야간 재기동?
   Redis·MinIO 도달?
2. 장비 FTP(Hitachi, AMAT 각각): 디렉터리 `RNFR/RNTO` 지원? 대상 존재 시 거부?
   세션 상한? 서버 해시 명령?
3. 장비의 레시피 선택 방식: 경로 기준인가, 폴더 스캔인가? staging 폴더를 무시하는가?
   (운전 중 자동 반영 금지 안의 성립 조건)
4. 상태 파일·로그의 경로·형식·갱신 주기(열린 질문 1).
5. Redis 영속성 정책(AOF/fsync, eviction).

## handoff.md에 반영할 편집

- 64–65행 SQLite 분기 삭제, "별도 web app + Redis 원장"으로 치환.
- 97–98행/124행 모순 정리, Phase 2 proxy 쓰기 범위 제외 명시.
- "UI/UX 제안"에 두 단계(복사 → 활성화) 안 추가, 사용자 채택 여부 질문으로.
- 상태 모델 절 신설(위 합의 3–4).
- 53행 CSV, 55–57행 외부 알림, 133행 `BackgroundJobs` prototype 삭제.
- 열린 질문 6 닫음, 위 답안지 5개를 열린 질문 맨 위로.
