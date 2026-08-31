# `scripts/` 작성 규칙

여기 있는 스크립트는 대부분 **사무실에서 손으로 한 번 실행**됩니다. 자동으로
도는 것이 없고, 집에서는 실행되지 않으며, 실패하면 그 자리에서 사람이
붙잡힙니다. 아래 규칙은 그 상황에서 실제로 시간을 잡아먹은 사고들에서 나왔습니다.

`tests/test_script_conventions.py` 가 이 규칙들을 강제합니다.

## 폴더 구성

목적별 하위 폴더로 나뉩니다. 새 스크립트는 아래 질문 중 무엇에 답하는지에
따라 자리를 정합니다.

| 폴더 | 답하는 질문 | 예 |
| --- | --- | --- |
| `adapters/` | office.py 어댑터를 만들고·갱신하고·치웁니다 | `sync_office_adapters`, `setup_office_adapters`, `prune_orphan_features` |
| `probes/` | 이 사무실 소스에 실제로 무엇이 들어 있는가? (스키마·값 정찰) | `probe_planstep_r3`, `inspect_redis_key`, `measure_msr_image_ftp` |
| `diagnose/` | 이 화면이 사무실에서 왜 비어 있는가? (증상에서 원인 찾기) | `diagnose_fdc_office`, `diagnose_storage_ppid_office` |
| `verify/` | 스왑·배포가 제대로 됐는가? (사후 검증) | `check_contract`, `probe_office_endpoints`, `check_ftp_proxy` |
| `deploy/` | Phase 3 번들 패킹과 프리플라이트 | `pack`, `preflight_cloud` |
| `clients/` | 외부 소비자에게 배포하는 API 클라이언트 예제 | `msr_image_download` |

실행 형식은 폴더를 그대로 씁니다: `python -m scripts.verify.check_contract`.

## 1. 두 가지 실행 형식을 모두 지원합니다

```bash
python -m scripts.<folder>.<name>          # 모듈 형식
python scripts/<folder>/<name>.py          # 경로 형식
```

저장소 패키지를 import 한다면 **첫 import 앞에** 부트스트랩을 둡니다.

```python
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]  # 하위 폴더 기준. 더 깊으면 숫자를 올립니다.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import scripts  # noqa: E402,F401  (applies the stdout UTF-8 fix)

from back_dev_home... import ...  # noqa: E402
```

`import scripts` 는 불필요해 보이지만 필요합니다. `scripts/__init__.py` 가
stdout 을 UTF-8 로 돌리는데, `-m` 은 패키지를 먼저 import 하므로 그 혜택을 자동으로
받지만 **경로 실행은 받지 못합니다.** 이 한 줄이 두 형식을 같게 만듭니다.

`-m` 은 작업 디렉터리를 `sys.path` 에 넣지만 경로 실행은 `scripts/` 를 넣습니다.
부트스트랩이 없으면 경로 실행이 첫 import 에서 `ModuleNotFoundError` 로 죽습니다.
파일 관리자, IDE 의 "이 파일 실행" 버튼, 탭 완성이 모두 경로 형식을 만들어내므로
설명으로 막을 수 있는 문제가 아닙니다.

## 2. 출력은 ASCII 로 씁니다

박스 문자(`─`, `═`), 엠대시(`—`), 화살표(`►`) 를 쓰지 않습니다. 사무실 터미널의
기본 인코딩은 ANSI 코드 페이지(한국어 Windows 에서 cp949)이고, 그중 다수는
cp949 로 인코딩되지 않아 `UnicodeEncodeError` 로 죽습니다. `--help` 조차 그렇게
죽은 적이 있습니다.

한글 자체는 cp949 에 있으므로 안내 문구는 한국어로 써도 됩니다. 구분선은
`----` 로 충분합니다.

`scripts/__init__.py` 가 stdout 을 UTF-8 로 돌리지만 그것은 `-m` 실행에만 걸리는
안전망일 뿐, 규칙을 대신하지 않습니다.

## 3. 편의 기능이 실행을 막지 않게 합니다

`sys.stdout.reconfigure(...)` 같은 호출은 반드시 감쌉니다. 그런 객체가 없는
stdout 이 있고, detach 된 스트림에서는 예외가 납니다. 감싸지 않으면 **한 글자도
출력하기 전에** 죽어서 "명령이 아무것도 안 한다" 가 됩니다.

```python
reconfigure = getattr(sys.stdout, "reconfigure", None)
if reconfigure is not None:
    try:
        reconfigure(line_buffering=True)
    except (ValueError, OSError):
        pass
```

## 4. 첫 줄에 살아 있다는 증거를 냅니다

오래 걸리는 스크립트는 어떤 무거운 작업보다 먼저 한 줄을 출력합니다. 프로세스가
떴다는 증거이자, 창마다 다르게 동작할 때 원인을 가르는 정보입니다.

```python
print(f"python {sys.version.split()[0]}  stdout={sys.stdout.encoding}")
```

## 5. 설정은 스스로 갖춥니다

`.env` 에 의존하지 않고 실행되어야 합니다. 사무실 값은 파일 안에 baseline 으로
두고, 환경 변수가 그것을 덮고, 명령줄 플래그가 최종입니다. 비밀이 아닌 값만
해당합니다 — MinIO access/secret 키처럼 gitignore 된 것은 절대 넣지 않습니다.

`.env` 를 읽는다면 **조건 없이** 읽습니다. `load_dotenv` 는 이미 환경에 있는 값을
덮어쓰지 않으므로 항상 읽는 편이 안전합니다. 한 변수의 유무로 파일 전체를
건너뛰면, 같은 파일에 있는 나머지 설정이 통째로 기본값으로 떨어집니다.

## 6. 실패는 원인과 다음 행동을 함께 말합니다

편의 기능(자동 탐색 등)이 실패했을 때 raw traceback 을 내면 "스크립트가
고장났다" 로 읽힙니다. 무엇이 없어서 실패했는지와 우회 방법을 함께 냅니다.

```python
raise SystemExit(
    f"could not discover a target: {type(exc).__name__}: {exc}\n"
    "Pass a locator explicitly to skip OpenSearch entirely:\n"
    "    --eqp-ip 10.1.2.3 --class-name ADI --msr <MSR>"
)
```

## 7. 측정·수집은 항목 하나 때문에 중단하지 않습니다

실장비 상대 실행은 한 번에 수 분이 듭니다. 파일 하나가 실패하면 건수를 보고하고
계속 진행하며, 전부 실패한 경우에만 중단합니다.
