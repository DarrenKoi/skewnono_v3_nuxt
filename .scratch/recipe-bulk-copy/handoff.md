# Handoff: 레시피 횡전개 앱 `recipe-copy` (설계 확정, 스펙 전)

Status: needs-triage

개정 r3 (2026-10-18): `grilling` 세션으로 r2의 미정 항목을 전부 닫았습니다. r2의
구조(SKEWNONO + 별도 worker, Redis 공유, 두 단계 복사)는 **폐기**되었고, 독립
web app 하나로 다시 정했습니다. 코드는 아직 없습니다. 폴더 이름
`recipe-bulk-copy`는 그대로 두고, 앱 이름만 `recipe-copy`입니다.

## 다음 세션이 할 일

`to-spec`으로 스펙을 씁니다. 아래 OFFICE-VERIFY 세 항목은 스펙을 막지 않습니다.
스펙은 "도달한다 / 레이아웃은 아래와 같다 / RNTO가 기존 파일을 덮는다"를 가정으로
적고, 답이 다르면 바뀌는 지점을 문장으로 표시합니다. 아래 확정 사항은 다시 미정으로
취급하지 않습니다.

## 배경 (user-confirmed 2026-10-18)

- MI 엔지니어만 쓰는 특수 목적 앱입니다. 레시피가 **매일 20~30개** 만들어지고 여러
  장비로 복사하는 일(**횡전개**)이 잦습니다. 레시피는 당일 만들어져 바로 복사되므로
  Redis registry 같은 지연된 목록은 쓸 수 없고, 장비 FTP를 실시간으로 봐야 합니다.
- SKEWNONO와 **서비스 목적이 달라** 별개로 운영합니다. SKEWNONO에는 상단 메뉴의
  외부 링크 하나("레시피 복사")만 둡니다.

## 확정한 결정 (user-confirmed 2026-10-18)

### 앱 구조

- **독립 web app 하나**(`recipe-copy`)에 검색·선택·확인·전송·결과 화면이 전부
  있습니다. 사내 클라우드 web app 슬롯 하나를 새로 받습니다.
- uWSGI는 `processes=1`, `threads=4`(화면 요청용), `enable-threads`, `lazy-apps`.
  **`touch-reload`와 `max-requests`는 두지 않습니다.** harakiri는 요청 단위라 전송
  스레드와 무관합니다. 전송 소비 스레드는 앱 부팅 때 하나 띄웁니다.
- 프로세스가 하나이므로 **상태 공유용 Redis가 필요 없습니다.** job·file 상태는
  로컬 **SQLite**(SKEWNONO `chat/store.py` 선례), 원본 스냅샷은 **로컬 임시
  폴더**(클라우드 스토리지 100 GB 여유)입니다. office Redis는 `sem_list`(장비
  IP·fab·모델·FTP 계정) **읽기 전용**으로만 씁니다.
- 스택은 새 repo, Flask가 빌드된 Nuxt SPA를 서빙하는 SKEWNONO와 같은 모양입니다.
  `_spa/`, `_auth/`, `_runtime/office_redis.py`, vendored `ftp_handler/`를
  **복사**합니다. 공용 패키지로 빼지 않습니다. repo는 SKEWNONO처럼 public(사무실은
  GitHub 로그인을 못 하므로 익명 pull).
- **Flask이지 FastAPI가 아닙니다** (user-confirmed 2026-10-18). 안정성은 프레임워크가
  아니라 `processes=1`·재기동 없음·파일별 temp+rename·대조 복구에서 나옵니다.
  async는 쓸 곳이 없습니다: `ftp_handler`가 동기 `ftplib`이라 threadpool로 감싸야
  하고, 동시성은 장비당 스레드로 이미 충분하며, 슬롯이 uWSGI 모양이라 ASGI는
  배포 절차를 바꿉니다. 복사할 플러밍도 전부 Flask입니다.
- Phase 2(office Windows, proxy 경유)는 범위 밖입니다. 집은 mock FTP, 검증은
  클라우드에서 직접 합니다.

#### SKEWNONO 안에서 돌리지 않는 이유 (r2에서 가져옴)

CPU가 아니라 **프로세스 수명**입니다. SKEWNONO worker 1의 스레드는 00:05
`touch-reload`, `max-requests=1000` 재생성, 동승 요청의 harakiri SIGKILL로
끊깁니다. 복구 설계가 있어 견딜 수는 있지만, 서비스 목적이 다르다는 이유가 더 큽니다.
자원·동시 처리량은 어느 쪽이든 같습니다(전송은 I/O 대기, 스레드는 요청 슬롯을
쓰지 않음).

### 레시피의 정의 (Hitachi 전용)

경로 사용자 설정은 **없습니다.** 원본과 **동일한 경로**에 놓습니다.

```text
/HITACHI/DEVICE/HD/{class_name}/data/{idw}/
    ├── {idp}.idp     ← 항상 포함
    └── {idp}/        ← raw 폴더, 항상 포함 (전체)
{idw}.idw             ← idp보다 상위 폴더, 여러 idp가 공유 → 옵션, 기본 끔
```

- `.idw`를 켜면 "다른 레시피도 영향받음" 문구를 붙입니다.
- 정확한 `.idw` 파일 위치와 raw 폴더의 확장자 목록은 OFFICE-VERIFY 2입니다.
  규칙은 코드에 고정하고 사용자 설정은 두지 않습니다.
- 다른 계열(AMAT)은 범위 밖입니다. 이 앱은 Hitachi 전용으로 개발합니다.

### 화면 흐름

1. **원본 장비**를 `sem_list`의 Hitachi 장비에서 고릅니다(fab 무관).
2. **class**를 고르고 그 `data/` 아래를 이름으로 거릅니다. 왕복은 LIST 1회입니다.
   테이블 열은 그 LIST로 얻는 것만: 레시피 이름(idp), 수정 시각, idw 이름.
   파일 수·총 크기는 행을 클릭했을 때 raw 폴더를 LIST해서 보여 줍니다.
3. 레시피 **여러 행** × 대상 장비 **여러 대** = job 하나. 대상은 Hitachi 장비이고
   **다른 fab도 허용**합니다.
4. 확인 팝업 (실행자 본인이 확인하며, 별도 승인자는 없습니다):
   - 대상에 같은 `{class_name}` 폴더가 **없으면** "만들까요?" (예 → 폴더 생성 후 진행).
   - 다른 fab의 대상에 같은 class 폴더가 **있으면** "이미 같은 class가 있으니 복사에
     주의" 팝업 뒤 진행.
   - 대상에 같은 레시피가 **이미 있으면** 알리고 **덮어쓰기** 허용(fab 무관).
5. 전송 → 검증 → 결과. 작업 목록에 진행 중/완료/실패, 열어 둔 상세 화면은 몇 초마다
   조회해 끝나면 요약을 띄웁니다. 통지는 **앱 안에서만**. 메일·Teams·푸시 없음.
6. 결과는 장비 → 레시피 → 파일 순으로 펼치고, 장비별 세 상태를 구분합니다.
   (1) 전부 검증됨(한 줄로 접힘), (2) 일부 실패(어느 파일이 왜), (3) 불명확(장비에서
   직접 확인). 처리율 100%와 전체 성공을 구분합니다. 재시도는 실패 장비만 골라
   **새 job**으로 보냅니다. "담당자 활성화 필요" 안내는 **없습니다.**

### 쓰기 규칙

- 유일한 쓰기 경로는 `FtpClient.put`(임시 이름 업로드 → rename)입니다. 파일 단위라
  반쪽 파일이 원래 이름으로 남지 않습니다.
- **덮어쓰기 모드 추가**: temp 업로드 → 기존 파일 `DELE` → `RNTO`. 그 사이 파일이
  잠깐 없는 순간은 사용자가 덮어쓰기를 확인한 뒤이므로 허용합니다.
- 대상 raw 폴더에 원본에 없는 파일은 **두고** "대상에만 있는 파일 n개"로 표시합니다.
- 디렉터리 생성 API가 없으므로 `FtpClient.mkdir`을 추가합니다(`{idp}/` raw 폴더,
  class 폴더). vendored 사본과 upstream `flask_modules`를 함께 고칩니다.
- 검증은 **전수 재다운로드 + SHA-256**. SIZE·mtime·응답 코드는 증거가 아닙니다.

### 동시성

- 원본은 job당 **한 번** 읽어 로컬 스냅샷에 둡니다. 수집 전후 목록(크기·mtime)이
  다르면 한 번 더 수집, 또 다르면 차단합니다(탐지이지 증명이 아님, 스펙에 명시).
- **장비당 스레드 1개·FTP 연결 1개**, 한 job은 대상 수만큼 **동시에** 보냅니다.
  15대면 전체 시간은 가장 느린 1대의 시간에 가깝습니다. 한 장비 안에서 파일은
  순차입니다.
- 상한은 job 하나가 아니라 **동시에 도는 job 전체의 스레드 합**(설정값, 기본 32)에
  두고, 넘치면 뒤 job이 기다립니다.
- 큐는 FIFO. 같은 장비(원본이든 대상이든)가 겹치는 job은 앞 job이 끝날 때까지
  기다리고, 겹치지 않는 job은 같이 돕니다. 화면에 "대기 n번째"를 표시합니다.
- 전송별 크기·시간·재시도·총 바이트 상한을 둡니다.

### 상태 모델 (r2 유지, 저장소만 SQLite)

- 단위: job → target(장비) → recipe → file. **상태는 file에만 둡니다.** 상위 상태는
  집계로 계산합니다.
- file 키: `(job_id, target_eqp, destination_path)`.
  상태: `pending → in_progress → verified | failed | uncertain`.
  `TransferUncertain`(`put`의 rename 응답 유실)이 `uncertain`의 출처입니다.
  r2의 `blocked`는 덮어쓰기 허용으로 사라졌습니다.
- job 기록: 실행자, 확인 시각, manifest(상대 경로·크기·해시) 해시, 스냅샷 폴더,
  원본·대상 장비, 취소 플래그. 취소는 파일 사이마다 봅니다. `paused`는 없습니다.
- **재시작 복구는 재전송이 아니라 대조입니다.** 기동 시 `in_progress`를 전부
  `uncertain`으로 보고, 대상을 읽어 manifest 해시와 같으면 `verified`, 다르거나
  없으면 `pending`으로 되돌립니다. 조회 실패는 `uncertain` 유지. 출처 모를 임시
  파일 일괄 삭제는 금지입니다.
- 스냅샷 수명: 전부 `verified`로 끝난 job은 즉시 삭제, 실패·불명확이 남은 job은
  사용자가 닫을 때 삭제. 총량 상한(기본 20 GB)을 넘으면 새 job을 거부합니다.
  재기동으로 스냅샷이 사라진 job은 `pending`부터 다시 수집합니다.

### 권한

- 신원은 SKEWNONO와 같은 `LASTUSER` 쿠키입니다(새 슬롯이 같은 게이트웨이 뒤인지는
  OFFICE-VERIFY 1).
- v1은 **MI 엔지니어 허용 목록**을 `.env`에 두고 배포 때 고칩니다. 목록이 자주
  바뀌면 관리자 화면을 넣습니다.

## r2에서 폐기된 것 (다시 꺼내지 말 것)

| r2 결정 | 폐기 이유 |
| --- | --- |
| SKEWNONO가 계획·승인·조회, 별도 worker가 전송 | 서비스 목적이 달라 앱 전체를 분리 |
| Redis hash + 리스트 큐, MinIO 스냅샷 | 프로세스가 하나라 공유할 상대가 없음 |
| 두 단계(staging 폴더 → rename → 사람 활성화) | 레시피가 폴더 하나가 아님. 활성화 단계도 실제로 없음 |
| 같은 이름 존재 시 `blocked`, 덮어쓰기 금지 | 사용자 확인 후 덮어쓰기 허용 |
| 상태 파일·로그로 실행 중 레시피 판정 | 사용자 확인이 그 역할. v2에서 필요하면 재검토 |
| 장비 간 병렬 "2에서 시작" | 장비당 연결이 1개라는 사실이 드러나 성능만 깎음 |
| 실행자는 앱 관리자만 | MI 엔지니어 허용 목록 |
| `announcements`(`/notices`) 알림 | 앱 안 작업 목록으로 충분 |
| 단일 루트 묶음 가정, 다중 루트 미정 | idp·idw·raw의 층이 다른 것이 정상 |
| Redis 영속성 확인(답안지 5) | SQLite로 바뀌어 무관 |

## OFFICE-VERIFY 답안지 (스펙을 막지 않음, 답이 다르면 해당 지점만 수정)

1. 새 web app 슬롯: 장비 FTP 대역에 직접 닿는가? office Redis(읽기)에 닿는가?
   `LASTUSER` 쿠키가 같은 게이트웨이를 거쳐 오는가? 야간 재기동 정책이 있는가
   (있어도 복구 설계로 견딤, 알아만 둠)?
2. 레이아웃: `.idw` 파일의 정확한 경로. raw 폴더 `{idp}/`의 실제 내용과 확장자.
   복사에서 빼야 할 파일이 있는가?
3. Hitachi FTP: `RNTO`가 기존 파일을 덮는가(아니면 `DELE` 뒤 `RNTO`)? `MKD`가
   되는가? 한 장비에 동시에 열 수 있는 세션 수(같은 장비를 `msr_image`도 1개 씀)?

## 이미 있는 재료 (다시 만들지 말 것)

- `ftp_handler/core/client.py`의 `FtpClient.put`: 임시 이름 업로드 후 rename,
  `TargetExists`·`TransferUncertain`. **덮어쓰기 모드와 `mkdir`을 추가**하고
  upstream `flask_modules`도 같이 고칩니다.
- `ftp_handler/direct_downloader`의 `FtpFleetDownloader`: `list_dirs`와 다운로드.
  fleet `upload`는 덮어쓰는 STOR이라 쓰지 않습니다.
- `ftp_handler/web_app`의 `BackgroundJobs`: 메모리 기반이라 복구를 못 하므로 쓰지 않습니다.
- `backend/chat/store.py`: 로컬 SQLite 저장소 선례.
- `backend/_spa/`, `_auth/`, `_runtime/office_redis.py`: 복사할 플러밍.
- `backend/sem_list/providers/office_example.py`: Redis parquet에서 장비 목록을 읽는 법.
- `docs/datatables/hitachi/recipe_idp.txt`: 레이아웃과 stem 규칙(office 확인 2026-07-27).
  `msr_image_ftp.txt`: 접속 계정·root. 계열별 FTP 설정은 `SKEWNONO_TOOL_FTP_*`.
- `ftp_handler/docs/adr/0001-proxy-batch-sizing.md`: 파일 프로파일(KB–수 MB).
- `.scratch/tool-files/spec.md` r2: 장비 해석(sem_list 행에서 IP·fab·모델·FTP 계정)과
  경로 검증 부품. 새 앱이 서버 측 로직을 복사합니다.

## 검토 기록

- `review-r1.md`: Claude(`claude-r1.md`)와 Codex(`codex-r1.md`)의 r1 검토 종합.
  r1·r2의 구조 결정은 r3에서 대부분 폐기되었으나, 상태 모델·검증·복구 규칙은 거기서
  왔습니다.

## 추천 스킬

- `to-spec`: 이 문서를 스펙으로. 새 repo 생성 전에 스펙을 먼저 씁니다.
- `codebase-design`: 소비 스레드·FTP 쓰기·SQLite 저장소의 seam을 잡을 때.
- `to-tickets`: 스펙 뒤 티켓으로 쪼갤 때.
