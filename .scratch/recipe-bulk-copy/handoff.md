# Handoff: 장비 간 레시피 일괄 복사 (설계 미착수)

Status: needs-triage

## 다음 세션이 할 일

장비 간 레시피 복사(배포)를 **어떻게 구현할지** 설계합니다. 아직 아무것도 정해지지
않았고 코드도 없습니다. 첫 산출물은 결정 하나입니다. 무엇을 어디서 실행하는지,
즉 웹 기능인지, `_scheduler` job인지, 별도 프로그램인지를 정하는 것입니다.

## 지금까지 정해진 것 (2026-10-17, user-confirmed)

- 웹 파일 탐색기(`tool-files`)는 **한 장비에서 PC로 파일을 가져오는 일**만 합니다.
  스펙은 `.scratch/tool-files/spec.md`입니다.
- 디스크 일괄 정리와 장비 간 레시피 복사는 그 탐색기에서 **뺐습니다**. 레시피 복사는
  보통 파일 **수백 개**가 움직이는 일이라, HTTP 요청 하나에 태우면 불안정하다는 데
  사용자가 동의했습니다.
- 불안정의 원인은 웹 자체가 아니라 **오래 걸리는 일괄 작업을 요청 스레드에 태우는
  것**이라는 진단입니다(추론, 측정하지 않음). uWSGI 타임아웃이나 탭 종료로 중간에
  끊기면 어디까지 복사됐는지 알 수 없고, 재시도와 이어 하기가 없고, 작업 동안
  worker가 묶입니다(lot_hist 전체 다운로드의 Broken pipe와 같은 계열).

## 열린 질문

1. 복사 단위가 무엇인가요? 레시피 하나가 파일 여러 개(본문, 조건 파일, 이미지)로
   이루어지는지, 그 묶음을 어떻게 알아내는지 모릅니다(`OFFICE-VERIFY`).
2. 대상 장비 수는 보통 몇 대인가요? 계열을 넘는 복사(HITACHI → AMAT)가 있나요?
3. 덮어쓰기 정책은 무엇인가요? 대상에 같은 이름이 있으면 건너뛰기, 덮어쓰기,
   백업 후 덮어쓰기 중 무엇인가요?
4. 실패 시 의미는 무엇인가요? 장비 10대 중 3대가 실패하면 나머지 7대는 그대로 두나요,
   되돌리나요?
5. 누가 실행하나요? `tool-files`의 승인 목록(팀·사번)을 그대로 쓰나요?
6. 실행 장소는 어디인가요? 클라우드 Flask, office PC의 별도 프로그램, `_scheduler`
   job 중 어디인가요? 클라우드에서 장비 FTP로 직접 닿는지, proxy를 거쳐야 하는지가
   이 결정을 좌우합니다(Windows는 proxy, 그 밖은 direct라는 기존 판별 참고).

## 이미 있는 재료 (다시 만들지 말 것)

- `ftp_handler/direct_downloader`의 `FtpFleetDownloader`: 여러 장비 동시 접속,
  `list_dirs`.
- `ftp_handler/proxy`: 방화벽 너머 클라이언트용 HTTP 전송. 서버(`flask_proxy.py`)에
  **업로드 라우트가 이미 있습니다**. `UploadSpec` wire 형식도 있습니다.
- `ftp_handler/web_app`의 `BackgroundJobs`: 웹 요청 밖에서 fleet 작업을 돌리고
  결과를 poll합니다. 요청 스레드 문제의 첫 번째 후보 해법입니다.
- `backend/_scheduler/`: 주기 작업은 정확히 한 프로세스만 실행합니다
  (`docs/deployment.md`의 `lazy-apps`, `enable-threads`).
- `ftp_handler/docs/adr/0001-proxy-batch-sizing.md`: proxy 배치 크기 결정 근거.
- 계열별 FTP 계정과 인코딩 설정은 msr_image config의 `SKEWNONO_TOOL_FTP_*`입니다.
  `tool-files` 작업에서 공용 위치로 옮겨질 예정입니다.
- `ftp_handler/`는 vendored copy입니다. 고치면 upstream `flask_modules`도 같이
  고쳐야 합니다.

## 추천 스킬

- `grilling`: 위 열린 질문을 사용자와 하나씩 확정할 때.
- `codebase-design`: 실행 장소가 정해진 뒤 job 모듈의 seam을 잡을 때.
- `prototype`: `BackgroundJobs`로 파일 수백 개 복사를 mock FTP 위에서 돌려 보고,
  끊김·재시도 동작을 관찰로 판단하고 싶을 때.
- 스펙으로 옮길 때는 `to-spec`, 티켓으로 쪼갤 때는 `to-tickets`.
