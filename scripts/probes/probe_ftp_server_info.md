# AMAT 장비 FTP 서버 정찰 절차 (스토리지 용량 수집 가능 여부)

VeritySEM·Provision 은 Windows 장비라서 CD-SEM·HV-SEM 처럼 `df -h` cron 결과를
FTP 로 읽을 수 없습니다. 장비에 무엇을 설치하기 전에, **장비의 FTP 서버가 디스크
여유 공간을 직접 알려 주는지** 먼저 확인합니다. 확인에 쓰는 스크립트는 같은 폴더의
`probe_ftp_server_info.py` 입니다.

이 스크립트는 정해진 읽기 전용 명령(`SYST`, `FEAT`, `HELP`, `HELP SITE`, `STAT`,
`AVBL`, `SITE DF`, `SITE DISKFREE`)만 보냅니다. 장비의 파일을 만들거나 지우는 명령은
보내지 않습니다.

절차는 두 단계입니다. **1 단계 결과가 나오기 전에는 2 단계를 하지 않습니다.**

| 단계 | 어디서 | 무엇을 | 언제 |
| --- | --- | --- | --- |
| 1 | 클라우드 호스트 | 직접 FTP 로 명령이 통하는지 확인 | 지금 |
| 2 | 프록시 호스트 | 같은 기능을 프록시 라우트로 추가 | 1 단계에서 명령이 통했을 때만 |

## 1 단계: 클라우드에서 직접 FTP 로 확인합니다

클라우드 호스트는 장비 FTP 에 직접 닿습니다. 클라우드 번들(`scripts/deploy/pack.py`)
에는 `scripts/` 가 들어가지 않으므로 파일 하나를 직접 복사합니다. 직접 모드는
파이썬 표준 라이브러리만 쓰므로 다른 파일은 필요 없습니다.

### 1.1 파일 복사

```bash
scp scripts/probes/probe_ftp_server_info.py <클라우드 호스트>:/tmp/
```

### 1.2 대상 장비와 계정 준비

- 장비 IP: VeritySEM 1 대, Provision 1 대 이상. 두 계열의 FTP 서버가 다를 수 있으므로
  반드시 **양쪽 모두** 확인합니다. Provision 은 data IP 가 아니라 **tool IP** 로
  시작하되, 시간이 되면 data IP 도 함께 확인합니다.
- 계정: 클라우드 `backend/.env` 의 `SKEWNONO_TOOL_FTP_ACCOUNTS` 에 계열별 계정이
  있습니다(`VERITYSEM=<user>:<pw>,PROVISION=<user>:<pw>`).

비밀번호가 셸 기록에 남지 않게 환경 변수로 넘기는 것을 권장합니다. `--user` /
`--password` 를 생략하면 `SKEWNONO_TOOL_FTP_USER` / `SKEWNONO_TOOL_FTP_PASSWORD` 를
읽습니다.

### 1.3 실행

VeritySEM:

```bash
export SKEWNONO_TOOL_FTP_USER=<VeritySEM 계정>
read -s SKEWNONO_TOOL_FTP_PASSWORD && export SKEWNONO_TOOL_FTP_PASSWORD
python /tmp/probe_ftp_server_info.py --direct --host <VeritySEM IP>
python /tmp/probe_ftp_server_info.py --direct --host <VeritySEM IP> --dir /C_Drive
```

Provision 은 계정만 바꿔 같은 명령을 실행합니다.

```bash
export SKEWNONO_TOOL_FTP_USER=<Provision 계정>
read -s SKEWNONO_TOOL_FTP_PASSWORD && export SKEWNONO_TOOL_FTP_PASSWORD
python /tmp/probe_ftp_server_info.py --direct --host <Provision tool IP>
python /tmp/probe_ftp_server_info.py --direct --host <Provision tool IP> --dir /C_Drive
```

옵션은 다음과 같습니다.

| 옵션 | 기본값 | 뜻 |
| --- | --- | --- |
| `--host` | 필수 | 장비 IP. 여러 번 주면 차례로 확인하고, 한 대가 실패해도 계속합니다 |
| `--dir` | `/D_Drive` | `AVBL` / `SITE DF` 에 붙이는 경로. 드라이브마다 따로 확인합니다 |
| `--port` | `21` | FTP 포트 |
| `--timeout` | `8` | 명령 하나당 대기 시간(초) |
| `--encoding` | `latin-1` | 서버 문자셋. 어떤 바이트도 읽으므로 바꿀 필요가 없습니다 |

### 1.4 결과 읽기

장비마다 마지막 줄에 판정이 나옵니다.

| 마지막 줄 | 뜻 | 다음 행동 |
| --- | --- | --- |
| `=> 여유 공간 명령 응답 있음: AVBL /D_Drive` | FTP 만으로 용량을 잴 수 있습니다 | 2 단계로 갑니다 |
| `=> 여유 공간 명령 응답 없음 (...)` | FTP 서버가 용량을 알려 주지 않습니다 | 2 단계를 하지 않습니다. 장비 쪽 예약 작업(`wmic` 결과를 파일로 남기기) 방안으로 넘어갑니다 |
| `FAIL error_perm: 530 ...` | 로그인 실패입니다 | 계정·비밀번호를 확인합니다 |
| `FAIL TimeoutError: ...` / `FAIL ConnectionRefusedError: ...` | 장비에 닿지 않습니다 | IP 와 장비 상태를 확인합니다 |

`welcome:` 줄과 `HELP` 응답 첫 줄에는 보통 FTP 서버 종류(IIS, FileZilla 등)가
나옵니다. 이것도 함께 기록합니다.

### 1.5 결과 전달

**출력 전체를 그대로** 붙여 넣어 전달합니다. 응답 원문(예: `213 123456789`)의 형식을
보고 파서를 작성하고, `docs/datatables/veritysem/verity_hosts.txt` 와
`docs/datatables/provision/provision_hosts.txt` 에 `office 확인` 날짜와 함께
기록합니다. 판정 줄만으로는 숫자의 단위(바이트·KB)를 알 수 없습니다.

## 2 단계: 프록시에 같은 기능을 추가합니다

**1 단계에서 여유 공간 명령이 통했을 때만** 진행합니다. 사무실 PC 처럼 장비 FTP 에
직접 닿지 않는 곳에서도 같은 확인을 하기 위한 단계입니다.

`ftp_handler` 는 다른 저장소와 공유하며 upstream 에서 `rsync --delete` 로 동기화하므로
건드리지 않습니다. 같은 파일이 프록시 앱에 붙는 별도 블루프린트 역할도 합니다.

### 2.1 프록시 호스트에 파일 복사

`docs/deployment-ftp-proxy.md` 4.1 에서 확인하는 앱의 `PYTHONPATH` 디렉터리,
즉 `ftp_handler/` 가 있는 곳에 **같은 수준으로** 복사합니다.

```bash
scp scripts/probes/probe_ftp_server_info.py <프록시 호스트>:<PYTHONPATH>/
```

### 2.2 프록시 앱에 블루프린트 등록

기존 `ftp_proxy_sknn_v3` 를 등록하는 줄 옆에 두 줄을 추가합니다.

```python
from probe_ftp_server_info import ftp_server_info_sknn_v3
app.register_blueprint(ftp_server_info_sknn_v3)
```

추가되는 라우트는 `POST /server_info_sknn_v3` 하나입니다. 인증(`FTP_PROXY_TOKEN`)과
기본 계정(`FTP_PROXY_FTP_USER` / `FTP_PROXY_FTP_PASSWORD`)은 기존 프록시와 같은
환경 변수를 쓰므로 새로 설정할 값이 없습니다.

### 2.3 재기동

`docs/deployment-ftp-proxy.md` 4.3(`__pycache__` 제거)과 4.5(재기동)를 그대로
따릅니다.

### 2.4 사무실 PC 에서 프록시로 확인

저장소 루트에서 `--direct` 없이 실행합니다. 프록시 주소는
`ftp_handler/proxy/proxy_downloader.py` 의 `PROXY_URL` 을 그대로 씁니다.

```bash
.venv\Scripts\python -m scripts.probes.probe_ftp_server_info --host <VeritySEM IP> --user <계정> --password <pw>
```

1 단계와 같은 출력이 나오면 완료입니다. `/server_info_sknn_v3 가 프록시에 없습니다
(404)` 가 나오면 2.1 의 복사 위치나 2.2 의 등록을 확인합니다.

### 2.5 되돌리기

2.2 에서 추가한 두 줄을 지우고 재기동합니다. 복사한 파일은 남겨 두어도 등록하지
않으면 아무 일도 하지 않습니다.
