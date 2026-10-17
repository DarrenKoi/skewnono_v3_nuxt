# Handoff: 장비 간 레시피 일괄 복사 (설계 진행 중)

Status: needs-triage

개정 r2 (2026-10-17): `review-r1.md`(Claude+Codex 검토 종합)를 반영했습니다.
두 단계(복사 → 활성화) 안은 사용자가 채택했습니다. 코드는 아직 없습니다.

## 다음 세션이 할 일

아래 "OFFICE-VERIFY 답안지" 다섯 항목의 답을 받은 뒤 `to-spec`으로 스펙을 씁니다.
답이 오기 전에 할 수 있는 일은 상태 모델과 Redis 키 설계, UI 흐름의 초안뿐입니다.
구현이나 장비 검증은 수행하지 않았습니다. 아래 확정 사항은 다시 미정으로 취급하지
않습니다.

## 확정한 결정 (user-confirmed)

### 구조

- **실행 장소는 별도 web app입니다.** 사용자가 할당받을 수 있는 사내 클라우드 web app에
  단일 worker 프로세스를 둡니다. SKEWNONO(2 CPU / 8 GiB, uWSGI `processes=4`)
  안에서는 돌리지 않습니다. 이유: uWSGI 스레드는 00:05 `touch-reload`,
  `max-requests` 재생성, 동승 요청의 harakiri SIGKILL로 끊기고(`chat`의
  `_spawn_daemon` 선례), 같은 호스트 `attach-daemon`은 CPU·RAM을 그대로 나눠 쓰며
  master reload에 같이 죽습니다. 자원 증설은 이 구조 문제를 풀지 못합니다.
- **두 앱의 결합은 office Redis 키 공유뿐입니다.** SKEWNONO는 계획 작성·승인·조회,
  worker는 큐 소비·전송·상태 기록의 **유일한 쓰기자**입니다. 앱 간 HTTP 호출은 두지
  않습니다. 단일 쓰기자이므로 잠금이 없습니다. 쓰기 선례는 `_scheduler/redis_jobs.py`,
  앱 소유 상태 선례는 `api_tokens`·`access_control`·`announcements`입니다.
- worker는 **프로세스 1개**로 고정합니다(`processes=1` 또는 비-WSGI 상시 프로세스).
  플랫폼이 여러 프로세스를 띄우면 `_scheduler/election.py`의 선출을 재사용합니다.
  lease 만료만 보고 후임을 띄우지 않습니다. 멈춘 전임이 FTP 쓰기를 재개할 수 있고
  FTP는 Redis 세대 번호를 모르기 때문입니다.
- 원본 스냅샷은 **MinIO 불변 객체**로 두고 Redis에는 참조와 해시만 둡니다. 별도
  web app의 로컬 디스크가 재시작을 넘긴다는 보장이 없습니다.
- Phase 2(office Windows, proxy 경유) 쓰기 경로는 **범위에서 뺍니다.** 집은 mock FTP,
  사무실 검증은 클라우드 worker에 직접 합니다. proxy 쓰기와 인증은 설계하지 않습니다.

### 두 단계: 복사 → 활성화

- **worker는 바이트를 비활성 경로에 전달만 하고, 활성화는 사람이 합니다.** 대상
  장비에 `<bundle>`이 없으면 `<bundle>.sknn-tmp/`(이름 규칙은 스펙에서 확정)에 전부
  올리고 검증한 뒤 **최종 경로로 rename까지 worker가 합니다.** 그 폴더가 장비에서
  "활성" 레시피가 되는 것은 장비 담당자가 정비 시간에 장비 쪽에서 선택할 때입니다.
- 이 분리로 handoff r1의 "운전 중 복사 가능"과 "실행 중 파일 보호"가 동시에
  성립합니다. 장비가 실행 중인 레시피의 폴더에는 어떤 쓰기도 하지 않습니다.
- **대상에 같은 이름의 폴더가 이미 있으면 그 묶음은 `blocked`로 끝입니다.** 파일
  단위 diff는 하지 않습니다. 기존 폴더를 backup으로 옮기고 새 폴더를 넣는 두 번의
  rename은 원자적이지 않으므로 금지합니다. 덮어쓰기 차단 결정은 그대로입니다.
- 성립 조건(OFFICE-VERIFY 3): 장비가 레시피를 경로 기준으로 선택하고, 이름이 다른
  staging 폴더를 자동으로 읽지 않아야 합니다. 디렉터리 `RNFR/RNTO`가 안 되는 계열은
  파일별 `put`으로 후퇴하되 묶음 원자성은 포기한 것으로 스펙에 적습니다.
- 잔여 위험을 스펙에 문장으로 남깁니다: 장비가 staging 폴더나 rename 직후의 새
  폴더를 사람의 활성화 없이 읽는 계열이 있다면 이 보호는 성립하지 않으며, 그 계열은
  자동 배포 대상에서 뺍니다.

### 정책 (r1에서 확정, 유지)

- 레시피 하나는 여러 파일과 폴더의 묶음입니다. 묶음을 식별하는 경로 규칙은 미확정이며,
  **묶음이 여러 루트에 걸치면 폴더 게시 방식이 안 되므로 경로 규칙 확정이 선행**입니다.
- 현재 실행 중인 레시피·파일 정보는 장비의 상태 파일·로그에서 읽을 수 있습니다.
  로그에는 레시피 이름만 나오고 전체 경로는 나오지 않습니다. 이름에 대응하는 경로는
  API 또는 장비 내 txt 파일로 확인할 예정입니다(연동 수단 미확정). 두 단계 안에서는
  이 정보가 "쓰기 금지 폴더" 판정에만 쓰입니다.
- 개별 문제로 작업 전체를 조기 중단하지 않고, 전송 가능한 나머지 대상을 계속
  처리합니다. 마지막에 전체 계획 대비 결과를 검토하여 사용자에게 알립니다.
- 검증은 **전수 재다운로드 + SHA-256**입니다. 서버 해시 명령이 확인된 계열만
  그것으로 대체합니다. SIZE·mtime·FTP 응답 코드는 완료의 증거가 아닙니다.
- 초기 실행자는 **앱 관리자**로 한정합니다. `tool-files` grant의 `level` 필드는
  필요해질 때 넣습니다.

## 상태 모델 (설계 초안, 스펙으로 옮길 것)

- 단위: job → target(장비) → bundle(묶음) → file. **상태는 file에만 둡니다.**
  bundle·target·job 상태는 집계로 계산하고 저장하지 않습니다.
- file 키: `(job_id, target_eqp, destination_path)`.
  상태: `pending → in_progress → verified | blocked | failed | uncertain`.
  `TransferUncertain`(`FtpClient.put`의 rename 응답 유실)이 `uncertain`의 출처입니다.
- job 기록: 실행자, 승인자, 승인 시각, manifest(상대 경로·크기·해시 목록) 해시,
  MinIO 스냅샷 참조, 원본·대상 장비 식별, 취소 플래그.
- 저장: job 하나당 Redis hash 하나(field = file 키, 값 = 작은 JSON). 큐는 Redis
  리스트 하나(`LPUSH`/`BRPOP`). 승인과 enqueue는 하나의 원자 연산으로 묶습니다.
  미완료 job에는 TTL을 두지 않습니다. 취소는 worker가 파일 사이마다 플래그를 봅니다.
  `paused` 상태는 두지 않습니다.
- **재시작 복구는 재전송이 아니라 대조입니다.** 기동 시 `in_progress`를 전부
  `uncertain`으로 보고, 대상을 읽어 manifest 해시와 같으면 `verified`, 다르면
  `blocked`, 없으면 `pending`으로 되돌립니다. 조회 실패는 `uncertain`을 유지합니다.
  `put`의 temp+rename 덕분에 원래 이름의 반쪽 파일은 없으므로 이 재판정이 안전합니다.
  출처를 모르는 임시 파일을 일괄 삭제하는 복구는 금지합니다.
- 재개 때 원본을 다시 읽어 누락을 메우지 않습니다. 같은 스냅샷만 씁니다. 스냅샷이
  없어졌으면 새 계획과 새 승인이 필요합니다.

## 동시성과 자원

- 파일은 KB–수 MB(ADR 0001의 프로파일)이므로 병목은 RAM이 아니라 **왕복 횟수와 장비
  FTP 세션 상한**입니다. 장비당 제어 연결 1개를 재사용하고 파일은 순차 처리합니다.
- 장비 간 병렬은 **2에서 시작**해 세션 상한과 다른 기능(`msr_image`, `tool-files`)의
  동시 접속을 확인한 뒤 올립니다. 같은 장비의 job은 직렬화합니다.
- 원본 수집은 한 번, worker에서 합니다. 수집 전후 목록(크기·mtime)을 비교해 다르면
  한 번 더 수집, 또 다르면 차단합니다. 이것은 탐지이지 증명이 아니며, 잠금 없는 동시
  수정에 대한 한계를 스펙에 적습니다.
- 전송별 크기·시간·재시도·총 바이트 상한을 둡니다. 스냅샷에서 파일 단위로 공급하고
  `UploadSpec`/base64 JSON에 전체를 펼치지 않습니다.

## UI/UX (추천, 미채택)

- 파일 탐색기와 분리된 레시피 배포 전용 페이지입니다. URL·기능 slug는 미정입니다.
- 작업 목록: 실행자, 대상 장비 수, 진행 상태, 생성 시각.
- 새 배포: 원본 장비·레시피 묶음 선택 → 대상 장비 다중 선택 → 원본 스냅샷 수집·검증 →
  고정된 계획 승인. 파일 수백 개를 직접 고르게 하지 않습니다.
- 작업 상세: 장비 → 묶음 순서로 펼치고, 파일 단계는 접힌 기본값으로 두어 실패·
  불명확 파일만 펼칩니다. 탭 종료와 무관하게 계속되며, 재방문하면 서버에서 조회합니다.
  처리율 100%와 전체 성공을 구분하고, **"전달 완료"와 "장비에서 활성화됨"을 구분**해
  표시합니다. 활성화는 이 앱이 알 수 없으므로 "담당자 활성화 필요" 안내로 끝납니다.
- 최종 검토: 승인 계획과 결과를 대조해 누락, 검증 실패, 충돌, 보호 폴더, 결과
  불명확을 표시하고 원인과 다음 행동을 제시합니다. 재시도는 현재 상태를 다시 확인한
  새 계획으로 진행합니다.
- 알림: `announcements`(`/notices`) 저장소에 개인 대상 알림 한 종류를 추가합니다.
  새 인프라를 만들지 않습니다. 메일·Teams·브라우저 푸시, 결과 CSV는 v1 제외입니다.

## OFFICE-VERIFY 답안지 (설계 분기를 가르는 것, 스펙 전에 답을 받을 것)

1. 별도 web app: 장비 FTP 대역에 직접 닿는가? 장시간 단일 프로세스를 허용하는가?
   야간 재기동 정책이 있는가? office Redis와 MinIO에 닿는가?
2. 장비 FTP(Hitachi, AMAT 각각): 디렉터리 `RNFR/RNTO`를 지원하는가? 대상이 있으면
   거부하는가? 세션 상한은? 서버 해시 명령(`XMD5`/`XCRC`)이 있는가?
3. 장비의 레시피 선택 방식: 경로 기준인가, 폴더 스캔인가? 이름이 다른 staging
   폴더를 무시하는가? (두 단계 안의 성립 조건)
4. 상태 파일·로그의 실제 경로, 형식, 갱신 주기. 레시피 이름 → 묶음 경로 매핑의
   유일성과 최신성.
5. office Redis의 영속성 정책(AOF/fsync, eviction). 승인 기록이 Redis에만 있습니다.

## 열린 질문 (답안지 뒤에)

1. 레시피 묶음의 경로 규칙. 여러 루트에 걸치는 묶음이 있는가?
2. 대상 장비 수의 통상값. 계열을 넘는 복사(HITACHI → AMAT)가 있는가?
3. 충돌(`blocked`) 묶음과 도중 실패(부분 반영) 묶음을 화면에서 어떻게 구분해 보여
   주는가.

## 이미 있는 재료 (다시 만들지 말 것)

- `ftp_handler/core/client.py`의 `FtpClient.put`: 덮어쓰기 거부, 임시 이름 업로드 후
  rename, `TargetExists`·`TransferUncertain`. **재사용하는 유일한 쓰기 경로입니다.**
  디렉터리 생성 API는 없으므로 추가가 필요합니다(upstream `flask_modules`도 함께).
- `ftp_handler/direct_downloader`의 `FtpFleetDownloader`: `list_dirs`와 다운로드.
  fleet `upload`는 **덮어쓰는 STOR**이라 쓰지 않습니다.
- `ftp_handler/proxy/flask_proxy.py`: fleet `upload()` 라우트는 있으나 덮어쓰며,
  탐색기용 단일 클라이언트 라우트에는 쓰기가 없습니다. 둘 다 이 기능에서 쓰지 않습니다.
- `ftp_handler/web_app`의 `BackgroundJobs`: 메모리 기반·단일 프로세스. 영속 큐와
  역할이 겹치고 복구를 못 하므로 쓰지 않습니다.
- `backend/_scheduler/election.py`: 프로세스 1개 선출. worker가 다중 프로세스일 때 재사용.
- `backend/_scheduler/redis_jobs.py`: 앱 소유 상태의 Redis 쓰기 선례.
- `backend/announcements`: 알림 저장소.
- `ftp_handler/docs/adr/0001-proxy-batch-sizing.md`: 파일 프로파일(KB–수 MB, 큰
  파일은 소수 장비). 그 ADR의 harakiri·RSS 수치는 다른 앱의 것이라 옮기지 않습니다.
- 계열별 FTP 계정과 인코딩 설정은 msr_image config의 `SKEWNONO_TOOL_FTP_*`입니다.
  `tool-files` 작업에서 공용 위치로 옮겨질 예정입니다. worker app도 같은 값을 읽습니다.
- `.scratch/tool-files/spec.md` r2의 공용 부품: 권한 판정, 장비 해석(sem_list 행에서
  IP·fab·모델·FTP 계정), 경로 검증. worker는 서버 측 장비 해석·경로 검증을 재사용하고,
  승인·실행·재개 시 권한과 쓰기 중지 플래그를 다시 확인합니다.
- `ftp_handler/`는 vendored copy입니다. 고치면 upstream `flask_modules`도 같이 고칩니다.

## 검토 기록

- `review-r1.md`: Claude(`claude-r1.md`)와 Codex(`codex-r1.md`)의 독립 검토를 대조한
  종합. 합의 10개, 한쪽 제안의 채택 여부, 이견 2개가 있습니다.

## 추천 스킬

- `grilling`: 답안지와 열린 질문을 사용자와 확정할 때.
- `codebase-design`: worker 모듈과 SKEWNONO 쪽 조회 API의 seam을 잡을 때.
- 스펙으로 옮길 때는 `to-spec`, 티켓으로 쪼갤 때는 `to-tickets`.
