"""활동 로그가 어느 OpenSearch alias 로 나가는지, 나가기는 하는지 확인합니다.

새 로그 필드를 추가했거나 계측 결과가 비어 있을 때 가장 먼저 볼 곳입니다.
같은 alias 를 쓰기와 읽기가 함께 잘못 보고 있으면 아무 이상이 없어 보이므로,
alias 를 사람 눈으로 확인하는 것 자체가 목적입니다.

    python -m scripts.verify.check_logging_target
    python scripts/verify/check_logging_target.py
    python scripts/verify/check_logging_target.py --user 2067928 --url myhost:8080

인자 없이 돌리면 환경만 읽어 alias 와 핸들러 설치 조건을 판정합니다. HTTP 를
타지 않으므로 인증도 셸도 주소도 문제되지 않습니다.

`--user` 를 주면 /api/health/logging 도 호출해 큐 드롭 카운터까지 봅니다. 그
값은 실행 중인 워커의 메모리에만 있어서 별도 프로세스로는 읽을 수 없기
때문입니다. admin ID 여야 하며, 아니면 403 이 돌아옵니다. 주소는 배포마다
다르므로 기본값을 두지 않습니다. `--url` 로 넘기거나 SKEWNONO_HEALTH_URL 에
한 번 정해 두십시오.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import scripts  # noqa: E402,F401  (applies the stdout UTF-8 fix)

from back_dev_home._logging.target import (  # noqa: E402
    LoggingConfigurationError,
    resolve_logging_target,
)
from back_dev_home._runtime.data_provider import get_mode  # noqa: E402
from back_dev_home._runtime.office_redis import load_env_file  # noqa: E402


_HEALTH_PATH = "/api/health/logging"

# 기본 주소를 두지 않습니다. 배포마다 host 와 port 가 다르고, 틀린 기본값은
# "연결 거부" 를 앱 문제로 읽게 만듭니다. SKEWNONO_HEALTH_URL 로 한 번 정해
# 두거나 --url 로 넘기십시오. host 만 줘도 됩니다.
_URL_ENV = "SKEWNONO_HEALTH_URL"


def resolve_url(raw: str) -> str:
    """host 든 전체 URL 이든 받아 health 엔드포인트 주소로 만듭니다."""
    url = raw if "://" in raw else f"http://{raw}"
    if _HEALTH_PATH in url:
        return url
    return url.rstrip("/") + _HEALTH_PATH


def report_environment() -> bool:
    """환경이 말하는 alias 와 설치 조건. 설치될 것으로 보이면 True 입니다."""
    mode = get_mode()
    password_set = bool(os.environ.get("OPENSEARCH_PASSWORD"))

    print("[environment]")
    print(f"  mode              = {mode}")
    print(f"  SKEWNONO_LOG_ENV  = {os.environ.get('SKEWNONO_LOG_ENV') or '(unset)'}")
    print(f"  OPENSEARCH_HOST   = {os.environ.get('OPENSEARCH_HOST') or '(unset)'}")
    print(f"  OPENSEARCH_PASSWORD set = {password_set}")

    try:
        target = resolve_logging_target()
    except LoggingConfigurationError as exc:
        print(f"  alias             = (해석 실패) {exc}")
        print()
        print("SKEWNONO_LOG_ENV 를 'local' 또는 'production' 으로 두십시오.")
        print("값이 없거나 오타면 핸들러는 부팅 시점에 거부합니다.")
        return False

    print(f"  alias             = {target.alias}")
    print(f"  deployment        = {target.deployment}")

    installs = mode == "office" and password_set
    print()
    print(f"[verdict] 이 환경이면 핸들러가 설치되는가: {installs}")
    if not installs:
        if mode != "office":
            print("  - mode 가 office 가 아닙니다. 집에서는 로그를 보내지 않습니다.")
        if not password_set:
            print("  - OPENSEARCH_PASSWORD 가 없습니다. 핸들러를 건너뜁니다.")
    print()
    print("주의: 여기 보이는 값은 '이 셸' 의 환경입니다. Flask 를 다른 환경에서")
    print("띄웠다면 실제 워커가 보는 값과 다를 수 있습니다. --user 로 확인하십시오.")
    return installs


def report_endpoint(url: str, user: str) -> int:
    """실행 중인 워커에게 직접 묻습니다. 종료 코드를 돌려줍니다."""
    print()
    print(f"[endpoint] {url}")
    request = urllib.request.Request(url, headers={"Cookie": f"LASTUSER={user}"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        print(f"  HTTP {exc.code}: {body}")
        if exc.code == 403:
            print("  -> 이 ID 는 admin 이 아닙니다. 위의 [environment] 로 충분합니다.")
        return 1
    except Exception as exc:
        print(f"  호출 실패: {type(exc).__name__}: {exc}")
        print("  -> Flask 가 그 주소에서 돌고 있는지, --url 이 맞는지 보십시오.")
        return 1

    print(json.dumps(payload, indent=2, ensure_ascii=False))

    diagnostics = payload.get("diagnostics") or {}
    dropped = diagnostics.get("queue_full_dropped")
    bulk_dropped = diagnostics.get("bulk_dropped")
    if not payload.get("installed"):
        print()
        print("installed=false: 이 워커는 로그를 보내지 않습니다.")
    elif dropped or bulk_dropped:
        print()
        print(f"경고: 문서가 버려지고 있습니다 (queue_full={dropped}, bulk={bulk_dropped}).")
        print("이 상태의 집계는 표본이 온전하지 않으므로 그대로 믿지 마십시오.")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--user",
        help="LASTUSER 쿠키에 넣을 admin ID. 주면 /api/health/logging 도 호출합니다.",
    )
    parser.add_argument(
        "--url",
        default=os.environ.get(_URL_ENV),
        help=(
            "앱 주소. host:port 만 줘도 되고 전체 URL 도 됩니다. "
            f"기본값은 환경 변수 {_URL_ENV} 입니다."
        ),
    )
    return parser.parse_args(argv)


def main() -> int:
    args = parse_args()
    print(f"python {sys.version.split()[0]}  stdout={sys.stdout.encoding}")
    print()

    load_env_file()  # 조건 없이 읽습니다. 이미 있는 값은 덮지 않습니다.
    report_environment()

    if args.user:
        if not args.url:
            print()
            print("--user 를 쓰려면 앱 주소가 필요합니다. 기본값은 두지 않습니다.")
            print("  python -m scripts.verify.check_logging_target --user <ID> --url <host:port>")
            print(f"또는 {_URL_ENV} 를 환경에 두면 다음부터는 생략됩니다.")
            return 1
        return report_endpoint(resolve_url(args.url), args.user)

    print()
    print("큐 드롭 카운터까지 보려면: --user <admin ID> --url <host:port>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
