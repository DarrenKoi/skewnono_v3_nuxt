# FTP 한글(cp949) 파일명 대응

- 일시: 2026-10-14 09:43 KST
- 상태: 코드 완료 및 push. 사무실 작업 2건(proxy 호스트 재배포, env 설정) 대기
- 스킬: `mattpocock-skills:tdd` 방식(회귀 테스트 먼저 red 확인), `herdr`(Codex 리뷰)

## 1. 요약

Windows 장비 FTP의 한글(cp949) 파일명 때문에 listing이 전부 실패하던 문제를 고쳤다.
`ftp_handler`에 `encoding` 옵션을 넣고 SKEWNONO에 `SKEWNONO_TOOL_FTP_ENCODING` env를
추가했다. 기본값은 utf-8이라 사무실에서 env를 설정하고 proxy 호스트를 재배포해야
실제로 해결된다.

## 2. 진행 사항

- 사용자는 "`flask_proxy`에 cp949 처리를 넣어야 한다"고 했지만, 코드를 따라가 보니
  `ftp_handler/proxy/flask_proxy.py`에는 FTP 코드가 없었다. JSON을 받아
  `FtpFleetDownloader`에 넘기는 래퍼일 뿐이다.
- 실제 디코딩 위치는 `ftp_handler/direct_downloader/fleet_downloader.py`의
  `_session()`이다. proxy와 direct가 같은 함수를 쓰므로 direct(클라우드)도 똑같이
  깨져 있었다. `core/client.py`의 `FtpClient`도 마찬가지였다.
- 실패 과정: `ftplib.FTP`의 `encoding` 기본값은 utf-8 strict이다. cp949 바이트를
  디코딩하다 `UnicodeDecodeError`가 나고, 이것이 `ValueError` 하위 클래스라
  `_FTP_ERRORS`에 걸려 listing 단위 실패로 기록된다. `nlst()`는 전체 줄을 한꺼번에
  읽으므로 한글 파일 하나가 디렉터리 전체를 실패시킨다.
- RETR도 문제였다. ftplib은 명령어도 같은 코덱으로 인코딩하므로, 한글 경로가
  utf-8 바이트로 나가 cp949 서버가 550으로 응답한다.
- 테스트는 upstream `flask_modules`에 먼저 썼다. 기존 FakeFTP는 ftplib 자체를
  대체해서 이 버그를 재현할 수 없었다. 그래서 cp949로 응답하는 작은 FTP 서버를
  loopback에 띄워 진짜 ftplib으로 검증하는 `tests/test_ftp_encoding.py`를 만들었다.
- red 확인 중 예상과 다른 점이 하나 나왔다. utf-8 기본값 케이스가 host 실패가 아니라
  빈 `HostListing`과 listing 단위 `HostFailure`를 반환했다. office가 보고한 에러
  문구와 같았고, 테스트 단언을 실제 동작에 맞췄다.
- `encoding` 인자를 추가하자 기존 FakeFTP들이 `TypeError`를 냈다(upstream 3개 파일,
  SKEWNONO `tests/test_vendored_ftp_handler.py` 14건 실패). ftplib 시그니처를 흉내
  내는 fake라서 `encoding` kwarg를 받도록 고쳤다.
- upstream을 고친 뒤 `rsync -a --delete --exclude=__pycache__`로 worktree
  `../skewnono-ftp-cp949`에 동기화했다. 수정 전 두 복사본은 `diff -rq`로 동일했다.
- Codex 리뷰를 herdr pane에서 돌렸다. 결과는 SHIP이었고 should 2건을 반영했다.
  Codex는 신/구 클라이언트와 신/구 proxy 4가지 조합을 loopback FTP로 재현했다.
- merge 직전 다른 세션이 `main`에 logging 커밋(`fb9f3ee9`)을 올려 ff가 실패했다.
  worktree를 rebase하고 관련 테스트 991개를 다시 돌린 뒤 merge했다.
- 사무실 전달 문서를 `docs/office-migration/`에 저장했다.

## 3. 수정 내용

flask_modules (`fd25c6d`, push 완료):

- 수정: `ftp_handler/direct_downloader/fleet_downloader.py` — `__init__`에 `encoding`,
  `_session()`에서 `FTP(timeout=..., encoding=self.encoding)`
- 수정: `ftp_handler/core/client.py` — `FtpClient`에 `encoding`
- 수정: `ftp_handler/proxy/proxy_downloader.py` — `encoding` 인자, `_tuning()`에 실어 보냄
- 수정: `ftp_handler/proxy/flask_proxy.py` — `_downloader_from`이 `body.get("encoding", "utf-8")`
- 신규: `tests/test_ftp_encoding.py` — cp949 loopback FTP 서버 테스트 5개
- 수정: `tests/test_ftp_client.py`, `test_ftp_flask_proxy.py`, `test_ftp_fleet_downloader.py`
  — FakeFTP가 `encoding` kwarg를 받음

skewnono (`c2f60835`, 문서 `f35e216d`, push 완료):

- 수정: `ftp_handler/` 4개 파일 — upstream과 동일
- 수정: `backend/msr_image/config.py` — `ImageConfig.ftp_encoding`, `_encoding()` 검증
- 수정: `backend/msr_image/providers/office_example.py`,
  `backend/ebeam/recipe_search/providers/office_example.py` — `_downloader`가 `encoding` 전달
- 수정: `backend/msr_image/tests/test_config.py`, `test_office_template.py`,
  `tests/test_vendored_ftp_handler.py`
- 수정: `backend/.env.example`, `backend/msr_image/MIGRATION.md`, `docs/deployment-ftp-proxy.md`
- 신규: `.scratch/ftp-cp949-261014/BRIEF.md`, `codex-review.md`
- 신규: `docs/office-migration/to-office-ftp-cp949-261014.md`

검증: upstream 479개 통과, SKEWNONO 전체 3957개 통과, ruff와 `npm run lint:md` 통과.

## 4. 결정 사항과 근거

- **수정 위치는 `flask_proxy`가 아니라 `FtpFleetDownloader._session()`.** proxy,
  direct, msr_image, recipe_search가 모두 이 함수를 지나므로 한 곳만 고치면 된다.
  proxy에만 처리를 넣었다면 클라우드 direct 경로가 그대로 깨져 있었을 것이다.
- **라이브러리 기본값은 utf-8 유지.** `flask_modules`는 다른 프로젝트도 쓴다.
  기본값을 cp949로 바꾸면 utf-8 서버의 한글 이름이 깨진다.
- **SKEWNONO 기본값도 utf-8, env로 cp949를 켠다 (사용자 결정).** 대안은 SKEWNONO
  기본값을 cp949로 두는 것이었다. 배포 즉시 해결되지만, 지금 UTF-8 한글 이름으로
  잘 도는 서버가 있으면 깨지고 어느 서버가 그런지 알 수 없다. 사용자는 "기존에
  운영되는 많은 작업들에 피해를 주면 안 된다"고 했고 env 방식을 골랐다.
- **latin-1 방식 기각.** 어떤 바이트든 왕복되어 실패하지 않지만 화면에 파일명이
  깨져 보인다.
- **downloader 단위 설정, host 단위 아님.** 문자셋이 섞인 장비 그룹은 계열별로
  downloader를 나누면 된다. 실제로 그런 장비가 확인되기 전에는 만들지 않는다.
- **utf-8 실패 후 cp949 재시도 방식은 쓰지 않음.** ftplib의 코덱이 `connect()`
  시점에 고정되어 연결을 다시 열어야 하고, vendored 라이브러리가 복잡해진다.
- **Codex should 2건 반영.** (1) `codecs.lookup`은 `base64_codec` 같은 문자열용이
  아닌 코덱도 통과시키므로 `"".encode(name)`으로 검증을 바꿨다. (2) 배포 가이드
  5.3의 기존 버전 확인(`HostSpec`에 `user` 필드)은 이번 변경 전 코드도 통과하므로,
  `_downloader_from({'encoding': 'cp949'})`로 확인하는 명령을 추가했다.
- **Codex hook 신뢰 프롬프트는 "신뢰하지 않고 계속".** hook 신뢰는 사용자가 정할
  일이라 자동으로 신뢰하지 않았다.
- **upstream push는 사용자 확인 후 진행.** SKEWNONO의 push 권한이 다른 저장소까지
  넘어가지 않는다고 보고 물었고, 사용자가 "push해줘"라고 했다.

## 5. 배운 것 / 주의점

- `ftplib.FTP`의 `encoding`은 `connect()`에서 control 연결 reader에 묶인다. 생성자에
  넘겨야 하고 연결 후에 바꾸면 늦다. `retrlines`의 data 연결도 같은 값을 쓴다.
- FakeFTP 기반 스위트는 ftplib 층의 버그를 원리상 볼 수 없다.
- proxy 호스트에는 `flask_proxy.py`와 `fleet_downloader.py`가 반드시 함께 올라가야
  한다. `flask_proxy.py`만 새것이면 옛 downloader가 `encoding`을 몰라 모든 요청이
  500이 된다.
- 옛 proxy는 `encoding` 키를 조용히 무시한다. 실패는 HTTP 200 안의
  `UnicodeDecodeError` 항목으로만 보인다.
- Codex pane이 닫혀도 작업은 백그라운드에서 계속 돌아 리뷰 파일이 작성됐다.
  `herdr agent wait`는 프롬프트 직후 `idle`을 바로 반환할 수 있으므로 `done`이나
  `blocked`를 기다려야 한다. 이 빌드에는 `herdr wait` 명령이 없다.
- loopback 테스트 서버는 MLSD, LIST, STOR를 구현하지 않는다. 이 세 명령의 cp949
  동작은 코드로만 확인했다.

## 6. 다음 단계

- 사무실: proxy 호스트 `ftp_handler` 통째 갱신과 재기동, 두 office adapter `cp`,
  `.env`에 `SKEWNONO_TOOL_FTP_ENCODING=cp949`. 절차와 회신 항목(A/B/C)은
  `docs/office-migration/to-office-ftp-cp949-261014.md`에 있다.
- 실제 Windows 장비에서 한글 listing과 다운로드 검증이 남아 있다.
- UTF-8로 한글 이름을 보내는 장비가 발견되면 계열별 downloader 분리가 필요하다 (추정).

## 7. 메모리 업데이트

- 신규 `feedback_herdr_vertical_splits_only.md`: herdr 분할은 항상
  `--direction right`. 사용자가 위아래로 쌓은 pane은 읽기 어렵다고 했다.
- 신규 `project_ftp_filename_encoding.md`: `encoding` 옵션의 구조, 기본값을 utf-8로
  둔 이유, 남은 사무실 작업, FakeFTP의 한계.
- 두 항목 모두 `MEMORY.md` 색인에 추가했다.
