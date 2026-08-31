from __future__ import annotations

import runpy
import sys
from pathlib import Path
from types import ModuleType

import pandas as pd
import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probes" / "inspect_redis_key.py"


class FakeRedisClient:
    def type(self, key: bytes) -> bytes:
        assert key == b"v3_df_sem_list"
        return b"string"

    def get(self, key: bytes) -> bytes:
        assert key == b"v3_df_sem_list"
        return b"parquet"


def _office_redis_module(
    fake_client: FakeRedisClient,
    dataframe: pd.DataFrame,
    connection_calls: list[bool],
) -> ModuleType:
    module = ModuleType("back_dev_home._runtime.office_redis")
    module.STORE_ERRORS = (ConnectionError,)
    module.read_dataframe = lambda raw, key: dataframe
    module.redis_text = lambda value: value.decode() if isinstance(value, bytes) else str(value)

    def redis_client() -> FakeRedisClient:
        connection_calls.append(True)
        return fake_client

    module.redis_client = redis_client
    return module


def test_console_execution_exposes_redis_and_dataframe_variables(monkeypatch) -> None:
    fake_client = FakeRedisClient()
    dataframe = pd.DataFrame({"eqp_id": ["SEM-01"]})
    connection_calls: list[bool] = []
    fake_module = _office_redis_module(fake_client, dataframe, connection_calls)
    monkeypatch.setitem(sys.modules, "back_dev_home._runtime.office_redis", fake_module)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT)])

    try:
        namespace = runpy.run_path(str(SCRIPT), run_name="__main__")
    except SystemExit as err:
        pytest.fail(f"console execution must not exit: {err}")

    assert namespace["client"] is fake_client
    assert namespace["key"] == namespace["KEY_NAME"].encode()
    assert namespace["kind"] == "string"
    assert namespace["raw"] == b"parquet"
    assert namespace["df"] is dataframe
    assert connection_calls == [True]


def test_importing_helpers_does_not_connect_to_redis(monkeypatch) -> None:
    fake_client = FakeRedisClient()
    dataframe = pd.DataFrame({"eqp_id": ["SEM-01"]})
    connection_calls: list[bool] = []
    fake_module = _office_redis_module(fake_client, dataframe, connection_calls)
    monkeypatch.setitem(sys.modules, "back_dev_home._runtime.office_redis", fake_module)

    namespace = runpy.run_path(str(SCRIPT), run_name="inspect_redis_key_import")

    assert callable(namespace["_human_bytes"])
    assert callable(namespace["describe_dataframe"])
    assert connection_calls == []


def test_passing_the_key_as_an_argument_is_refused(monkeypatch) -> None:
    """A supplied key must fail loudly instead of being silently ignored.

    The script inspects `KEY_NAME` from its own source, so
    `-m scripts.probes.inspect_redis_key v3_df_sem_avail` used to print
    `v3_df_sem_list`'s schema under the operator's belief that it was avail's.
    Refusing costs one retry; the silent version costs a wrong datatables entry.
    """
    fake_client = FakeRedisClient()
    dataframe = pd.DataFrame({"eqp_id": ["SEM-01"]})
    connection_calls: list[bool] = []
    fake_module = _office_redis_module(fake_client, dataframe, connection_calls)
    monkeypatch.setitem(sys.modules, "back_dev_home._runtime.office_redis", fake_module)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "v3_df_sem_avail"])

    with pytest.raises(SystemExit) as err:
        runpy.run_path(str(SCRIPT), run_name="__main__")

    message = str(err.value)
    assert "KEY_NAME" in message
    assert "v3_df_sem_avail" in message
    # Refused before opening a connection: the office Redis handshake is the
    # slow part, and a doomed run must not pay for it.
    assert connection_calls == []
