"""The mock↔office response-shape guard, exercised without a live Flask.

`scripts/verify/check_contract.py` is the only automated check that the office
providers return the same *shape* the frontend was built against, and
`scripts/verify/capture_fixtures.py` is the only thing that writes the frozen
baselines it compares to. Both are manual CLIs that need a running server, so
until now neither had a single test — the guard itself was unguarded.

Two things are pinned here:

* the pure comparison (`_diff_shape`), which decides what counts as drift, and
* the roster (`ENDPOINTS`), because a feature missing from that list is
  silently exempt from the guard — it reads as "0 problems", not "not checked".

Nothing in this file may write into a real `back_dev_home/**/__fixtures__/`
directory: those JSON files are frozen baselines, and regenerating them from a
mock run would destroy their value as a drift detector. The `fixture_root`
fixture below is therefore **autouse** — remembering to ask for it is not a
safety mechanism, and `capture()`'s default `fetch` would also reach the
network.
"""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path

import pytest

from scripts.verify import capture_fixtures, check_contract

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "back_dev_home"


@pytest.fixture(autouse=True)
def fixture_root(tmp_path, monkeypatch):
    """Move the fixture tree to tmp_path and pin the port — for every test.

    Autouse on purpose: a single `capture(...)` call that forgot to redirect
    would overwrite the frozen baselines *and* dial a real server through the
    default `fetch`. Tests that need to read the real tree use the module-level
    `BACKEND` constant, which this deliberately does not touch.
    """
    monkeypatch.setattr(capture_fixtures, "BACKEND_ROOT", tmp_path)
    monkeypatch.setenv("PORT", "5050")
    return tmp_path


# --------------------------------------------------------------------------
# _diff_shape — 값이 아니라 형태만 본다
# --------------------------------------------------------------------------


def test_identical_shapes_produce_no_issues():
    payload = {"rows": [{"eqp_id": "ECXDX204", "count": 3}], "total": 1}

    assert check_contract._diff_shape(payload, payload) == []


def test_same_shape_with_different_values_passes():
    """The whole point of the tool: mock and office data differ in *values*.
    A comparison that flagged those would be noise on every single endpoint.
    """
    expected = {"rows": [{"eqp_id": "ECXDX204", "count": 3}], "total": 1}
    actual = {"rows": [{"eqp_id": "TP0921", "count": 9999}], "total": 42}

    assert check_contract._diff_shape(expected, actual) == []


def test_missing_top_level_key_fails():
    issues = check_contract._diff_shape({"rows": [], "total": 0}, {"rows": []})

    assert any("$.total" in i and "키 누락" in i for i in issues)


def test_extra_top_level_key_is_reported_too():
    """An office adapter returning *more* than the contract is not harmless
    here — it usually means the adapter answered a different query shape."""
    issues = check_contract._diff_shape({"rows": []}, {"rows": [], "cursor": None})

    assert any("$.cursor" in i for i in issues)


def test_missing_first_row_key_fails():
    expected = {"rows": [{"eqp_id": "A", "fab_name": "M16B"}]}
    actual = {"rows": [{"eqp_id": "A"}]}

    issues = check_contract._diff_shape(expected, actual)

    assert any("$.rows[0].fab_name" in i and "키 누락" in i for i in issues)


def test_changed_value_type_fails():
    expected = {"rows": [{"count": 3}]}
    actual = {"rows": [{"count": "3"}]}

    issues = check_contract._diff_shape(expected, actual)

    assert any("$.rows[0].count" in i and "타입 불일치" in i for i in issues)


def test_int_and_float_are_distinct_types():
    """A real office trap: Redis/OpenSearch numerics arrive as floats where the
    mock had ints. It is flagged, which is deliberate — the frontend formats
    the two differently — but it is the most likely false alarm, so it is
    pinned rather than left to be rediscovered mid-swap."""
    issues = check_contract._diff_shape({"count": 3}, {"count": 3.0})

    assert any("expected=int" in i and "actual=float" in i for i in issues)


def test_bool_is_not_reported_as_int():
    """bool is a subclass of int in Python; the type check must special-case it
    or every True/1 swap would pass silently."""
    assert check_contract._type_name(True) == "bool"
    assert check_contract._diff_shape({"ok": True}, {"ok": 1}) != []


def test_null_in_the_fixture_versus_a_value_fails():
    """Nulls are the most fragile part of a frozen fixture: whichever mock row
    landed first decides whether a nullable column is 'null' or 'str' forever.
    The check has no notion of nullability, so it flags the difference."""
    issues = check_contract._diff_shape({"note": None}, {"note": "실측"})

    assert any("expected=null" in i for i in issues)

    assert check_contract._diff_shape({"note": None}, {"note": None}) == []


def test_nested_dicts_are_compared_recursively():
    expected = {"meta": {"page": {"size": 20}}}
    actual = {"meta": {"page": {"size": "20"}}}

    issues = check_contract._diff_shape(expected, actual)

    assert any("$.meta.page.size" in i for i in issues)


def test_top_level_type_mismatch_short_circuits():
    """Once the container type differs, per-key diffs would be noise — one
    clear line beats twenty derived ones."""
    issues = check_contract._diff_shape({"rows": []}, [])

    assert len(issues) == 1
    assert "expected=dict" in issues[0]


def test_an_empty_expected_array_carries_no_shape_information():
    """A fixture captured while the mock had no rows cannot assert anything
    about row shape — it must not be read as 'rows must be empty'."""
    assert check_contract._diff_shape({"rows": []}, {"rows": [{"a": 1}]}) == []


def test_an_empty_actual_array_is_reported_as_uncomparable():
    """Not silently passing here is what catches an office adapter that
    connects, authenticates and returns zero rows."""
    issues = check_contract._diff_shape({"rows": [{"a": 1}]}, {"rows": []})

    assert any("비어 있어" in i for i in issues)


def test_only_the_first_row_is_compared():
    """Documented limitation, pinned so nobody 'fixes' a heterogeneous-array
    bug report by assuming later rows were ever checked."""
    expected = {"rows": [{"a": 1}, {"a": 1}]}
    actual = {"rows": [{"a": 1}, {"totally": "different"}]}

    assert check_contract._diff_shape(expected, actual) == []


def test_a_bare_top_level_array_is_supported():
    assert check_contract._diff_shape([{"a": 1}], [{"a": 2}]) == []
    assert check_contract._diff_shape([{"a": 1}], [{"b": 2}]) != []


def test_empty_payloads_compare_equal():
    assert check_contract._diff_shape({}, {}) == []
    assert check_contract._diff_shape([], []) == []


# --------------------------------------------------------------------------
# 포트 해석 — :5000 하드코딩이 실제 결함이었다
# --------------------------------------------------------------------------


def test_default_port_is_the_documented_home_port(monkeypatch):
    """Regression: FLASK_BASE was hardcoded to :5000, but the home Flask runs
    on :5050 (index.py's default; 5000 is taken by macOS AirPlay). Both
    scripts therefore failed at home with 'connection refused' on every
    endpoint — the same symptom as a broken office adapter."""
    monkeypatch.delenv("PORT", raising=False)

    assert capture_fixtures.flask_base() == "http://localhost:5050"


def test_port_env_var_retargets_another_flask(monkeypatch):
    """The port must stay switchable by configuration alone — same
    cross-phase principle as NUXT_API_TARGET. It is read per call, not
    frozen at import, so a test (or a shell) can move it."""
    monkeypatch.setenv("PORT", "5000")

    assert capture_fixtures.flask_base() == "http://localhost:5000"


def test_both_scripts_share_one_resolver():
    """check_contract imports the resolver rather than copying it — a second
    copy would drift and compare against a different server than the one the
    fixtures came from."""
    assert check_contract.flask_base is capture_fixtures.flask_base
    assert check_contract.fixture_path is capture_fixtures.fixture_path
    assert check_contract._fetch is capture_fixtures._fetch


def test_fixture_path_is_relocatable(fixture_root):
    """Both scripts read the module global, so the autouse fixture can move
    the whole fixture tree out of the repo — see this file's docstring."""
    assert capture_fixtures.fixture_path("sem_list", "sem-list.json") == (
        fixture_root / "sem_list" / "__fixtures__" / "sem-list.json"
    )
    assert check_contract.fixture_path("sem_list", "sem-list.json").is_relative_to(
        fixture_root
    )


# --------------------------------------------------------------------------
# check_endpoints — 픽스처 누락/응답 실패 오케스트레이션
# --------------------------------------------------------------------------


def _freeze(root: Path, feature: str, name: str, payload: object) -> Path:
    target = root / feature / "__fixtures__" / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def test_matching_response_is_ok(fixture_root):
    _freeze(fixture_root, "sem_list", "sem-list.json", {"rows": [{"eqp_id": "A"}]})
    endpoints = [("sem_list", "sem-list.json", "/api/sem-list")]

    outcomes = list(
        check_contract.check_endpoints(
            endpoints, fetch=lambda url: {"rows": [{"eqp_id": "Z"}]}
        )
    )

    assert [(o.path, o.status) for o in outcomes] == [("/api/sem-list", "ok")]


def test_drifted_response_fails_with_the_offending_path(fixture_root):
    _freeze(fixture_root, "sem_list", "sem-list.json", {"rows": [{"eqp_id": "A"}]})
    endpoints = [("sem_list", "sem-list.json", "/api/sem-list")]

    outcome = next(
        check_contract.check_endpoints(
            endpoints, fetch=lambda url: {"rows": [{"eqpId": "Z"}]}
        )
    )

    assert outcome.status == "fail"
    assert any("eqp_id" in i for i in outcome.issues)


def test_a_missing_fixture_skips_without_calling_the_server(fixture_root):
    """A skip is neither pass nor fail. It used to vanish from the summary
    entirely, so an endpoint whose fixture was never captured looked like a
    clean run."""
    endpoints = [("sem_list", "nope.json", "/api/sem-list")]

    def explode(url):  # pragma: no cover - must not be reached
        raise AssertionError("fetched despite a missing fixture")

    outcomes = list(check_contract.check_endpoints(endpoints, fetch=explode))

    assert outcomes[0].status == "skip"
    assert "nope.json" in outcomes[0].reason


def test_an_unreachable_server_fails_that_endpoint_only(fixture_root):
    _freeze(fixture_root, "sem_list", "a.json", {"rows": [{"x": 1}]})
    _freeze(fixture_root, "afm", "b.json", {"rows": [{"x": 1}]})
    endpoints = [
        ("sem_list", "a.json", "/api/a"),
        ("afm", "b.json", "/api/b"),
    ]

    def flaky(url):
        if url.endswith("/api/a"):
            raise urllib.error.URLError("connection refused")
        return {"rows": [{"x": 2}]}

    outcomes = list(check_contract.check_endpoints(endpoints, fetch=flaky))

    assert [o.status for o in outcomes] == ["fail", "ok"]
    assert "응답 실패" in outcomes[0].reason


def test_an_http_error_response_fails_rather_than_crashing(fixture_root):
    """HTTPError subclasses URLError, so a 500 from one office adapter must
    not abort the remaining endpoints."""
    _freeze(fixture_root, "sem_list", "a.json", {"rows": [{"x": 1}]})
    endpoints = [("sem_list", "a.json", "/api/a")]

    def boom(url):
        raise urllib.error.HTTPError(url, 500, "Server Error", hdrs=None, fp=None)

    assert next(check_contract.check_endpoints(endpoints, fetch=boom)).status == "fail"


def test_the_request_url_uses_the_resolved_base(fixture_root, monkeypatch):
    monkeypatch.setenv("PORT", "5114")
    _freeze(fixture_root, "sem_list", "a.json", {"rows": [{"x": 1}]})
    seen: list[str] = []

    def record(url):
        seen.append(url)
        return {"rows": [{"x": 1}]}

    list(
        check_contract.check_endpoints(
            [("sem_list", "a.json", "/api/a")], fetch=record
        )
    )

    assert seen == ["http://localhost:5114/api/a"]


# --------------------------------------------------------------------------
# capture — 픽스처를 실제로 덮어쓰는 유일한 경로
# --------------------------------------------------------------------------


def test_capture_writes_one_fixture_per_endpoint(fixture_root):
    failures = capture_fixtures.capture(
        [("ebeam/storage", "storage-cdsem.json", "/api/cdsem/storage")],
        fetch=lambda url: {"rows": [{"ppid": "P1"}]},
    )

    written = fixture_root / "ebeam/storage/__fixtures__/storage-cdsem.json"
    assert failures == []
    assert json.loads(written.read_text(encoding="utf-8")) == {"rows": [{"ppid": "P1"}]}


def test_capture_keeps_korean_readable_and_indented(fixture_root):
    """Fixtures are read by humans and pasted into office LLM prompts;
    \\uXXXX escapes or a single long line defeat both uses."""
    capture_fixtures.capture(
        [("sem_list", "sem-list.json", "/api/sem-list")],
        fetch=lambda url: {"rows": [{"note": "실측"}]},
    )

    text = (fixture_root / "sem_list/__fixtures__/sem-list.json").read_text(
        encoding="utf-8"
    )
    assert "실측" in text
    assert "\n  " in text


def test_capture_truncates_long_arrays(fixture_root):
    """30 rows is the cap; the frontend sees thousands but a fixture only
    needs to carry shape."""
    capture_fixtures.capture(
        [("sem_list", "sem-list.json", "/api/sem-list")],
        fetch=lambda url: {"rows": [{"i": i} for i in range(120)]},
    )

    payload = json.loads(
        (fixture_root / "sem_list/__fixtures__/sem-list.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(payload["rows"]) == 30


def test_capture_truncates_a_bare_top_level_array(fixture_root):
    capture_fixtures.capture(
        [("sem_list", "sem-list.json", "/api/sem-list")],
        fetch=lambda url: [{"i": i} for i in range(120)],
    )

    payload = json.loads(
        (fixture_root / "sem_list/__fixtures__/sem-list.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(payload) == 30


def test_capture_leaves_nothing_behind_for_a_failed_endpoint(fixture_root):
    """Half-written fixtures are worse than none: the next check_contract run
    would compare against whatever the failing server last managed to emit.
    Not even the directory is created, so a typo'd feature_dir cannot litter
    the tree with empty __fixtures__/ folders."""
    def refused(url):
        raise urllib.error.URLError("connection refused")

    failures = capture_fixtures.capture(
        [("sem_list", "sem-list.json", "/api/sem-list")], fetch=refused
    )

    assert failures == ["/api/sem-list"]
    assert not (fixture_root / "sem_list").exists()


def _snapshot(root: Path) -> dict[str, tuple[int, int]]:
    return {
        str(p.relative_to(root)): (p.stat().st_size, p.stat().st_mtime_ns)
        for p in sorted(root.rglob("__fixtures__/*.json"))
    }


def test_capturing_does_not_touch_the_frozen_baselines():
    """The invariant this whole module is built around, asserted against the
    real tree rather than tmp_path: run the writer over the *real* ENDPOINTS
    roster and every committed fixture must be byte-for-byte untouched.
    Without the autouse redirection this test fails — which is the point."""
    before = _snapshot(BACKEND)
    assert before, "no frozen fixtures found — the guard would be vacuous"

    capture_fixtures.capture(
        capture_fixtures.ENDPOINTS, fetch=lambda url: {"rows": [{"x": 1}]}
    )

    assert _snapshot(BACKEND) == before


# --------------------------------------------------------------------------
# main() — 두 CLI 의 종료 코드와 요약 줄
# --------------------------------------------------------------------------


def test_main_exits_zero_and_prints_ok_when_shapes_match(
    fixture_root, monkeypatch, capsys
):
    _freeze(fixture_root, "sem_list", "a.json", {"rows": [{"x": 1}]})
    monkeypatch.setattr(check_contract, "ENDPOINTS", [("sem_list", "a.json", "/api/a")])
    monkeypatch.setattr(check_contract, "_fetch", lambda url: {"rows": [{"x": 2}]})

    assert check_contract.main() == 0

    out = capsys.readouterr().out
    assert "[ OK ] /api/a" in out
    assert "1 / 1 통과" in out


def test_main_exits_nonzero_when_a_shape_drifts(fixture_root, monkeypatch, capsys):
    """The exit code is what a human (or a future CI job with a live server)
    actually reads — a report-only run would make the guard decorative."""
    _freeze(fixture_root, "sem_list", "a.json", {"rows": [{"x": 1}]})
    monkeypatch.setattr(check_contract, "ENDPOINTS", [("sem_list", "a.json", "/api/a")])
    monkeypatch.setattr(check_contract, "_fetch", lambda url: {"rows": [{"y": 1}]})

    assert check_contract.main() == 1

    out = capsys.readouterr().out
    assert "[FAIL] /api/a" in out
    assert "0 / 1 통과" in out


def test_main_counts_skips_separately_from_passes(fixture_root, monkeypatch, capsys):
    """Regression: a skipped endpoint used to vanish from the summary, so
    '1 / 1 통과' could mean 'one checked, one never looked at'."""
    _freeze(fixture_root, "sem_list", "a.json", {"rows": [{"x": 1}]})
    monkeypatch.setattr(
        check_contract,
        "ENDPOINTS",
        [("sem_list", "a.json", "/api/a"), ("afm", "missing.json", "/api/b")],
    )
    monkeypatch.setattr(check_contract, "_fetch", lambda url: {"rows": [{"x": 1}]})

    assert check_contract.main() == 0

    out = capsys.readouterr().out
    assert "[SKIP] /api/b" in out
    assert "1 / 1 통과 (1 개 건너뜀)" in out


def test_capture_main_exits_nonzero_when_an_endpoint_fails(
    fixture_root, monkeypatch, capsys
):
    def refused(url):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(
        capture_fixtures, "ENDPOINTS", [("sem_list", "a.json", "/api/a")]
    )
    monkeypatch.setattr(capture_fixtures, "_fetch", refused)

    assert capture_fixtures.main() == 1
    assert "5050" in capsys.readouterr().err


def test_capture_main_exits_zero_after_writing_every_fixture(
    fixture_root, monkeypatch, capsys
):
    monkeypatch.setattr(
        capture_fixtures, "ENDPOINTS", [("sem_list", "a.json", "/api/a")]
    )
    monkeypatch.setattr(capture_fixtures, "_fetch", lambda url: {"rows": []})

    assert capture_fixtures.main() == 0
    assert (fixture_root / "sem_list/__fixtures__/a.json").is_file()


# --------------------------------------------------------------------------
# ENDPOINTS 로스터 — 목록에 없는 피처는 검증에서 조용히 빠진다
# --------------------------------------------------------------------------


def test_every_listed_feature_directory_exists():
    """A typo in feature_dir writes the fixture to a brand-new directory and
    check_contract then reports SKIP forever — never a failure."""
    missing = sorted(
        {f for f, _n, _p in capture_fixtures.ENDPOINTS if not (BACKEND / f).is_dir()}
    )

    assert missing == []


def test_every_listed_endpoint_has_a_captured_fixture():
    """Without the fixture the endpoint is skipped, not checked."""
    missing = [
        f"{feature}/{name}"
        for feature, name, _path in capture_fixtures.ENDPOINTS
        if not (BACKEND / feature / "__fixtures__" / name).is_file()
    ]

    assert missing == []


def test_no_two_endpoints_share_a_fixture_file():
    """Two entries with the same (feature, name) would silently overwrite each
    other, and check_contract would compare one endpoint against the other's
    response shape."""
    pairs = [(f, n) for f, n, _p in capture_fixtures.ENDPOINTS]

    assert len(pairs) == len(set(pairs))


def test_no_two_endpoints_share_an_api_path():
    paths = [p for _f, _n, p in capture_fixtures.ENDPOINTS]

    assert len(paths) == len(set(paths))


# Individual files that are NOT captured HTTP-endpoint snapshots, so their
# absence from ENDPOINTS does not mean a feature slipped past the shape
# guard unnoticed -- there is no endpoint to capture in the first place.
# Keyed on the FILE, not its parent __fixtures__ dir: a directory-level
# exemption would silently cover a future real endpoint snapshot dropped
# into the same folder, which is exactly the blind spot this guard exists
# to catch.
#
# `back_dev_home/ebeam/__fixtures__/tool_type_cases.json` is a hand-written
# contract consumed directly by `back_dev_home/ebeam/tests/
# test_tool_type_parity.py` and `front-dev-home/app/utils/
# toolTypeParity.test.ts` (pytest and node --test reading the same JSON), not
# a mock-server response. Add to this set only for the same reason: a file
# with nothing `capture_fixtures.py` could ever have produced.
NON_ENDPOINT_FIXTURE_FILES: frozenset[Path] = frozenset({
    BACKEND / "ebeam" / "__fixtures__" / "tool_type_cases.json",
})


def test_no_feature_with_fixtures_is_exempt_from_the_shape_guard():
    """A feature with frozen fixtures but no ENDPOINTS entry is invisible to
    check_contract — it looks covered and is not.

    pm_planning and skew were exactly that until their endpoints were added;
    both need a required fab_name, which is why they were easy to skip. If this
    fails, add the endpoint to ENDPOINTS rather than relaxing the assertion
    -- unless the new fixture file isn't an endpoint snapshot at all, in
    which case it belongs in NON_ENDPOINT_FIXTURE_FILES above, not here.
    """
    listed = {feature for feature, _n, _p in capture_fixtures.ENDPOINTS}
    with_fixtures = {
        str(d.parent.relative_to(BACKEND))
        for d in BACKEND.rglob("__fixtures__")
        # rglob, not iterdir: a feature may nest its fixtures in a
        # subdirectory (e.g. chat/__fixtures__/knowledge/*.json) with
        # nothing directly under __fixtures__/ itself. iterdir() alone made
        # such a feature invisible to this guard entirely.
        if any(
            f for f in d.rglob("*.json") if f not in NON_ENDPOINT_FIXTURE_FILES
        )
    }

    assert sorted(with_fixtures - listed) == []


def test_every_listed_api_path_starts_at_the_api_prefix():
    """The base URL carries no path, so a missing /api would hit the SPA
    catch-all and compare against an HTML error page."""
    assert all(p.startswith("/api/") for _f, _n, p in capture_fixtures.ENDPOINTS)
