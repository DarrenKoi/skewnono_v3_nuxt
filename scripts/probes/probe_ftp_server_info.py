"""What can this tool's FTP server tell us about itself? (disk free, features)

Asks a fixed, read-only list of FTP commands (FEAT, HELP, AVBL, SITE DF ...)
and prints each reply. Written for VeritySEM / Provision (Windows tools): if
the server answers AVBL or a SITE free-space command, storage can be collected
over the FTP we already have, with nothing installed on the tool.

Two ways to reach the tool, same output:

    python -m scripts.probes.probe_ftp_server_info --host 10.1.2.3            # via the proxy
    python -m scripts.probes.probe_ftp_server_info --host 10.1.2.3 --direct   # direct FTP

This file is ALSO the proxy-side add-on. The vendored ftp_handler is shared
with other repos and synced from upstream with `rsync --delete`, so this route
lives outside it and the proxy host mounts it beside the stock blueprint:

    1. copy this one file next to ftp_handler/ on the proxy host (the app's
       PYTHONPATH, see docs/deployment-ftp-proxy.md 4.1)
    2. in that app:  from probe_ftp_server_info import ftp_server_info_sknn_v3
                     app.register_blueprint(ftp_server_info_sknn_v3)

The server half needs only flask + stdlib ftplib. It never takes a command
from the wire -- only host/credentials/directory -- so the route cannot be
turned into a write (DELE, RMD, STOR) by any caller. Auth and the credential
fallback match flask_proxy: FTP_PROXY_TOKEN, FTP_PROXY_FTP_USER/_PASSWORD.
"""

from __future__ import annotations

import argparse
import ftplib
import hmac
import os
import sys
from pathlib import Path

# Bootstrap for the client CLI (scripts/README.md 1). Harmless on the proxy
# host, where this file sits flat and `scripts` does not exist.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
try:
    import scripts  # noqa: F401  (applies the stdout UTF-8 fix)
except ImportError:
    pass

URL_SERVER_INFO = "/server_info_sknn_v3"
ERROR_STATUS = 422
DEFAULT_DIR = "/D_Drive"

# Read-only by construction: informational verbs only. "{dir}" is the one
# caller-supplied value, and _check_dir keeps it to a single line.
COMMANDS = (
    "SYST",
    "FEAT",
    "HELP",
    "HELP SITE",
    "STAT",
    "AVBL",
    "AVBL {dir}",
    "SITE DF",
    "SITE DF {dir}",
    "SITE DISKFREE",
    "SITE DISKFREE {dir}",
)
FREE_SPACE_PREFIXES = ("AVBL", "SITE DF", "SITE DISKFREE")


def _check_dir(remote_dir: object) -> str:
    # A CR/LF would end our command and start a second one on the control
    # channel -- the only way an injected write could get in.
    if not isinstance(remote_dir, str) or any(c in remote_dir for c in "\r\n\0"):
        raise ValueError("remote_dir must be a single-line string")
    return remote_dir


def run_probe(ftp: ftplib.FTP, remote_dir: str) -> list[dict]:
    """Every COMMANDS reply; a 5xx is recorded, not raised -- it IS the answer."""
    remote_dir = _check_dir(remote_dir)
    replies = []
    for template in COMMANDS:
        cmd = template.format(dir=remote_dir)
        try:
            replies.append({"cmd": cmd, "ok": True, "reply": ftp.sendcmd(cmd)})
        except ftplib.error_perm as exc:  # 5xx: not supported / refused
            replies.append({"cmd": cmd, "ok": False, "reply": str(exc)})
        except ftplib.error_reply as exc:  # unexpected 1xx/3xx
            replies.append({"cmd": cmd, "ok": False, "reply": str(exc)})
    return replies


def probe_direct(
    host: str,
    user: str,
    password: str,
    *,
    port: int = 21,
    timeout: float = 8.0,
    encoding: str = "latin-1",
    remote_dir: str = DEFAULT_DIR,
) -> dict:
    ftp = ftplib.FTP(timeout=timeout, encoding=encoding)
    try:
        welcome = ftp.connect(host=host, port=port, timeout=timeout)
        ftp.login(user=user, passwd=password)
        return {"host": host, "welcome": welcome, "replies": run_probe(ftp, remote_dir)}
    finally:
        ftp.close()


# ---- server half (proxy host) ------------------------------------------------


def _make_blueprint():
    from flask import Blueprint, jsonify, request

    bp = Blueprint("ftp_server_info_sknn_v3", __name__)

    @bp.post(URL_SERVER_INFO)
    def server_info():
        token = os.getenv("FTP_PROXY_TOKEN")
        if token is not None and not hmac.compare_digest(
            request.headers.get("Authorization", ""), f"Bearer {token}"
        ):
            return jsonify({"error": "unauthorized"}), 401

        def fail(code: str, exc: BaseException):
            return jsonify({"code": code, "error": str(exc)}), ERROR_STATUS

        try:
            body = request.get_json(force=True)
            if not isinstance(body, dict) or not isinstance(body.get("host"), str):
                raise ValueError("body must be a JSON object with a string 'host'")
            kwargs = {
                "port": int(body.get("port", 21)),
                "timeout": float(body.get("timeout", 8.0)),
                "encoding": str(body.get("encoding", "latin-1")),
                "remote_dir": _check_dir(body.get("remote_dir", DEFAULT_DIR)),
            }
        except (TypeError, ValueError) as exc:
            return fail("bad_request", exc)
        try:
            return jsonify(
                probe_direct(
                    body["host"],
                    body.get("user", os.getenv("FTP_PROXY_FTP_USER", "")),
                    body.get("password", os.getenv("FTP_PROXY_FTP_PASSWORD", "")),
                    **kwargs,
                )
            )
        except UnicodeError as exc:
            return fail("encoding", exc)
        except ftplib.all_errors as exc:  # connect / login
            return fail("unreachable", exc)

    return bp


try:
    ftp_server_info_sknn_v3 = _make_blueprint()
except ImportError:  # client-only machine without flask
    ftp_server_info_sknn_v3 = None


# ---- client half (office PC) -------------------------------------------------


def probe_via_proxy(
    host: str,
    user: str | None,
    password: str | None,
    *,
    proxy_url: str,
    token: str | None,
    port: int = 21,
    timeout: float = 8.0,
    encoding: str = "latin-1",
    remote_dir: str = DEFAULT_DIR,
) -> dict:
    import requests

    payload = {
        "host": host,
        "port": port,
        "timeout": timeout,
        "encoding": encoding,
        "remote_dir": remote_dir,
    }
    if user is not None:  # omitted -> the proxy host's own account
        payload.update(user=user, password=password or "")
    response = requests.post(
        proxy_url.rstrip("/") + URL_SERVER_INFO,
        json=payload,
        headers={"Authorization": f"Bearer {token}"} if token else {},
        # Eleven commands, each bounded by `timeout` on the proxy side.
        timeout=(10, timeout * (len(COMMANDS) + 2)),
    )
    if response.status_code == 404:
        raise SystemExit(
            f"{URL_SERVER_INFO} 가 프록시에 없습니다 (404). 이 파일을 프록시 호스트에\n"
            "복사하고 블루프린트를 등록했는지 확인하세요 (파일 머리말 1-2 단계).\n"
            "또는 --direct 로 직접 접속하세요."
        )
    if response.status_code != 200:
        raise RuntimeError(f"proxy {response.status_code}: {response.text[:300]}")
    return response.json()


def _print_result(result: dict) -> None:
    print(f"---- {result['host']}")
    print(f"  welcome: {result['welcome']}")
    for item in result["replies"]:
        mark = "OK  " if item["ok"] else "FAIL"
        reply = item["reply"].replace("\r", "").replace("\n", "\n        ")
        print(f"  {mark} {item['cmd']!r}\n        {reply}")
    answered = [
        item["cmd"]
        for item in result["replies"]
        if item["ok"] and item["cmd"].startswith(FREE_SPACE_PREFIXES)
    ]
    if answered:
        print(f"  => 여유 공간 명령 응답 있음: {', '.join(answered)}")
    else:
        print("  => 여유 공간 명령 응답 없음 (FTP 만으로는 불가, 장비 쪽 예약 작업 필요)")


def main() -> None:
    print(f"python {sys.version.split()[0]}  stdout={sys.stdout.encoding}")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--host", action="append", required=True, help="tool IP; repeatable")
    parser.add_argument("--direct", action="store_true", help="direct FTP instead of the proxy")
    parser.add_argument("--user", default=os.getenv("SKEWNONO_TOOL_FTP_USER"))
    parser.add_argument("--password", default=os.getenv("SKEWNONO_TOOL_FTP_PASSWORD"))
    parser.add_argument("--port", type=int, default=21)
    parser.add_argument("--timeout", type=float, default=8.0)
    parser.add_argument("--encoding", default="latin-1")
    parser.add_argument("--dir", default=DEFAULT_DIR, help=f"directory for AVBL/SITE DF (default {DEFAULT_DIR})")
    args = parser.parse_args()

    if args.direct and args.user is None:
        raise SystemExit("--direct 에는 --user/--password (또는 SKEWNONO_TOOL_FTP_USER/_PASSWORD) 가 필요합니다.")
    if not args.direct:
        # Same location/auth the real proxy clients use, so this cannot drift.
        from ftp_handler.proxy.proxy_downloader import PROXY_TOKEN, PROXY_URL

        print(f"proxy: {PROXY_URL}")

    common = dict(port=args.port, timeout=args.timeout, encoding=args.encoding, remote_dir=args.dir)
    failed = 0
    for host in args.host:  # one bad host never stops the rest (README 7)
        try:
            if args.direct:
                result = probe_direct(host, args.user, args.password or "", **common)
            else:
                result = probe_via_proxy(
                    host, args.user, args.password, proxy_url=PROXY_URL, token=PROXY_TOKEN, **common
                )
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001 - report and move on
            failed += 1
            print(f"---- {host}\n  FAIL {type(exc).__name__}: {exc}")
            continue
        _print_result(result)
    if failed == len(args.host):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
