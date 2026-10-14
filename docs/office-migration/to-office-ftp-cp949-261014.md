# FTP 한글(cp949) 파일명 대응 — Home → Office (2026-10-14)

- 작성일: 2026-10-14입니다.
- 수신자: 사무실에서 SKEWNONO와 FTP proxy 호스트를 배포·확인하는 Office agent입니다.
- 목적: 한글 파일명이 있는 장비 디렉터리의 listing이 전부 실패하는 문제를 고쳤습니다.
  코드는 `main`에 올라가 있지만, **사무실에서 두 가지 작업을 해야 실제로 해결됩니다.**
- 커밋: skewnono `c2f60835`, flask_modules `fd25c6d`입니다.
- 실제 장비와 사내 proxy 호스트에서는 아직 검증하지 못했습니다. 집에서는 cp949로
  응답하는 테스트 FTP 서버로만 확인했습니다.

## 1. 증상과 원인

- 한글 파일명이 하나라도 있는 디렉터리는 listing 전체가 실패했습니다. 에러는
  `list <dir> failed: UnicodeDecodeError: 'utf-8' codec can't decode ...` 형태입니다.
- Windows 장비 FTP는 파일명을 cp949로 보내는데, 우리 코드는 utf-8로만 읽었습니다.
- proxy 경로뿐 아니라 direct 경로(클라우드)도 같은 문제였습니다. 두 경로가 같은
  연결 코드를 씁니다.
- 파일명을 미리 알고 있어도 한글 경로는 다운로드가 `550`(파일 없음)으로 실패했습니다.
  요청 경로도 utf-8로 보내졌기 때문입니다.

## 2. 변경 내역

- `ftp_handler`에 파일명 문자셋을 지정하는 `encoding` 옵션을 추가했습니다. 기본값은
  `utf-8`이라 기존과 같습니다. 클라이언트가 요청마다 `encoding`을 실어 보내고, proxy가
  그 값으로 장비에 접속합니다.
- skewnono에 env `SKEWNONO_TOOL_FTP_ENCODING`을 추가했습니다. msr_image와
  recipe_search가 같이 씁니다. 설정하지 않으면 `utf-8`이므로 **배포만으로는 동작이
  바뀌지 않습니다.**

proxy 호스트에서 쓰이는 파일은 아래와 같습니다.

| 파일 | 변경 | proxy 호스트에서 필요 여부 |
| --- | --- | --- |
| `proxy/flask_proxy.py` | 요청의 `encoding`을 읽어 전달합니다 | 필요합니다 |
| `direct_downloader/fleet_downloader.py` | `encoding`으로 장비에 접속합니다 | 필요합니다 |
| `proxy/proxy_downloader.py` | 클라이언트가 `encoding`을 보냅니다 | 클라이언트 쪽 코드입니다 |
| `core/client.py` | `FtpClient`에 `encoding`을 추가했습니다 | proxy 경로에서는 쓰이지 않습니다 |

## 3. 사무실 작업

두 작업을 모두 해야 해결됩니다. 순서는 상관없습니다.

### 3.1 FTP proxy 호스트 (fileloader)

1. `ftp_handler` 폴더를 **통째로** 새 버전으로 덮어씁니다. 파일을 골라서 올리면 안
   됩니다. `flask_proxy.py`만 새것이면 옛 downloader가 `encoding` 인자를 몰라서 모든
   요청이 `500`이 됩니다.
2. `__pycache__`를 정리하고 uWSGI를 재기동합니다. 절차는
   [`deployment-ftp-proxy.md`](../deployment-ftp-proxy.md) 4.3절과 4.5절에 있습니다.
3. 앱과 같은 인터프리터로 아래 명령을 실행해 반영 여부를 확인합니다.

```bash
python -c "from ftp_handler.proxy.flask_proxy import _downloader_from; print('filename encoding:', getattr(_downloader_from({'encoding': 'cp949'}), 'encoding', 'MISSING'))"
```

| 출력 | 의미 |
| --- | --- |
| `filename encoding: cp949` | 반영되었습니다 |
| `filename encoding: MISSING` | 옛 코드입니다. 복사 경로와 `__pycache__`를 다시 확인합니다 |

### 3.2 skewnono (사무실 PC와 클라우드 모두)

1. `git pull`을 받습니다.
2. office adapter를 갱신합니다. msr_image와 recipe_search의 `office_example.py`를
   `office.py`로 복사합니다. 이 단계를 빼면 env를 넣어도 옛 `office.py`가 `encoding`을
   넘기지 않아 아무 변화가 없습니다.
3. `.env`에 아래 한 줄을 추가합니다.

```ini
SKEWNONO_TOOL_FTP_ENCODING=cp949
```

마지막으로 앱을 재기동합니다.

## 4. 확인 방법

- 한글 파일명이 있는 장비 디렉터리의 이미지 목록이 정상적으로 나오는지 확인합니다.
- 한글 파일명 이미지 1건이 실제로 열리는지 확인합니다.
- 기존에 잘 되던 영문 파일명 장비도 1건 확인합니다. 영향이 없어야 합니다.

## 5. 알아 둘 점

- proxy만 옛 버전이면 에러 없이 기존과 똑같이 동작하고, 한글 문제만 그대로 남습니다.
  실패는 HTTP 200 응답 안의 `UnicodeDecodeError` 항목으로만 보입니다.
- env 값을 잘못 넣으면 경고 로그를 남기고 `utf-8`로 동작합니다.
- `cp949`를 켜면 **모든 장비에 일괄 적용됩니다.** 한글 파일명을 UTF-8로 보내는 장비가
  섞여 있다면 그 장비의 한글 파일이 반대로 깨집니다. 영문 파일명은 어느 쪽이든 영향이
  없습니다. 그런 장비가 발견되면 알려 주십시오. 계열별로 나누는 작업이 추가로
  필요합니다.

## 6. 회신

아래 세 가지를 알려 주십시오.

- A. 3.1의 확인 명령 출력 한 줄입니다.
- B. 한글 파일명 디렉터리의 listing 결과입니다. 성공이면 `OK`, 실패면 에러 한 줄입니다.
- C. 영문 파일명 장비 1건의 결과입니다. `OK` 또는 에러 한 줄입니다.
