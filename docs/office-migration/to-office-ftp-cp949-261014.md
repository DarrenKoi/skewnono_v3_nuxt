# FTP 비ASCII 파일명 대응 — Home → Office (2026-10-14)

- 작성일: 2026-10-14입니다. 같은 날 office 확인 결과를 받아 **권장값을 정정했습니다.**
- 수신자: 사무실에서 SKEWNONO와 FTP proxy 호스트를 배포·확인하는 Office agent입니다.
- 목적: 비ASCII 파일명이 있는 장비 디렉터리의 listing이 전부 실패하는 문제를
  고쳤습니다. 코드는 `main`에 올라가 있지만, **사무실에서 두 가지 작업을 해야 실제로
  해결됩니다.**
- 커밋: skewnono `c2f60835`, flask_modules `fd25c6d`가 `encoding` 옵션을 넣었고, 이
  문서와 같은 커밋이 권장값을 `latin-1`로 바꿨습니다.

## 0. 정정 — cp949가 아니라 latin-1입니다

처음에는 원인을 한글(cp949) 파일명으로 가정하고 `SKEWNONO_TOOL_FTP_ENCODING=cp949`를
권장했습니다. office에서 수정본으로 확인한 결과는 달랐습니다. 비ASCII 이름 10개가 모두
cp949로도 utf-8로도 해석되지 않는 난수형 바이트였습니다. 인코딩 문제가 아니라 **손상된
파일명**입니다.

그래서 권장값은 `latin-1`입니다. `latin-1`은 모든 바이트를 문자 하나에 1:1로
대응시키므로 어떤 이름이 와도 실패하지 않고, 나열된 이름을 다시 요청하면 원래 바이트
그대로 나갑니다. 집에서 손상된 바이트 이름으로 확인한 결과는 아래와 같습니다.

| encoding | 결과 |
| --- | --- |
| `utf-8` | listing 전체 실패 (`UnicodeDecodeError`) |
| `cp949` | listing 전체 실패 (`UnicodeDecodeError`) |
| `latin-1` | 손상된 파일과 정상 파일 모두 나열·다운로드 성공 |

코드 구조는 그대로입니다. 이미 `cp949`를 넣었다면 값만 바꾸면 됩니다.

## 1. 증상과 원인

- 해석되지 않는 파일명이 하나라도 있는 디렉터리는 listing 전체가 실패했습니다. 에러는
  `list <dir> failed: UnicodeDecodeError: 'utf-8' codec can't decode ...` 형태입니다.
- 우리 코드는 파일명을 utf-8로만 읽었고, 읽지 못하는 이름 하나가 목록 전체를
  버리게 했습니다.
- proxy 경로뿐 아니라 direct 경로(클라우드)도 같은 문제였습니다. 두 경로가 같은
  연결 코드를 씁니다.

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
python -c "from ftp_handler.proxy.flask_proxy import _downloader_from; print('filename encoding:', getattr(_downloader_from({'encoding': 'latin-1'}), 'encoding', 'MISSING'))"
```

| 출력 | 의미 |
| --- | --- |
| `filename encoding: latin-1` | 반영되었습니다 |
| `filename encoding: MISSING` | 옛 코드입니다. 복사 경로와 `__pycache__`를 다시 확인합니다 |

### 3.2 skewnono (사무실 PC와 클라우드 모두)

1. `git pull`을 받습니다.
2. office adapter를 갱신합니다. msr_image와 recipe_search의 `office_example.py`를
   `office.py`로 복사합니다. 이 단계를 빼면 env를 넣어도 옛 `office.py`가 `encoding`을
   넘기지 않아 아무 변화가 없습니다.
3. `.env`에 아래 한 줄을 추가합니다. 이미 `cp949`를 넣었다면 값을 바꿉니다.

```ini
SKEWNONO_TOOL_FTP_ENCODING=latin-1
```

마지막으로 앱을 재기동합니다.

## 4. 확인 방법

- 손상된 파일명이 있던 장비 디렉터리의 목록이 실패 없이 나오는지 확인합니다.
- 같은 디렉터리의 정상(영문) 파일 1건이 실제로 열리는지 확인합니다.
- 기존에 잘 되던 다른 장비도 1건 확인합니다. 영향이 없어야 합니다.

## 5. 알아 둘 점

- proxy만 옛 버전이면 에러 없이 기존과 똑같이 동작하고, 문제만 그대로 남습니다.
  실패는 HTTP 200 응답 안의 `UnicodeDecodeError` 항목으로만 보입니다.
- env 값을 잘못 넣으면 경고 로그를 남기고 `utf-8`로 동작합니다.
- `latin-1`은 실패를 막을 뿐 **손상된 이름을 고쳐 주지 않습니다.** 그 파일들은 깨진
  글자의 이름으로 보입니다. msr_image는 이미지 확장자로 끝나는 이름만 목록에 싣습니다.
- 손상된 이름 안에 줄바꿈 바이트가 들어 있으면 이름 하나가 둘로 쪼개져 보일 수
  있습니다. 이 경우에도 listing은 실패하지 않습니다.
- 영문 파일명은 어떤 값에서도 결과가 같습니다. 진짜 한글 파일명을 쓰는 장비가 따로
  확인되면 그 이름은 `latin-1`에서 깨진 글자로 보이므로 알려 주십시오.

## 6. 회신

아래 네 가지를 알려 주십시오.

- A. 3.1의 확인 명령 출력 한 줄입니다.
- B. `latin-1` 적용 후 손상된 이름이 있던 디렉터리의 listing 결과입니다. 성공이면
  `OK`, 실패면 에러 한 줄입니다.
- C. 다른 장비 1건의 결과입니다. `OK` 또는 에러 한 줄입니다.
- D. 손상된 이름 10개가 있던 장비와 디렉터리입니다. 우리가 쓰는 파일인지도 알려
  주십시오.
