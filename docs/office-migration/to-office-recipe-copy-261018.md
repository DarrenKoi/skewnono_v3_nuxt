# 레시피 횡전개 앱을 위한 장비 FTP 확인 — Home → Office (2026-10-18)

- 작성일: 2026-10-18입니다.
- 수신자: 사무실에서 SKEWNONO를 실행·확인하는 Office agent입니다.
- 목적: 레시피를 다른 장비로 복사하는 새 앱(`recipe-copy`, SKEWNONO와 별개 web app)의
  설계에서 가정으로 둔 두 가지를 실제 장비에서 확인합니다. (가) Hitachi 장비의
  레시피 파일 레이아웃, 특히 `.idw`의 위치와 raw 폴더의 내용. (나) 장비 FTP 서버가
  `MKD`와 "기존 파일 위로 `RNTO`"를 허용하는지. 설계 전문은
  `.scratch/recipe-bulk-copy/handoff.md`(r3)에 있습니다.
- 범위: 1절은 **읽기만** 합니다. 2절은 **로그인 홈 아래 조사용 폴더 하나**를 만들고
  그 안에서만 쓰고 지웁니다. 레시피 폴더(`data/`)와 이미지 폴더(`images/`)에는
  쓰지 않습니다. 2절은 측정 중이 아닌 장비 한 대에서, 장비 담당자가 괜찮다고 한
  뒤에 돌립니다.
- 답이 손으로 옮겨지므로 스크립트가 **짧은 줄만** 찍도록 했습니다. 그 줄들과 글자
  몇 개가 회신의 전부입니다.

## 0. 공통 준비

클라우드 호스트(Linux, 장비 FTP에 직접 닿는 쪽)에서 저장소 루트의 `python`으로
돌립니다. 사무실 Windows PC는 proxy를 거치므로 2절의 쓰기 명령을 보낼 수 없습니다.

접속 정보는 SKEWNONO `.env`의 `SKEWNONO_TOOL_FTP_USER` / `_PASSWORD` /
`_ENCODING`을 그대로 씁니다. 아래 두 스크립트 모두 이 머리말로 시작합니다.

```python
import os
from backend._runtime.office_redis import load_env_file
load_env_file("SKEWNONO_LOG_ENV")
from ftp_handler.core.client import FtpClient

HOST = "<장비 eqp_ip>"          # sem_list 의 eqp_ip
CLASS = "<class_name>"          # 그 장비에서 최근 측정한 레시피의 class
IDW = "<idw stem>"              # 같은 레시피의 idw_name 에서 확장자·경로를 뗀 값
IDP = "<idp stem>"              # 같은 레시피의 idp_name 에서 확장자·경로를 뗀 값
ROOT = "/HITACHI/DEVICE/HD"

def client():
    return FtpClient(
        host=HOST,
        user=os.environ.get("SKEWNONO_TOOL_FTP_USER") or "hitachi",
        password=os.environ.get("SKEWNONO_TOOL_FTP_PASSWORD") or "hid",
        encoding=os.environ.get("SKEWNONO_TOOL_FTP_ENCODING") or "utf-8",
        timeout=15,
    )

def show(c, path, tag):
    try:
        rows = c.list_details(path, max_entries=200)
    except Exception as exc:
        print(f"{tag} LIST-FAIL {path}: {type(exc).__name__}: {str(exc)[:80]}")
        return
    print(f"{tag} {path} entries={len(rows)}")
    for r in rows[:60]:
        kind = "D" if r.is_dir else "F"
        print(f"  {kind} {r.name} size={r.size} mtime={r.modified}")
```

`CLASS`/`IDW`/`IDP`는 recipe-search 화면에서 그 장비로 최근 열린 레시피 하나를 고르면
됩니다. meas_hist의 `idw_name`/`idp_name`은 경로 문자열이므로 stem만 넣습니다
(`/Recipe/ADI/ADI_CD_BIAS_001.idp` → `ADI_CD_BIAS_001`).

## 1. 레이아웃 조사 (읽기만)

설계는 레시피 하나를 "`data/{idw}/{idp}.idp` + `data/{idw}/{idp}/` raw 폴더 전체 +
상위 폴더의 `{idw}.idw`(옵션)"로 잡았습니다. `.idw` 파일이 **정확히 어디** 있는지,
raw 폴더에 **무엇이** 들어 있는지를 확인합니다.

```python
with client() as c:
    print("home", c.home())
    show(c, f"{ROOT}/{CLASS}", "L1")                      # .idw 가 여기 있는가
    show(c, f"{ROOT}/{CLASS}/data", "L2")                 # 또는 여기인가
    show(c, f"{ROOT}/{CLASS}/data/{IDW}", "L3")           # {idp}.idp 와 {idp}/ 가 보여야 함
    show(c, f"{ROOT}/{CLASS}/data/{IDW}/{IDP}", "L4")     # raw 폴더 내용
```

보고 싶은 것:

- `L1`~`L3` 중 어디에 `{IDW}.idw`가 있는가. 아무 데도 없으면 `.idw`가 쓰이는 다른
  경로를 알고 있는지 알려 주십시오.
- `L3`에 `{IDP}.idp`와 `{IDP}/` 폴더가 **둘 다** 있는가. `.idp` 외에 같은 stem의
  다른 파일(예: `.idpx`, `.bak`)이 있는가.
- `L4`의 파일 목록. 확장자 종류와 개수, 하위 폴더 유무. 복사하면 안 되는 파일
  (장비가 실행 중에 쓰는 임시 파일, 로그 등)이 있어 보이면 그 이름.
- `L2`의 entries 수. 장비 한 대의 class 하나에 레시피가 몇 개 있는지의 감입니다.

## 2. 쓰기 동작 조사 (조사용 폴더 안에서만)

앱의 쓰기 경로는 `FtpClient.put`(임시 이름 STOR → `RNTO`)입니다. 덮어쓰기 모드와
폴더 생성을 추가하려면 서버가 다음을 허용하는지 알아야 합니다. 스크립트는 로그인
홈 아래 `sknn_probe_261018/`를 만들고, 끝나면 자기가 만든 것을 전부 지웁니다. 조사
중간에 끊기면 그 폴더만 남으니 손으로 지우면 됩니다.

```python
import secrets
from ftplib import error_perm

with client() as c:
    ftp = c._ftp
    home = c.home()
    base = f"{home.rstrip('/')}/sknn_probe_261018"
    # (A) MKD
    try:
        ftp.mkd(base); print("A MKD ok")
    except error_perm as exc:
        print("A MKD refused:", str(exc)[:60]); raise SystemExit
    # (B) 중첩 MKD — class 폴더를 만들 때 data/ 까지 한 번에 되는가
    try:
        ftp.mkd(f"{base}/x/y"); print("B nested MKD ok (한 번에 두 단계)")
    except error_perm as exc:
        print("B nested MKD refused:", str(exc)[:60])
        ftp.mkd(f"{base}/x"); ftp.mkd(f"{base}/x/y"); print("B one level at a time ok")
    # (C) put 으로 파일 생성
    target = f"{base}/x/y/probe.txt"
    c.put(target, b"one"); print("C put ok")
    # (D) RNTO 가 기존 파일을 덮는가
    temp = f"{target}.{secrets.token_hex(4)}.part"
    ftp.storbinary(f"STOR {temp}", __import__("io").BytesIO(b"two"))
    try:
        ftp.rename(temp, target); print("D RNTO over existing: REPLACED")
        overwritten = True
    except error_perm as exc:
        print("D RNTO over existing: REFUSED", str(exc)[:60]); overwritten = False
    # (E) 내용 확인
    buf = bytearray()
    ftp.retrbinary(f"RETR {target}", buf.extend)
    print("E content now:", bytes(buf))
    # (F) DELE 후 RNTO (D 가 REFUSED 일 때 앱이 쓸 경로)
    if not overwritten:
        ftp.delete(target); ftp.rename(temp, target); print("F DELE+RNTO ok")
    # (G) 디렉터리 위로 RNTO 는 어떻게 되는가 (put 의 SIZE 검사가 폴더를 못 보는 문제)
    ftp.mkd(f"{base}/x/y/dirtarget")
    ftp.storbinary(f"STOR {base}/x/y/f2", __import__("io").BytesIO(b"z"))
    try:
        ftp.rename(f"{base}/x/y/f2", f"{base}/x/y/dirtarget"); print("G RNTO onto dir: ACCEPTED (!)")
    except error_perm as exc:
        print("G RNTO onto dir: refused", str(exc)[:60])
    # 정리
    for p in (f"{base}/x/y/f2", f"{base}/x/y/dirtarget/f2", target, temp):
        try: ftp.delete(p)
        except Exception: pass
    for d in (f"{base}/x/y/dirtarget", f"{base}/x/y", f"{base}/x", base):
        try: ftp.rmd(d)
        except Exception as exc: print("cleanup left:", d, str(exc)[:40])
    print("done")
```

(G)에서 `ACCEPTED`가 나오면 `f2`가 `dirtarget/` 안으로 들어갔을 수 있어 정리
루프가 그 경로도 지웁니다.

## 3. 세션 수 (알면 적어 주십시오, 조사 불필요)

장비 FTP에 동시에 열 수 있는 세션 수의 상한을 알고 있으면 적어 주십시오. 모르면
"모름"으로 충분합니다. 앱은 장비당 연결 1개만 쓰고, `msr_image`가 같은 장비를 읽을
때 +1입니다.

## 4. 회신

- A. 1절 스크립트 출력 전체입니다(`L1`~`L4`). 레시피 이름은 지워도 됩니다.
- B. `.idw`가 있던 위치: `L1` / `L2` / `L3` / `없음` 중 하나.
- C. 2절 스크립트 출력 전체입니다. 특히 `A`, `B`, `D`, `E`, `G` 줄.
- D. `cleanup left:` 줄이 있었는지, 손으로 지웠는지.
- E. 3절의 세션 상한 또는 `모름`.
- F. 2절을 돌린 장비의 eqp_id와 그 장비가 유휴 상태였는지.
