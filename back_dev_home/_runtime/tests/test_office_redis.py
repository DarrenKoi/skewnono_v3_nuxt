"""The Redis plumbing every Redis-backed office adapter shares.

office_redis.py is the one module Phase 2 cannot route around: a bug in the
format dispatch or the client config breaks every office feature at once, and
it breaks it *at the office*, where this suite cannot be re-run against the
real store. So the tests pin the behaviour adapters rely on from bytes alone —
no Redis is dialled here (company data is unreachable from home anyway), and
constructing a redis.Redis never opens a socket, so the config assertions are
safe against a deliberately unroutable host.

Two invariants are load-bearing beyond this module and easy to break silently:

* Failures must be **exactly** LookupError. The app factory's handler checks
  ``type(err) is not LookupError`` and sends subclasses to a 500, so raising a
  KeyError instead would turn a diagnosable 502 into an opaque traceback.
* Unset config must be **exactly** RuntimeError, for the same reason (503).
"""

import gzip
import os
import pickle
import sys
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from redis.backoff import NoBackoff

from back_dev_home._runtime import office_redis
from back_dev_home._runtime.office_redis import (
    load_env_file,
    read_dataframe,
    redis_client,
)
# The live_alarm suite already owns an in-memory Redis double; a second copy
# here would be one more thing to keep honest.
from back_dev_home.ebeam.hitachi.live_alarm.tests.fake_redis import FakeRedis

# Everything these tests read from or write into the process environment.
CONNECTION_VARS = ("REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD", "OPENSEARCH_HOST")


@pytest.fixture(autouse=True)
def _no_connection_env(monkeypatch):
    """Strip the connection vars and drop the cached client around every test.

    The parent conftest's _clean_env only scrubs SKEWNONO_*; REDIS_HOST really
    is in .env on the dev machine and at the office, so the "unset" tests would
    otherwise pass a real host into the client. And redis_client is
    lru_cached — without cache_clear() the first test to build a client would
    hand its connection kwargs to every later test.
    """
    for name in CONNECTION_VARS:
        # setenv-then-delenv, because monkeypatch.delenv on an *absent* var
        # records no undo: the load_env_file tests write straight into
        # os.environ via python-dotenv, and a tmp_path value would leak out of
        # this module into the rest of the suite.
        monkeypatch.setenv(name, "")
        monkeypatch.delenv(name)
    redis_client.cache_clear()
    yield
    redis_client.cache_clear()


@pytest.fixture
def no_env_file(monkeypatch):
    """Make the .env fallback a no-op, and record that it was consulted.

    redis_client() reaches for .env before giving up, which on the dev machine
    would find a real REDIS_HOST and make "missing config" untestable.
    """
    calls = []
    monkeypatch.setattr(office_redis, "load_env_file", lambda var: calls.append(var))
    return calls


@pytest.fixture
def fake_package(monkeypatch, tmp_path):
    """Factory: aim load_env_file's package-relative path at a throwaway dir.

    load_env_file finds the second candidate through
    ``sys.modules["back_dev_home"].__file__``, so the real package would point
    at the real (gitignored, machine-dependent) .env. Returns the directory
    standing in for back_dev_home/.
    """

    def build(name: str = "pkg") -> Path:
        pkg_dir = tmp_path / name
        pkg_dir.mkdir()
        monkeypatch.setitem(
            sys.modules,
            "back_dev_home",
            SimpleNamespace(__file__=str(pkg_dir / "__init__.py")),
        )
        return pkg_dir

    return build


def _parquet(df: pd.DataFrame) -> bytes:
    """What the office writer produces: df.to_parquet() into a buffer."""
    buffer = BytesIO()
    df.to_parquet(buffer, engine="pyarrow", index=False)
    return buffer.getvalue()


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {"eqp_id": ["TP01", "TP02"], "version": ["1.20", "3.40"]}
    )


# ------------------------------------------------------------- read_dataframe

def test_parquet_payload_round_trips_with_text_columns_intact():
    """The office's actual encoding, and why it is the preferred one.

    Parquet carries dtypes, so a version like "1.20" comes back as the str it
    was written as. The JSON branch below does not manage that — see
    test_json_payload_does_not_preserve_column_dtypes.
    """
    df = _frame()
    out = read_dataframe(_parquet(df), "v3_df_sem_version")

    assert list(out.columns) == ["eqp_id", "version"]
    assert out["version"].tolist() == ["1.20", "3.40"]


def test_parquet_is_selected_by_the_magic_bytes_not_the_key_name():
    """Dispatch is a property of the payload: adapters pass arbitrary keys."""
    raw = _parquet(_frame())
    assert raw[:4] == b"PAR1"
    assert len(read_dataframe(raw, "not-a-parquet-sounding-key")) == 2


def test_json_object_of_columns_payload_is_read_as_json():
    """df.to_json()'s default orient — a leading '{'."""
    out = read_dataframe(_frame().to_json().encode("utf-8"), "some_json_key")
    assert out["eqp_id"].tolist() == ["TP01", "TP02"]


def test_json_records_payload_is_read_as_json():
    """A leading '[' counts too: some writers store orient='records'."""
    raw = _frame().to_json(orient="records").encode("utf-8")
    assert raw[:1] == b"["
    out = read_dataframe(raw, "some_json_key")
    assert out["eqp_id"].tolist() == ["TP01", "TP02"]


def test_json_detection_tolerates_leading_whitespace():
    """_looks_like_json lstrips, so a pretty-printed or newline-prefixed dump
    still takes the JSON branch instead of falling through to pickle."""
    raw = b"\n  " + _frame().to_json().encode("utf-8")
    assert read_dataframe(raw, "some_json_key")["eqp_id"].tolist() == ["TP01", "TP02"]


def test_json_payload_does_not_preserve_column_dtypes():
    """Documented asymmetry, not an aspiration.

    read_json infers types, so a numeric-looking string column comes back as
    float64. Adapters that must guarantee str columns coerce them themselves
    (which is why feature-specific normalization stays in the adapter).
    """
    out = read_dataframe(_frame().to_json().encode("utf-8"), "some_json_key")
    assert out["version"].dtype == "float64"


def test_pickled_dataframe_payload_is_returned_as_is():
    df = _frame()
    out = read_dataframe(pickle.dumps(df), "legacy_pickle_key")
    assert out.equals(df)


def test_pickled_dict_payload_becomes_a_dataframe():
    """The df.to_dict() writer. The project stores dataframe-dicts widely, so
    a pickled dict is a plausible value, not a corrupt one."""
    out = read_dataframe(pickle.dumps(_frame().to_dict()), "legacy_dict_key")

    assert isinstance(out, pd.DataFrame)
    assert list(out.columns) == ["eqp_id", "version"]
    assert out["version"].tolist() == ["1.20", "3.40"]


# ------------------------------------------------------- diagnostic LookupError

def test_payload_of_the_wrong_type_names_the_key_and_what_it_got():
    """The reader needs both halves to act: which key, and what it actually
    held. 'expected a DataFrame' alone sends you back to Redis to look."""
    with pytest.raises(LookupError) as exc:
        read_dataframe(pickle.dumps(["TP01", "TP02"]), "v3_df_sem_avail")

    message = str(exc.value)
    assert "v3_df_sem_avail" in message
    assert "list" in message
    assert "expected a DataFrame or dict" in message


def test_wrong_type_raises_exactly_lookuperror_not_a_subclass():
    """The app factory 502-maps only ``type(err) is LookupError``; a subclass
    would be reported as an internal 500 and lose this message."""
    with pytest.raises(LookupError) as exc:
        read_dataframe(pickle.dumps(42), "v3_df_sem_avail")
    assert type(exc.value) is LookupError


def test_undeserializable_payload_reports_key_bytes_length_and_real_cause():
    """A gzipped value is the realistic version of this failure: someone
    changes the writer to compress and every reader breaks. The message has to
    carry enough to identify that without a debugger — hence the hex prefix
    (1f 8b is gzip) and the compression hint.
    """
    with pytest.raises(LookupError) as exc:
        read_dataframe(gzip.compress(pickle.dumps(_frame())), "v3_df_sem_avail")

    message = str(exc.value)
    assert type(exc.value) is LookupError
    assert "v3_df_sem_avail" in message
    assert "1f 8b" in message                       # the magic bytes, hex-spaced
    assert "UnpicklingError" in message             # the cause, not just "failed"
    assert "gzip 1f8b" in message                   # what to add a branch for
    assert "numpy" in message                       # the other common cause


def test_an_empty_value_is_a_diagnosable_failure_too():
    """A key written but never filled (a truncated or crashed writer) is not a
    missing key, so it reaches here — and must arrive as the plumbing's own
    LookupError rather than a bare EOFError from pickle."""
    with pytest.raises(LookupError) as exc:
        read_dataframe(b"", "v3_df_sem_avail")

    assert type(exc.value) is LookupError
    assert "length 0" in str(exc.value)


def test_non_utf8_binary_is_not_reported_as_a_decode_error():
    """Why _looks_like_json exists.

    An unconditional raw.decode('utf-8') fallback would turn every corrupt
    binary value into a UnicodeDecodeError from deep inside read_json, hiding
    that the real problem was the pickle. The failure must surface as the
    plumbing's own diagnostic instead.
    """
    with pytest.raises(LookupError) as exc:
        read_dataframe(b"\x89PNG\r\n\x1a\n\x80\x81", "v3_df_sem_avail")

    assert "UnicodeDecodeError" not in str(exc.value)


def test_bytes_straight_off_a_client_get_deserialize():
    """client.get(key) -> read_dataframe(raw, key), against a fake store.

    The composition adapters write, with nothing decoding in between
    (decode_responses=False): the value is handed to the deserializer as the
    bytes Redis returned. Values are poked into the store directly because the
    double's set() encodes str — parquet is binary.
    """
    client = FakeRedis()
    client.strings["v3_df_sem_avail"] = _parquet(_frame())

    out = read_dataframe(client.get("v3_df_sem_avail"), "v3_df_sem_avail")
    assert out["eqp_id"].tolist() == ["TP01", "TP02"]


def test_a_missing_key_is_the_adapters_guard_not_this_functions():
    """Where the contract boundary sits, so nobody assumes it is covered here.

    A GET on an unpopulated key returns None, and read_dataframe subscripts its
    argument immediately — a TypeError, which the app factory reports as a 500,
    not the 502 a missing key deserves. Every adapter therefore checks
    ``if raw is None: raise LookupError(...)`` before calling in (see
    sem_list/providers/office_example.py's _load_dataframe). Pinned because the
    key-not-yet-written case is the likeliest office failure of all, and an
    adapter that forgets the guard gets an opaque traceback instead.
    """
    client = FakeRedis()
    assert client.get("v3_df_sem_avail") is None

    with pytest.raises(TypeError):
        read_dataframe(client.get("v3_df_sem_avail"), "v3_df_sem_avail")


# --------------------------------------------------------------- redis_client

def test_missing_redis_host_raises_exactly_runtimeerror(no_env_file):
    """Unset config is a 503 ("backend unconfigured"), which the app factory
    keys off the exact RuntimeError type. The message has to say how to fix it,
    because the reader is usually someone who ran pytest from the wrong cwd."""
    with pytest.raises(RuntimeError) as exc:
        redis_client()

    message = str(exc.value)
    assert type(exc.value) is RuntimeError
    assert "REDIS_HOST" in message
    assert "back_dev_home/.env" in message


def test_missing_redis_host_consults_the_env_file_first(no_env_file):
    """A standalone `python -m ...providers.office` run has no Flask factory and
    no conftest to have loaded .env; redis_client must load it itself before
    concluding the host is unset."""
    with pytest.raises(RuntimeError):
        redis_client()

    assert no_env_file == ["REDIS_HOST"]


def test_the_missing_host_error_is_not_cached(monkeypatch, no_env_file):
    """lru_cache does not memoize exceptions, and the docstring promises that:
    fix the env after a failed first call and the next call must succeed
    instead of replaying the RuntimeError for the life of the process."""
    with pytest.raises(RuntimeError):
        redis_client()

    monkeypatch.setenv("REDIS_HOST", "redis.invalid")
    assert redis_client().connection_pool.connection_kwargs["host"] == "redis.invalid"


def test_client_can_be_built_from_a_dotenv_file_alone(
    monkeypatch, tmp_path, fake_package
):
    """The whole point of the .env fallback, end to end and unstubbed.

    Every MIGRATION.md verifies an adapter with a bare
    `python -m back_dev_home.<feature>.providers.office` — no Flask factory, no
    conftest, nothing in the environment. The client has to come up from the
    file on disk alone.
    """
    monkeypatch.chdir(tmp_path)
    (fake_package() / ".env").write_text(
        "REDIS_HOST=redis.invalid\nREDIS_PORT=6381\n"
    )

    kwargs = redis_client().connection_pool.connection_kwargs
    assert kwargs["host"] == "redis.invalid"
    assert kwargs["port"] == 6381


def test_one_client_and_pool_is_reused_per_process(monkeypatch):
    """The reason for the lru_cache: a fresh client per request would open a
    fresh TCP connection per request."""
    monkeypatch.setenv("REDIS_HOST", "redis.invalid")
    assert redis_client() is redis_client()


def test_client_takes_host_port_and_password_from_the_environment(monkeypatch):
    monkeypatch.setenv("REDIS_HOST", "redis.invalid")
    monkeypatch.setenv("REDIS_PORT", "6380")
    monkeypatch.setenv("REDIS_PASSWORD", "s3cret")

    kwargs = redis_client().connection_pool.connection_kwargs
    assert kwargs["host"] == "redis.invalid"
    assert kwargs["port"] == 6380  # int, not the "6380" string from the env
    assert kwargs["password"] == "s3cret"


def test_port_defaults_and_password_is_optional(monkeypatch):
    """The office store is reachable on the default port with no password on
    some hosts; requiring either would refuse a working config."""
    monkeypatch.setenv("REDIS_HOST", "redis.invalid")

    kwargs = redis_client().connection_pool.connection_kwargs
    assert kwargs["port"] == 6379
    assert kwargs["password"] is None


def test_values_are_kept_as_raw_bytes(monkeypatch):
    """decode_responses must stay False: values are serialized DataFrames, and
    decoding parquet as UTF-8 fails before read_dataframe ever sees it."""
    monkeypatch.setenv("REDIS_HOST", "redis.invalid")
    assert redis_client().connection_pool.connection_kwargs["decode_responses"] is False


def test_client_is_configured_to_fail_fast_on_a_bad_host(monkeypatch):
    """The reason the retry is spelled out rather than left default.

    redis-py 8 defaults to 3 retries with exponential backoff, so a wrong
    REDIS_HOST would hang a request roughly a minute before erroring — long
    enough to read as "the backend is broken" instead of "the config is wrong".
    """
    monkeypatch.setenv("REDIS_HOST", "redis.invalid")
    kwargs = redis_client().connection_pool.connection_kwargs

    assert kwargs["socket_connect_timeout"] == 5
    assert kwargs["socket_timeout"] == 10
    retry = kwargs["retry"]
    assert retry.get_retries() == 1
    # No public accessor for the backoff; the private attribute is the only
    # window onto the half of the config that decides how long a retry waits.
    assert isinstance(retry._backoff, NoBackoff)


# --------------------------------------------------------------- load_env_file

def test_repo_root_relative_env_file_wins(monkeypatch, tmp_path, fake_package):
    """First candidate is cwd-relative, honoring "run from the repo root"."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "back_dev_home").mkdir()
    (tmp_path / "back_dev_home" / ".env").write_text("REDIS_HOST=from-repo-root\n")
    (fake_package() / ".env").write_text("REDIS_HOST=from-beside-the-package\n")

    load_env_file()
    assert os.environ["REDIS_HOST"] == "from-repo-root"


def test_env_file_beside_the_package_is_the_fallback(
    monkeypatch, tmp_path, fake_package
):
    """The path that works from any cwd — a notebook, a script, `python -m`
    from a subdirectory. Nothing is cwd-relative about it."""
    monkeypatch.chdir(tmp_path)  # no back_dev_home/ here at all
    (fake_package() / ".env").write_text("REDIS_HOST=from-beside-the-package\n")

    load_env_file()
    assert os.environ["REDIS_HOST"] == "from-beside-the-package"


def test_a_value_already_in_the_environment_is_never_overwritten(
    monkeypatch, tmp_path, fake_package
):
    """override=False. Flask, pytest and `SKEWNONO_...=... python -m ...` all
    set config before an adapter imports; .env is the fallback, not the truth."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REDIS_HOST", "set-by-the-caller")
    (fake_package() / ".env").write_text("REDIS_HOST=from-dotenv\n")

    load_env_file()
    assert os.environ["REDIS_HOST"] == "set-by-the-caller"


def test_required_var_decides_whether_to_try_the_second_path(
    monkeypatch, tmp_path, fake_package
):
    """An OpenSearch adapter must not stop at a .env that only proves Redis is
    configured — hence required_var rather than a hardcoded REDIS_HOST probe."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "back_dev_home").mkdir()
    (tmp_path / "back_dev_home" / ".env").write_text("REDIS_HOST=from-repo-root\n")
    (fake_package() / ".env").write_text("OPENSEARCH_HOST=os.invalid\n")

    load_env_file("OPENSEARCH_HOST")
    assert os.environ["OPENSEARCH_HOST"] == "os.invalid"
    assert os.environ["REDIS_HOST"] == "from-repo-root"


def test_no_env_file_anywhere_is_quiet(monkeypatch, tmp_path, fake_package):
    """A home/mock run has no .env at all; loading must not be an error there,
    only the eventual RuntimeError from redis_client if office data is asked
    for."""
    monkeypatch.chdir(tmp_path)
    fake_package()  # directory exists, .env does not

    load_env_file()  # must not raise
    assert "REDIS_HOST" not in os.environ
