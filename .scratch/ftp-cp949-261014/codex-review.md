SHIP

기존 운영을 깨뜨리는 변경은 발견하지 못했습니다. `encoding`을 생략하면 기존 `utf-8` 동작을 유지하며, 새 클라이언트와 구 프록시를 섞어도 추가 키 때문에 요청이 실패하지 않습니다. cp949 문제의 해결은 프록시까지 갱신한 뒤에 적용됩니다. 아래 두 항목은 비차단 개선사항입니다.

## 검토 범위와 가정

- 이 worktree의 `git diff main`, upstream `flask_modules`의 미커밋 변경과 새 `tests/test_ftp_encoding.py`를 검토했습니다.
- 별도 배포는 클라이언트와 프록시가 각각 완전한 `ftp_handler/`를 사용하는 조합으로 가정했습니다. 서버 파일 일부만 교체한 상태는 호환성 보장 대상에 포함하지 않았습니다.
- downloader 하나에 연결된 장비들은 같은 파일명 인코딩을 사용한다고 가정했습니다. 서로 다른 문자셋의 장비를 한 downloader로 처리하는 기능은 이번 변경에 없습니다.

## 발견사항

### 1. [should] 등록된 비텍스트 코덱도 설정 검증을 통과합니다

근거: `backend/msr_image/config.py:62`.

`SKEWNONO_TOOL_FTP_ENCODING=base64_codec`이면 `codecs.lookup()`가 성공하고 설정에 그대로 저장됩니다. 그러나 FTP가 사용하는 문자열 인코딩과 텍스트 reader에서는 `LookupError: 'base64_codec' is not a text encoding`이 발생합니다. `hex_codec`, `rot_13`도 같은 결과를 재현했습니다. 현재 검증은 알 수 없는 이름은 걸러도 파일명 문자셋으로 사용할 수 없는 등록된 코덱은 걸러내지 못합니다.

이 설정을 넣으면 msr_image와 recipe_search의 FTP 작업들이 장비별 실패로 기록됩니다. 정상 기본값과 `cp949`에는 영향이 없으므로 배포 차단 사유는 아닙니다.

최소 수정: 조회만 하는 대신 `"".encode(name)`처럼 문자열용 코덱인지를 검증하고, 발생하는 `LookupError`에 기존 경고와 `utf-8` fallback을 적용합니다. `base64_codec` 입력 한 건을 기존 설정 테스트에 추가하면 됩니다.

### 2. [should] 배포 가이드의 기존 버전 확인으로는 cp949 적용 여부를 알 수 없습니다

근거: `docs/deployment-ftp-proxy.md:104`, `docs/deployment-ftp-proxy.md:161`.

추가된 안내는 프록시 갱신이 필요하다고 정확히 설명하지만, 5.3의 확인 명령은 여전히 `HostSpec`에 `user` 필드가 있는지만 검사합니다. 이번 변경 전 `main`의 프록시도 이 검사를 통과합니다. 따라서 기존 점검을 모두 통과한 상태에서도 새 클라이언트가 보낸 `encoding="cp949"`는 무시될 수 있습니다. 구 프록시와 실제 cp949 loopback 서버를 연결해 HTTP 200 안에 `UnicodeDecodeError` listing 실패가 남는 것을 확인했습니다.

최소 수정: 5.3에 호스트 프로세스와 같은 인터프리터로 `flask_proxy._downloader_from({"encoding": "cp949"})`를 만들고 그 객체의 `encoding`이 `cp949`인지 검사하는 명령을 추가합니다. 빈 specs를 보내는 원격 점검만으로는 구 프록시가 이 키를 읽는지 구별할 수 없습니다.

## 검증 결과와 한계

- Upstream: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`로 **479 tests, OK**를 확인했습니다. 새 실제 cp949 loopback FTP 테스트 5개가 포함됩니다.
- SKEWNONO: main tree의 venv로 지정된 pytest 범위를 실행해 **669 passed**를 확인했습니다. 파일 생성 방지를 위해 `PYTHONDONTWRITEBYTECODE=1`과 `-p no:cacheprovider`를 추가했습니다.
- 변경된 SKEWNONO Python 파일의 `ruff check --no-cache`는 통과했습니다.
- 추가 재현은 파일을 만들지 않는 Python 코드로 수행했습니다. `main`의 구 클라이언트와 구 프록시 소스를 메모리에서 로드하여 신·구 조합을 실제 loopback FTP와 연결했습니다.
- `npm run lint:md`는 `markdownlint-cli2: command not found`로 실행하지 못했습니다. 의존성을 설치하지 않았습니다. 작성한 보고서가 있는 `.scratch/`는 원래 이 명령의 검사 대상에서 제외됩니다.
- 실제 Windows 장비, 사내 프록시 호스트, 운영 중인 `office.py` 사본은 확인하지 않았습니다. Upstream 테스트와 추가 loopback 재현은 Python 3.14.2, SKEWNONO pytest는 Python 3.11.14에서 실행했습니다. 로컬 3.11 테스트 통과는 실제 사무실 실행 증거가 아닙니다.
- 새 loopback 서버는 MLSD, LIST, STOR를 구현하지 않습니다. 이 세 명령의 cp949 동작은 호출 코드와 로컬 `ftplib` 구현까지 확인했으며, 실제 전송 테스트를 통과했다고 판단하지 않았습니다. 외부 프로젝트의 모든 subclass나 FTP monkeypatch는 확인하지 않았습니다.

## 확인했고 문제없었던 항목

- `diff -rq --exclude=__pycache__ ftp_handler /Users/daeyoung/Codes/flask_modules/ftp_handler`는 차이가 없었습니다.
- FtpClient, direct fleet, proxy fleet 생성자는 모두 기존부터 keyword-only입니다. 새 인수의 위치가 기존 positional 호출의 의미를 바꾸는 문제는 없습니다. direct/proxy의 download/list/size/upload wrapper와 `collect_fleet`는 `**kwargs` 또는 `**tuning`으로 새 값을 전달합니다. 검토한 코드 안에서는 이 클래스들을 상속하는 실제 호출자를 찾지 못했습니다.
- 기본 인코딩으로 구 클라이언트→구 프록시, 구→신, 신→구, 신→신 네 조합 모두 ASCII 파일의 다운로드·목록·크기 조회가 성공했고 결과 내용도 같았습니다. 구 클라이언트→신 프록시는 인코딩 키가 없어도 `utf-8`을 사용합니다.
- cp949 loopback에서 direct의 NLST·RETR·SIZE, FtpClient의 NLST·RETR, 신 클라이언트→신 프록시의 다운로드는 한글 경로와 원본 바이트를 보존했습니다. 신→구 프록시는 cp949를 무시하고 기존 실패를 반환하며, 추가 키 자체로 인한 4xx/5xx는 없었습니다.
- 프록시에 `encoding`으로 `null`, 숫자, 객체, 알 수 없는 이름, 비텍스트 코덱을 보냈을 때 모두 HTTP 200의 호스트별 `failures`로 격리됐습니다. `_run_fleet`가 worker 예외를 수집하므로 요청 전체의 500으로 전파되지 않습니다.
- `FTP(..., encoding=...)`는 `connect()` 전에 실행됩니다. 로컬 ftplib의 control reader와 `retrlines` data reader 모두 이 값을 사용합니다. MLSD는 `retrlines`를 사용하고, FtpClient의 LIST도 같은 메서드를 호출합니다. RETR·SIZE·STOR 명령 경로는 `putline`에서 같은 코덱으로 인코딩되며 파일 내용은 binary 전송을 유지합니다. 경로를 다른 코덱으로 고정 변환하는 코드도 발견하지 못했습니다.
- msr_image의 공통 downloader 생성 경로와 recipe_search의 IDP·raw-folder 공통 생성 경로에 설정 전달이 연결되어 있습니다. 계정, timeout, concurrency, 응답 구조는 이 diff에서 변경되지 않았습니다.
