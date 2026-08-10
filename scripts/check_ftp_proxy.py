"""Check the FTP proxy host after a deploy — reachable, configured, current.

The proxy's server half (`ftp_handler/proxy/flask_proxy.py`) lives on a
different machine than skewnono and is deployed by hand, so "did my change
actually land there" is a real question with no git to ask. This runs the
checks from `docs/deployment-ftp-proxy.md` §5 so nobody has to hand-assemble a
POST with the right quoting:

    .venv/bin/python -m scripts.check_ftp_proxy
    .venv\\Scripts\\python -m scripts.check_ftp_proxy     # office Windows PC

Run it from the office network — `aipp01` does not resolve from home.

Nothing here touches a measuring tool. The download probe deliberately sends an
EMPTY spec list: the route builds its downloader (reading the proxy's
environment) before it looks at the specs, so an empty list exercises the
credential configuration and opens no FTP connection at all. It is safe to run
as often as you like.

## What each check can and cannot prove

    healthz    the blueprint is mounted and the app is up. NOT that the
               credentials are set -- healthz never builds a downloader, so it
               answers `ok` on a proxy that 500s every real request.
    env        FTP_PROXY_FTP_USER / FTP_PROXY_FTP_PASSWORD are readable on the
               proxy host. This is the only server-side fact checkable from
               here.
    client     the vendored ftp_handler IN THIS REPO supports per-host
               credentials. Says nothing about the proxy host's copy.

The proxy host's own version cannot be checked remotely: `healthz` carries no
version, and a stale server half fails by silently IGNORING per-host
credentials rather than erroring. This script prints the one-liner to run in a
shell on that host; there is no way around going there.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Read the deployment's proxy location from the code that actually uses it, so
# this script can never drift from where requests really go.
from ftp_handler.proxy.proxy_downloader import PROXY_TOKEN, PROXY_URL  # noqa: E402

HEALTH_PATH = "/healthz_sknn_v3"
DOWNLOAD_PATH = "/download_sknn_v3"

VERSION_PROBE = (
    'python -c "from ftp_handler.direct_downloader import HostSpec; '
    "print('per-host credentials:', 'user' in HostSpec.__dataclass_fields__)\""
)


def _headers(token: str | None) -> dict:
    return {"Authorization": f"Bearer {token}"} if token else {}


def _check_health(requests, base: str, token: str | None, timeout: float) -> bool:
    print("[1/3] healthz — 프록시가 살아 있는가")
    try:
        response = requests.get(
            base + HEALTH_PATH, headers=_headers(token), timeout=timeout
        )
    except Exception as exc:  # noqa: BLE001 - any transport failure is the answer
        print(f"      FAIL  연결 불가: {type(exc).__name__}")
        print("      사내망에서 실행했는지, 앱이 기동 중인지 확인하십시오.")
        return False

    if response.status_code == 200:
        print(f"      OK    {response.text.strip()[:80]}")
        print("      (크리덴셜이 없어도 통과하는 검사입니다 — 2단계가 본론입니다.)")
        return True
    print(f"      FAIL  HTTP {response.status_code}")
    return False


def _check_env(requests, base: str, token: str | None, timeout: float) -> bool:
    print("[2/3] download(빈 specs) — 프록시 호스트에 FTP 환경 변수가 있는가")
    try:
        response = requests.post(
            base + DOWNLOAD_PATH,
            json={"specs": []},
            headers=_headers(token),
            timeout=timeout,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"      FAIL  연결 불가: {type(exc).__name__}")
        return False

    if response.status_code == 200:
        print(f"      OK    {response.text.strip()[:80]}")
        return True
    if response.status_code == 500:
        print("      FAIL  HTTP 500 — FTP_PROXY_FTP_USER / FTP_PROXY_FTP_PASSWORD 누락")
        print("      프록시 호스트의 wsgi.ini 에 env= 두 줄을 넣고 재기동하십시오.")
        return False
    if response.status_code == 401:
        print("      FAIL  HTTP 401 — 프록시가 FTP_PROXY_TOKEN 을 요구합니다.")
        print("      --token <값> 을 붙여 다시 실행하십시오.")
        return False
    print(f"      FAIL  HTTP {response.status_code}: {response.text.strip()[:120]}")
    return False


def _check_client_version() -> bool:
    print("[3/3] 이 레포의 vendored ftp_handler 버전")
    from ftp_handler.direct_downloader import HostSpec

    fields = HostSpec.__dataclass_fields__
    supported = "user" in fields and "password" in fields
    if supported:
        print("      OK    장비별 크리덴셜 지원 (2026-08-10 이후)")
    else:
        print("      FAIL  장비별 크리덴셜 미지원 — git pull 이 필요합니다.")
    return supported


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_ftp_proxy",
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="장비에 접속하지 않으므로 몇 번을 돌려도 안전합니다.",
    )
    parser.add_argument(
        "--url",
        default=PROXY_URL,
        help=f"프록시 주소 (기본값은 코드의 PROXY_URL: {PROXY_URL})",
    )
    parser.add_argument(
        "--token",
        default=PROXY_TOKEN,
        help="FTP_PROXY_TOKEN 을 쓰는 배포라면 그 값",
    )
    parser.add_argument(
        "--timeout", type=float, default=15.0, help="HTTP 타임아웃 초 (기본 15)"
    )
    args = parser.parse_args(argv)

    try:
        import requests
    except ImportError:
        raise SystemExit(
            "error: requests 가 없습니다. venv 인터프리터로 실행하십시오 "
            "(.venv/bin/python -m scripts.check_ftp_proxy)."
        ) from None

    base = args.url.rstrip("/")
    print(f"프록시: {base}\n")

    results = [
        _check_health(requests, base, args.token, args.timeout),
        _check_env(requests, base, args.token, args.timeout),
        _check_client_version(),
    ]

    print()
    if all(results):
        print("원격에서 확인 가능한 항목은 모두 통과했습니다.")
    else:
        print(f"{results.count(False)}건 실패 — 위 안내를 따르십시오.")

    # Always printed, pass or fail: the server half's version is the one thing
    # this script cannot reach, and a stale one fails silently rather than
    # loudly. Leaving it to "check if something looks wrong" is how it gets
    # skipped -- by then the symptom is an authentication error on one vendor's
    # tools, which reads like a credential problem, not a deploy problem.
    print()
    print("남은 검사 — 프록시 호스트의 셸에서 직접 실행해야 합니다:")
    print(f"    cd <PYTHONPATH> && {VERSION_PROBE}")
    print("    (<PYTHONPATH> 는 그 앱 wsgi.ini 의 pythonpath 값입니다)")
    print("절차 전체: docs/deployment-ftp-proxy.md")

    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
