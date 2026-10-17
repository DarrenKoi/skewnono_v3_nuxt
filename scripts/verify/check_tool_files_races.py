"""Replay the tool-files WATCH/MULTI races against the real office Redis.

Home can only stage a WatchError on a fake, so whether the real transactions
abort and retry correctly is an office question (ticket 09):

    .venv/bin/python -m scripts.verify.check_tool_files_races
    .venv\\Scripts\\python -m scripts.verify.check_tool_files_races     # office Windows PC

Each scenario seeds a request, then lets a SECOND connection write between the
adapter's WATCH and its EXEC, exactly where a concurrent admin or a re-request
would land. Real Redis must then abort the EXEC; the adapter must answer with
409 (RequestChanged) or a clean retry, never a grant the admin did not see.

Safe on the live store: the adapter's two keys are pointed at a scratch
namespace (``skewnono:tool_files:racecheck:*``) for the whole run and deleted
afterwards, so no real grant or request is read or touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
import scripts  # noqa: E402,F401  (applies the stdout UTF-8 fix)

import json  # noqa: E402
from collections.abc import Callable  # noqa: E402

from backend.ebeam.tool_files.providers import office_example as office  # noqa: E402

_PREFIX = "skewnono:tool_files:racecheck"
_GRANTS = f"{_PREFIX}:grants"
_REQUESTS = f"{_PREFIX}:requests"
_GRANT = {"granted_at": "2026-10-17T00:00:00Z", "granted_by": "racecheck"}


def _request(request_id: str, dept_nm: str = "RACE-TEAM") -> dict:
    return {
        "request_id": request_id,
        "reason": "racecheck",
        "dept_nm": dept_nm,
        "requested_at": "2026-10-17T00:00:00Z",
        "status": "pending",
    }


class _Interleaving:
    """Hands the adapter its own connection, and fires ``hook`` once on a
    second connection right before the adapter's first MULTI: after WATCH and
    the reads, before EXEC."""

    def __init__(self, adapter_client, rival_client):
        self._adapter = adapter_client
        self.rival = rival_client
        self.hook: Callable[[], None] | None = None
        self.multis = 0

    def __getattr__(self, name):
        return getattr(self._adapter, name)

    def pipeline(self, *args, **kwargs):
        pipe = self._adapter.pipeline(*args, **kwargs)
        real_multi = pipe.multi
        outer = self

        def multi():
            outer.multis += 1
            if outer.hook is not None:
                hook, outer.hook = outer.hook, None
                hook()
            return real_multi()

        pipe.multi = multi
        return pipe


def _put(client, key: str, field: str, record: dict) -> None:
    client.hset(key, field, json.dumps(record, ensure_ascii=False))


def _get(client, key: str, field: str) -> dict | None:
    raw = client.hget(key, field)
    return None if raw is None else json.loads(raw)


def _approve_vs_rerequest(c: _Interleaving) -> str:
    _put(c, _REQUESTS, "9000001", _request("r1"))
    c.hook = lambda: _put(c.rival, _REQUESTS, "9000001", _request("r2"))
    try:
        office.approve_request("9000001", "r1", _GRANT)
    except office.RequestChanged:
        pass
    else:
        return "approve went through although the request changed"
    if c.hexists(_GRANTS, "emp:9000001"):
        return "a grant was written for a request the admin did not see"
    if (_get(c, _REQUESTS, "9000001") or {}).get("request_id") != "r2":
        return "the re-request was lost"
    return ""


def _reject_vs_rerequest(c: _Interleaving) -> str:
    _put(c, _REQUESTS, "9000002", _request("r1"))
    c.hook = lambda: _put(c.rival, _REQUESTS, "9000002", _request("r2"))
    try:
        office.reject_request("9000002", "r1")
    except office.RequestChanged:
        pass
    else:
        return "reject went through although the request changed"
    after = _get(c, _REQUESTS, "9000002") or {}
    if (after.get("request_id"), after.get("status")) != ("r2", "pending"):
        return f"the re-request was overwritten: {after}"
    return ""


def _approve_vs_unrelated(c: _Interleaving) -> str:
    _put(c, _REQUESTS, "9000003", _request("r1"))
    c.hook = lambda: _put(c.rival, _REQUESTS, "9000099", _request("x"))
    office.approve_request("9000003", "r1", _GRANT)
    if c.multis < 2:
        return "EXEC was not aborted, so the race was never exercised"
    if not c.hexists(_GRANTS, "emp:9000003") or c.hexists(_REQUESTS, "9000003"):
        return "the retry did not grant and clear the request"
    return ""


def _team_vs_new_member_request(c: _Interleaving) -> str:
    _put(c, _REQUESTS, "9000004", _request("a"))
    c.hook = lambda: _put(c.rival, _REQUESTS, "9000005", _request("b"))
    _, cleared = office.approve_team("RACE-TEAM", _GRANT)
    if c.multis < 2:
        return "EXEC was not aborted, so the race was never exercised"
    if cleared != ["9000004", "9000005"] or c.hexists(_REQUESTS, "9000005"):
        return f"the late request was not judged on the retry: cleared={cleared}"
    return ""


def _team_vs_empno_approval(c: _Interleaving) -> str:
    _put(c, _REQUESTS, "9000006", _request("a"))
    _put(c, _REQUESTS, "9000007", _request("b"))

    def rival_approves_one():
        _put(c.rival, _GRANTS, "emp:9000006", _GRANT)
        c.rival.hdel(_REQUESTS, "9000006")

    c.hook = rival_approves_one
    _, cleared = office.approve_team("RACE-TEAM", _GRANT)
    if cleared != ["9000007"]:
        return f"team approval claimed a request another admin handled: cleared={cleared}"
    if not c.hexists(_GRANTS, "team:RACE-TEAM"):
        return "the team grant is missing"
    return ""


SCENARIOS: list[tuple[str, Callable[[_Interleaving], str]]] = [
    ("approve <-> re-request", _approve_vs_rerequest),
    ("reject <-> re-request", _reject_vs_rerequest),
    ("approve <-> unrelated request", _approve_vs_unrelated),
    ("team approve <-> new member request", _team_vs_new_member_request),
    ("team approve <-> empno approval", _team_vs_empno_approval),
]


def run(connect: Callable[[], object]) -> int:
    """``connect`` returns a fresh client each call; two distinct connections
    are what make the interleaving real."""
    keys = (office._GRANTS_KEY, office._REQUESTS_KEY)
    office._GRANTS_KEY, office._REQUESTS_KEY = _GRANTS, _REQUESTS
    failures = 0
    try:
        for name, scenario in SCENARIOS:
            client = _Interleaving(connect(), connect())
            client.delete(_GRANTS, _REQUESTS)
            original = office._client
            office._client = lambda c=client: c
            try:
                problem = scenario(client)
            except Exception as exc:  # report and keep going (scripts rule 7)
                problem = f"{type(exc).__name__}: {exc}"
            finally:
                office._client = original
                client.delete(_GRANTS, _REQUESTS)
            failures += bool(problem)
            print(f"{'FAIL' if problem else 'ok  '}  {name}" + (f"  -- {problem}" if problem else ""))
    finally:
        office._GRANTS_KEY, office._REQUESTS_KEY = keys
    print("----")
    print(f"{len(SCENARIOS) - failures}/{len(SCENARIOS)} scenarios passed")
    return 1 if failures else 0


def _office_connect():
    import redis

    from backend._runtime.office_redis import load_env_file

    load_env_file("REDIS_HOST")
    import os

    host = os.environ.get("REDIS_HOST")
    if not host:
        raise SystemExit(
            "REDIS_HOST is not set.\n"
            "Run from the repo root so backend/.env is found, or set "
            "REDIS_HOST / REDIS_PORT / REDIS_PASSWORD first."
        )
    return redis.Redis(
        host=host,
        port=int(os.environ.get("REDIS_PORT", "6379")),
        password=os.environ.get("REDIS_PASSWORD"),
        decode_responses=False,
        socket_connect_timeout=5,
        socket_timeout=10,
    )


def main() -> int:
    print(f"python {sys.version.split()[0]}  stdout={sys.stdout.encoding}")
    return run(_office_connect)


if __name__ == "__main__":
    raise SystemExit(main())
