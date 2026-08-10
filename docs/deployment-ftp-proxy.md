# FTP 프록시 호스트 배포 가이드

`skewnono-scheduler1-webapp` 에 `flask_modules` 의 `ftp_handler` 를 갱신하는
절차입니다. skewnono 본체 배포는 [`deployment.md`](deployment.md) 를 따르며, 이
문서는 **그 앱이 의존하는 프록시 절반**만 다룹니다.

## 1. 이 배포가 필요한 때

사무실 로컬 PC(Windows)는 계측 장비 FTP 로 직접 나가지 못하므로, `msr_image` 와
`recipe_search` 의 모든 FTP 호출이 이 프록시를 거칩니다. 프록시 절반은
`ftp_handler/proxy/flask_proxy.py` 의 블루프린트이고,
`skewnono-scheduler1-webapp` 에 마운트되어 있습니다.

따라서 **`ftp_handler` 가 바뀌면 skewnono 만 배포해서는 절반만 갱신됩니다.**
클라이언트 절반(`proxy_downloader.py`)은 skewnono 번들에 실려 가지만, 서버
절반은 이 절차로 따로 올려야 합니다.

## 2. 무엇이 어디로 가는가

| 구성 요소 | 사는 곳 | 갱신 수단 |
| --- | --- | --- |
| 클라이언트 절반 (`proxy_downloader.py`) | skewnono 번들 안의 vendored `ftp_handler/` | skewnono 배포 |
| 서버 절반 (`flask_proxy.py`) | 프록시 호스트의 `flask_modules` 체크아웃 | **이 문서** |
| 장비 FTP 계정 | 프록시 호스트의 프로세스 환경 | 이 문서 4단계 |

두 사본은 항상 동일해야 합니다. 어긋난 상태가 어떻게 보이는지는 6절에 있습니다.

## 3. 사무실 PC 에서 최신 코드 받기

`flask_modules` 는 **공개 저장소**이므로 GitHub 로그인 없이 받을 수 있습니다.
사무실에서 GitHub 계정 로그인이 불가능한 제약과 무관하게 동작합니다.

```bash
git clone https://github.com/DarrenKoi/flask_modules.git    # 최초 1회
git -C flask_modules pull                                   # 이후
```

받은 뒤 커밋을 기록해 두십시오. 프록시 호스트에는 git 이 없으므로, **여기서 적어
둔 커밋 해시가 나중에 "무엇을 올렸는지"를 아는 유일한 근거**가 됩니다.

```bash
git -C flask_modules log --oneline -1
```

## 4. 프록시 호스트로 올리기

### 4.1 대상 경로 확인

복사 대상은 그 앱의 `wsgi.ini` 가 `pythonpath` 로 가리키는 디렉터리입니다.
템플릿의 기본값은 `/opt/flask_modules` 이지만 **기본값을 그대로 믿지 마십시오** —
실제 값을 먼저 확인합니다.

```bash
grep pythonpath /경로/wsgi.ini
```

### 4.2 복사

최소 범위는 `ftp_handler/` 하나입니다. 다만 그 앱이 `ops_store` 등 다른 모듈도
쓴다면 트리 전체를 맞추는 편이 안전합니다.

```bash
# <PYTHONPATH> 는 4.1 에서 확인한 경로입니다.
scp -r flask_modules/ftp_handler <호스트>:<PYTHONPATH>/
```

### 4.3 `__pycache__` 제거 — 수동 복사에서 제일 잘 미끄러지는 단계

파이썬은 `.pyc` 재사용 여부를 소스의 mtime 으로 판단합니다. 복사 수단이 원본
mtime 을 보존하면(`scp -p`, 공유 폴더 복사, 일부 압축 해제) **새 소스가 옛
`.pyc` 보다 오래된 것으로 보여 옛 바이트코드가 그대로 실행됩니다.** 파일은 분명히
바뀌었는데 동작만 옛것인, 진단하기 가장 나쁜 형태입니다.

```bash
find <PYTHONPATH>/ftp_handler -name __pycache__ -type d -exec rm -rf {} +
```

### 4.4 환경 변수

장비 FTP 계정은 프록시 호스트가 자기 환경에서 읽습니다. `os.environ[...]` 이라
**없으면 `KeyError` → 500** 입니다. uWSGI 라면 그 앱의 `wsgi.ini` 에 넣습니다.

```ini
env = FTP_PROXY_FTP_USER=hitachi
env = FTP_PROXY_FTP_PASSWORD=hid
```

이 두 값은 **플릿 기본값**입니다. 계열이 섞여 계정이 갈리는 장비는 클라이언트가
spec 에 실어 보내며, 그 경우에도 여기 설정은 나머지 장비를 위해 남아 있어야
합니다.

### 4.5 재기동

```bash
uwsgi --ini wsgi.ini      # 또는 운영 중인 프로세스 재시작
```

## 5. 검증 — 반드시 두 가지를 모두 확인합니다

### 5.1 살아 있는가

```bash
curl http://skewnono-scheduler1-webapp.aipp01.skhynix.com/healthz_sknn_v3
```

`{"status": "ok"}` 가 나와야 합니다. 다만 이것은 **크리덴셜이 없어도 통과합니다** —
`healthz` 는 다운로더를 만들지 않기 때문입니다. 살아 있다는 것 외에는 아무것도
증명하지 못합니다.

### 5.2 어떤 버전이 올라갔는가

`healthz` 는 버전을 알려주지 않고 호스트에는 git 이 없으므로, 코드에 직접
물어봅니다. 3절에서 적어 둔 커밋이 실제로 올라갔는지 확인하는 단계입니다.

```bash
cd <PYTHONPATH> && python -c "
from ftp_handler.direct_downloader import HostSpec
f = HostSpec.__dataclass_fields__
print('per-host credentials:', 'user' in f and 'password' in f)
"
```

2026-08-10 이후 버전이라면 `True` 입니다. `False` 라면 복사가 닿지 않았거나
4.3 의 `__pycache__` 가 남아 있는 것입니다.

## 6. 조용한 실패 모드

이 배포에서 나오는 고장은 대부분 **에러를 내지 않습니다.** 미리 알고 보지 않으면
찾기 어려우므로 정리합니다.

| 증상 | 원인 | 확인 |
| --- | --- | --- |
| 모든 FTP 요청이 500 | 4.4 환경 변수 누락 | 프록시 로그의 `KeyError` |
| 장비별 계정이 무시됨 | 서버 절반이 옛 버전 | 5.2 probe 가 `False` |
| 파일이 바뀌었는데 동작은 옛것 | 옛 `.pyc` 재사용 | 4.3 재실행 |
| 큰 요청만 실패 | `host_timeout` > `harakiri` | 7절 |

두 번째가 가장 위험합니다. 서버 절반이 옛 버전이면 클라이언트가 보낸 장비별
계정을 **조용히 버리고** 환경 변수 계정으로 로그인합니다. 예외도 로그도 없이
"인증 실패" 또는 "파일 없음" 으로만 보입니다.

이 방향은 의도된 설계입니다 — `_spec_from_wire` 가 `.get()` 이라 구버전
클라이언트가 신버전 프록시에 붙어도 500 이 나지 않습니다. 덕분에 양쪽 배포 순서를
자유롭게 잡을 수 있지만, **대가로 버전 불일치가 조용해집니다.** 그래서 5.2 가
선택이 아니라 필수입니다.

## 7. `host_timeout` 과 `harakiri` 는 함께 움직입니다

프록시 요청 하나가 여러 호스트의 배치를 나릅니다. 다운로더의 호스트별 백스톱
(`host_timeout`, 프록시 경로 기본 45초)은 uWSGI 가 요청을 죽이기 **전에** 발동해야
합니다. 그래야 워커가 강제 종료되는 대신 앱이 부분 리포트를 돌려줍니다.

`wsgi.ini` 의 `harakiri = 75` 가 그 여유이며, `host_timeout` 을 올리면 이 값도 같이
올려야 합니다. `harakiri` 를 넘긴 예산은 시간을 버는 대신 **배치 전체를 잃습니다.**
근거는 `ftp_handler/docs/adr/0001-proxy-batch-sizing.md` 에 있습니다.

## 8. 롤백

git 이 없는 호스트이므로 되돌릴 대상을 미리 남겨 두는 편이 빠릅니다.

```bash
mv <PYTHONPATH>/ftp_handler <PYTHONPATH>/ftp_handler.bak-YYYYMMDD   # 4.2 직전
```

되돌릴 때는 `.bak` 을 제자리에 놓고 `__pycache__` 를 지운 뒤 재기동합니다.
클라이언트 절반은 되돌리지 않아도 됩니다 — 구버전 프록시에 신버전 클라이언트가
붙는 조합은 6절의 두 번째 행(장비별 계정 무시)으로 떨어질 뿐, 공용 계정 장비는
정상 동작합니다.
