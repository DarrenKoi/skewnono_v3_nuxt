# AMAT 계열 첫 조사 — Home → Office (2026-10-13)

- 작성일: 2026-10-13입니다.
- 수신자: 사무실에서 SKEWNONO를 실행·확인하는 Office agent입니다.
- 목적: VeritySEM과 Provision을 붙이기 시작합니다. 이 두 계열은 장비 명부와 FTP 접근만
  있고 Redis·OpenSearch 소스와 측정 이력은 아직 없어서, **FTP에서 소스를 만드는 일**이
  먼저입니다. 무엇을 적재할지 정하려면 명부의 실제 모델 코드와 FTP에 무엇이 있는지를
  알아야 합니다.
- 범위: Redis와 장비 FTP를 **읽기만** 합니다. 디렉터리 이름만 보고 파일은 내려받지
  않습니다.
- 답이 손으로 옮겨지므로 스크립트가 **짧은 줄만** 찍도록 했습니다. 그 줄들과 글자 세 개가
  회신의 전부입니다.

## 1. 먼저 받아 둘 것

`main`을 다시 받은 뒤 실행해 주십시오. 모델 코드 판정이 `VERITY*` / `PROVISION*`
접두사로 넓어졌습니다. 예전 판정은 `VERITYSEM` / `VERITY_SEM`만 잡았습니다.

## 2. 스크립트

저장소 루트에서 `python`을 열고 붙여 넣습니다.

```python
from collections import Counter
from backend._runtime.office_redis import load_env_file
from backend.ebeam._tool_specs import model_to_tool_type
from backend.msr_image.config import load_config
from backend.sem_list.data import get_pending_tools, get_sem_list
from scripts.probes.probe_recipe_ftp import _downloader, _transport

load_env_file("REDIS_HOST")
avail, pend = get_sem_list(), get_pending_tools()
amat = lambda r: r["vendor_nm"] == "AMAT" or model_to_tool_type(r["eqp_model_cd"]) in ("veritysem", "provision")  # noqa: E731
for model in sorted({r["eqp_model_cd"] for r in avail + pend if amat(r)}):
    a = [r for r in avail if r["eqp_model_cd"] == model]
    p = sum(r["eqp_model_cd"] == model for r in pend)
    fabs = ",".join(f"{f}:{n}" for f, n in Counter(r["fab_name"] for r in a).most_common(3))
    print(f"{model} {model_to_tool_type(model)} avail={len(a)} pend={p} {fabs}")

cfg = load_config()
Downloader, HostSpec, ListDir, mode = _transport(False)
def ls(dl, ip, path):
    report = dl.list_dirs([HostSpec(ip, listings=[ListDir(path)])])
    if report.failures:
        return None, str(report.failures[0].error)[:60]
    return [x.rstrip("/").rsplit("/", 1)[-1] for l in report.listings for x in l.paths], ""

for family in ("veritysem", "provision"):
    tool = next((r for r in avail if model_to_tool_type(r["eqp_model_cd"]) == family and r["available"] == "On"), None)
    if tool is None:
        print(f"{family} no reachable tool")
        continue
    dl = _downloader(Downloader, cfg, tool["eqp_ip"])
    root, err = ls(dl, tool["eqp_ip"], "/")
    print(f"{family} {tool['eqp_id']} {tool['eqp_model_cd']} {mode} root={root[:10] if root is not None else 'FAIL ' + err}")
    for name in (root or [])[:5]:
        sub, err = ls(dl, tool["eqp_ip"], "/" + name)
        print(f"  /{name} n={len(sub) if sub is not None else 'FAIL'} {sub[:3] if sub else err}")
```

찍히는 모양은 이렇습니다(값은 예입니다).

```text
PROVISION_10 provision avail=12 pend=1 M10B:3,R3:2,M15C:2
VERITYSEM_5 veritysem avail=6 pend=0 R3:2,M14A:1,M15B:1
XYZ100 None avail=2 pend=0 M16A:2
veritysem MCD158 VERITYSEM_5 proxy (Windows) root=['Data', 'Recipe', 'Log']
  /Data n=41 ['20261012', '20261013', 'index.xml']
  /Recipe n=7 ['ADI', 'AEI', 'GATE']
  /Log n=3 ['alarm.log', 'event.log', 'sys.log']
provision VCD773 PROVISION_10 proxy (Windows) root=FAIL 530 Login incorrect
```

- 모델 줄 — AMAT 장비의 모델 코드마다 한 줄입니다. 둘째 칸은 판정된 계열이고, `None`이면
  vendor는 AMAT인데 어느 계열로도 판정되지 않은 코드입니다. 이 줄이 가장 중요합니다.
  `avail`은 접속 가능한 대수, `pend`는 방화벽 대기 대수, 끝은 대수가 많은 fab 셋입니다.
- 계열 줄 — 계열마다 접속 가능한 장비 한 대를 골라 FTP 최상위 이름을 열 개까지 찍습니다.
  실패하면 `FAIL`과 오류의 앞 60자가 나옵니다.
- 들여쓴 줄 — 최상위 항목 다섯 개까지 그 안의 개수와 앞 이름 셋입니다. 파일을 디렉터리처럼
  열어서 나는 `FAIL`은 무시하셔도 됩니다.

줄이 많으면 모델 줄과 계열 줄만 옮겨 주셔도 됩니다. 들여쓴 줄은 다음 회차에 필요한 곳만
다시 여쭙겠습니다.

## 3. 글자로 답하는 질문

**A. AMAT 장비의 FTP 계정은 Hitachi 장비와 같습니까.**
1. 같음(위 스크립트가 그대로 로그인됨)
2. 다르고, 계정을 이미 알고 있음
3. 다르고, 계정을 아직 모름
4. 모름

**B. 측정 결과가 장비 FTP의 어디에 쌓이는지 알고 계십니까.**
1. 앎 → 한 줄(예: `/Data/<날짜>/<lot>/result.csv`, 형식은 텍스트)
2. 모름

**C. Hitachi의 MSR처럼 "측정 1회 = 파일 또는 폴더 1개"인 단위가 있습니까.**
1. 있음
2. 없음(한 파일에 여러 측정이 계속 덧붙음)
3. 계열마다 다름 → 한 줄
4. 모름

## 4. 답안지

```text
모델 줄들
veritysem 줄
provision 줄
A
B
C
```

## 5. 회신 (2026-10-14)

원문(사용자가 옮겨 적은 그대로입니다):

```text
A hitachi 계정과 다름. 계열별로 갈림. veritysem = rtauser, provision = wf.. 둘다 회사내에서 데이터 취득 가능.
B 1 계열마다 다름.  veritysem D:\Output, provision /I_Drive + /D_drive/
C 1 잇음.
```

해석과 반영은 다음과 같습니다.

| 질문 | 읽은 뜻 | 반영 |
| --- | --- | --- |
| A | 계정이 Hitachi와 다르고 **계열마다** 하나씩입니다. VeritySEM은 `rtauser`, Provision은 `wf…` 계정입니다. 둘 다 사내에서 데이터를 받을 수 있습니다 | 2026-08-28의 "계정은 fab·장비별이고 계열과는 무관"이라는 전제가 틀렸습니다. FTP 계정 조회에 계열 키(`VERITYSEM`, `PROVISION`)를 더했습니다 |
| B | 위치를 압니다. VeritySEM은 `D:\Output`, Provision은 `/I_Drive`와 `/D_drive/` 두 곳입니다 | 계열별 스키마 문서에 기록했습니다. VeritySEM 경로가 FTP에서 어떻게 보이는지는 미확인입니다 |
| C | 측정 1회 = 파일 또는 폴더 1개인 단위가 있습니다 | 측정 이력 적재를 Hitachi MSR과 같은 단위로 설계할 수 있습니다 |

**받지 못한 것:** 스크립트의 출력 줄(모델 줄, 계열 줄)이 회신에 없습니다. 실행하지 않았다면
계열 계정을 설정한 뒤 다시 돌려야 합니다. 스크립트는 FTP 계정을 같은 조회로 고르므로, 계열
키가 생기기 전에는 AMAT 장비에도 Hitachi 계정으로 로그인해 실패했을 것입니다.
