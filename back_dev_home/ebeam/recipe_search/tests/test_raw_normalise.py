"""``_to_rows`` must survive whatever container the office reader returns.

The only part of the office raw-folder adapter testable from home — and the part
most likely to be wrong, because the readers' return CONTAINER is OFFICE-VERIFY,
not merely their field names. A wrong guess here must degrade to oddly-ordered
rows, never to a 500 on a screen that used to work.
"""

import pandas as pd
import pytest

from back_dev_home.ebeam.recipe_search import rawfiles
from back_dev_home.ebeam.recipe_search.providers import office_example as office


def test_a_dict_becomes_rows_in_insertion_order():
    """Order is the reader's own — nothing sorts or renames."""
    assert office._to_rows({"B": 2, "A": "x"}) == [
        {"key": "B", "value": "2"},
        {"key": "A", "value": "x"},
    ]


def test_a_dict_of_dicts_becomes_rows_tagged_with_their_group():
    """ENMP (read_af_pr_condition) returns eight NESTED groups
    (office 확인 2026-07-30). Before this, str() flattened each inner dict into
    one unreadable "{'a': 1}" cell."""
    parsed = {
        "sequence_measurement": {"Mode": "Auto"},
        "measurement_focusing": {"Mode": "Off", "Retry": 2},
    }

    assert office._to_rows(parsed) == [
        {"key": "Mode", "value": "Auto", "section": "sequence_measurement"},
        {"key": "Mode", "value": "Off", "section": "measurement_focusing"},
        {"key": "Retry", "value": "2", "section": "measurement_focusing"},
    ]


def test_two_groups_sharing_an_inner_key_stay_separate_rows():
    """Addressing pass 1 and pass 2 are the same settings twice, so they carry
    identical inner keys. Collapsing them would show pass 1's value twice."""
    rows = office._to_rows({
        "addressing_auto_focus1": {"Acceptance": "200"},
        "addressing_auto_focus2": {"Acceptance": "150"},
    })

    assert [row["value"] for row in rows] == ["200", "150"]
    assert len({row["section"] for row in rows}) == 2


def test_a_flat_pair_beside_grouped_ones_keeps_its_own_row():
    """Tolerated rather than rejected: dropping it would hide a setting the
    office does send, and no shape here has been seen twice yet."""
    rows = office._to_rows({"Version": "3", "measurement_focusing": {"Mode": "Off"}})

    assert rows[0] == {"key": "Version", "value": "3"}
    assert rows[1]["section"] == "measurement_focusing"


def test_a_flat_dict_gains_no_section():
    """The four flat readers must be untouched — that is what keeps their
    tables rendering byte-identically to before."""
    assert all("section" not in row for row in office._to_rows({"A": 1, "B": 2}))


def test_a_single_row_dataframe_becomes_column_rows():
    frame = pd.DataFrame([{"Mag": "50.0K", "Vacc": 800}])
    assert office._to_rows(frame) == [
        {"key": "Mag", "value": "50.0K"},
        {"key": "Vacc", "value": "800"},
    ]


def test_a_wide_single_row_dataframe_keeps_every_column():
    frame = pd.DataFrame([{f"F{i}": i for i in range(8)}])
    assert len(office._to_rows(frame)) == 8


def test_a_two_column_dataframe_is_read_as_key_value_pairs():
    frame = pd.DataFrame({"item": ["Mag", "Vacc"], "value": ["50.0K", 800]})
    assert office._to_rows(frame) == [
        {"key": "Mag", "value": "50.0K"},
        {"key": "Vacc", "value": "800"},
    ]


def test_a_one_by_two_frame_is_read_as_columns_not_as_one_pair():
    """The one genuinely ambiguous shape: 1x2 satisfies both readings and they
    disagree. Columns win — a settings file holding a single setting is rarer
    than one holding two. Documented as OFFICE-VERIFY; flip the branch in
    _to_rows if the office turns out to emit 1x2 pair frames."""
    frame = pd.DataFrame([{"Mag": "50.0K", "Vacc": "800"}])
    rows = office._to_rows(frame)
    assert rows == [
        {"key": "Mag", "value": "50.0K"},
        {"key": "Vacc", "value": "800"},
    ]
    assert rows != [{"key": "50.0K", "value": "800"}]


def test_a_list_of_pairs_becomes_rows():
    assert office._to_rows([("Mag", "50.0K"), ["Vacc", 800]]) == [
        {"key": "Mag", "value": "50.0K"},
        {"key": "Vacc", "value": "800"},
    ]


def test_none_and_empty_become_no_rows():
    assert office._to_rows(None) == []
    assert office._to_rows({}) == []
    assert office._to_rows([]) == []
    assert office._to_rows(pd.DataFrame()) == []


def test_an_unrecognised_container_is_empty_rather_than_an_exception():
    assert office._to_rows(42) == []


def test_every_value_is_stringified_for_json_safety():
    """numpy scalars are not JSON-serialisable; str() is what makes them so."""
    frame = pd.DataFrame([{"Frame": 8, "WD": 5.5, "On": True}])
    assert all(
        isinstance(row["value"], str) for row in office._to_rows(frame)
    )


# ── _read_block ───────────────────────────────────────────────────────────


def test_read_block_returns_none_when_the_file_is_absent():
    """Absent is normal, not an error: a parameter may simply lack the file."""
    assert office._read_block("PRMS0001", None, lambda _: {"a": 1}) is None
    assert office._read_block(None, b"data", lambda _: {"a": 1}) is None


def test_read_block_returns_none_when_the_reader_raises():
    """One malformed file must not take the whole parameter down with it."""
    def _explode(_payload):
        raise ValueError("not a recognised amp file")

    assert office._read_block("PRMS0001", b"junk", _explode) is None


def test_read_block_names_the_file_it_parsed():
    block = office._read_block("PRMS0001", b"x", lambda _: {"Mag": "50K"})
    assert block == {
        "source": "PRMS0001",
        "rows": [{"key": "Mag", "value": "50K"}],
    }


# ── slot planning (now shared with the mock, in rawfiles) ─────────────────


def test_slot_sources_matches_the_naming_rules():
    amp, af_pr, images = rawfiles.slot_sources({
        "img_add1": "IMMP0001",
        "img_add2": "PRMP0001",
        "image_add3": "I2MP0001",
        "img_meas1": "IMMS0001",
        "img_meas2": "PRMS0001",
    })
    assert amp == "PRMS0001"
    assert af_pr == "ENMP0001"
    assert images == [
        ("img_add1", "IMMP0001.jpeg", ".IMMP0001.jpeg/cond.txt"),
        ("image_add3", "I2MP0001.jpeg", ".I2MP0001.jpeg/cond.txt"),
        ("img_meas1", "IMMS0001.jpeg", ".IMMS0001.jpeg/cond.txt"),
    ]


def test_slot_sources_drops_the_empty_sentinel():
    amp, af_pr, images = rawfiles.slot_sources({
        "img_add1": "non", "img_add2": "non", "img_meas2": "non",
    })
    assert amp is None
    assert af_pr is None
    assert images == []


def test_fetch_raw_with_no_names_opens_no_session():
    """Guards the empty-slot case from costing an FTP connection."""
    assert office._fetch_raw(
        {"eqp_ip": "10.1.2.3", "class_name": "C", "idw": "W", "idp": "P"}, []
    ) == {}


def test_both_providers_plan_a_parameter_identically():
    """Provider parity by construction, not by discipline.

    mock and office used to each walk the slots themselves; they now share
    rawfiles.slot_sources, and this pins that they still agree on the one thing
    the contract tests cannot see — WHICH FILE each slot names. Since
    2026-08-08 the plan starts from a raw-folder listing (the office lists over
    FTP, the mock synthesizes one), so parity means: the mock's response equals
    slot_sources fed the same listing the mock synthesized.
    """
    from back_dev_home.ebeam.recipe_search.providers import mock

    slots = {
        "img_add1": "IMMP0001", "img_add2": "PRMP0001", "image_add3": "non",
        "img_meas1": "IMMS0001", "img_meas2": "PRMS0001",
    }
    locator = {"eqp_ip": "10.1.2.3", "class_name": "C", "idw": "W", "idp": "P"}
    item = {"locator": locator, "parameter": "Para_1", "slots": slots}

    mocked = mock.get_param_detail([item])[0]
    amp, af_pr, images = rawfiles.slot_sources(
        slots, listing=mock._mock_raw_listing(locator, slots)
    )

    assert mocked["amp"]["source"] == amp
    assert mocked["af_pr"]["source"] == af_pr
    assert [(i["slot"], i["name"]) for i in mocked["images"]] == [
        (slot, name) for slot, name, _ in images
    ]


# ── _fetch_many ───────────────────────────────────────────────────────────
#
# The batched FTP fan-out is office-only, but its RESULT MATCHING is pure
# bookkeeping and is where a fleet call goes wrong silently: bytes landing under
# the wrong recipe read as real settings. A fake downloader makes it testable
# here instead of only at the office.


class _FakeResult:
    def __init__(self, host, remote_path, data):
        self.host, self.remote_path, self.data = host, remote_path, data


class _FakeFailure:
    """Mirrors ftp_handler's HostFailure: ``remote_path`` is None when the
    failure happened before any specific file (connect / login / listing)."""

    def __init__(self, remote_path, error="550", host="10.0.0.1"):
        self.remote_path, self.error, self.host = remote_path, error, host


class _FakeReport:
    def __init__(self, files, failures=()):
        self.files, self.failures = files, list(failures)

    def grouped(self):
        out = {}
        for f in self.files:
            out.setdefault(f.host, {})[f.remote_path] = f.data
        return out


class _FakeDownloader:
    """Serves `available`; records the specs it was handed."""

    def __init__(self, available):
        self.available = available
        self.calls = []

    host_down = False

    def download(self, specs):
        self.calls.append(specs)
        if self.host_down:
            # remote_path=None — the library's marker for connect/login failure.
            return _FakeReport([], [
                _FakeFailure(None, "ConnectionRefusedError", spec.host)
                for spec in specs
            ])
        files = [
            _FakeResult(spec.host, path, self.available[(spec.host, path)])
            for spec in specs
            for path in spec.files
            if (spec.host, path) in self.available
        ]
        missing = [
            _FakeFailure(path, host=spec.host) for spec in specs for path in spec.files
            if (spec.host, path) not in self.available
        ]
        return _FakeReport(files, missing)


class _FakeSpec:
    def __init__(self, host, files=(), listings=()):
        self.host, self.files, self.listings = host, list(files), list(listings)


class _FakeListDir:
    def __init__(self, remote_dir, pattern=None):
        self.remote_dir, self.pattern = remote_dir, pattern


def _patch_ftp(monkeypatch, available):
    downloader = _FakeDownloader(available)
    monkeypatch.setattr(
        office, "_transport",
        lambda: office._Transport(object, _FakeSpec, _FakeListDir, "fake")
    )
    monkeypatch.setattr(office, "_downloader", lambda _cls, _cfg: downloader)
    return downloader


A = ("10.0.0.1", "CLS", "IDW_A", "IDP_A")
B = ("10.0.0.2", "CLS", "IDW_B", "IDP_B")


def _path(key, name):
    return rawfiles.remote_path(rawfiles.raw_dir(key[1], key[2], key[3]), name)


def test_fetch_many_issues_exactly_one_download_for_many_hosts(monkeypatch):
    """The whole point of the batch: N tools must be one fleet call, not N."""
    downloader = _patch_ftp(monkeypatch, {
        (A[0], _path(A, "PRMS0001")): b"a",
        (B[0], _path(B, "PRMS0002")): b"b",
    })
    out = office._fetch_many({A: ["PRMS0001"], B: ["PRMS0002"]})

    assert len(downloader.calls) == 1
    assert {spec.host for spec in downloader.calls[0]} == {A[0], B[0]}
    assert out[A] == {"PRMS0001": b"a"}
    assert out[B] == {"PRMS0002": b"b"}


def test_fetch_many_does_not_cross_wire_the_same_path_on_two_hosts(monkeypatch):
    """Two tools can hold the same recipe at the same path. Matching on path
    alone would give one recipe the other's settings — silently plausible."""
    same = ("10.0.0.1", "CLS", "IDW_X", "IDP_X")
    other = ("10.0.0.2", "CLS", "IDW_X", "IDP_X")
    _patch_ftp(monkeypatch, {
        (same[0], _path(same, "PRMS0001")): b"from-host-1",
        (other[0], _path(other, "PRMS0001")): b"from-host-2",
    })
    out = office._fetch_many({same: ["PRMS0001"], other: ["PRMS0001"]})

    assert out[same] == {"PRMS0001": b"from-host-1"}
    assert out[other] == {"PRMS0001": b"from-host-2"}


def test_fetch_many_omits_missing_files_without_raising(monkeypatch):
    """A missing file is normal — it must be absent, not an exception."""
    _patch_ftp(monkeypatch, {(A[0], _path(A, "PRMS0001")): b"a"})
    out = office._fetch_many({A: ["PRMS0001", "ENMP0001"]})

    assert out[A] == {"PRMS0001": b"a"}
    assert "ENMP0001" not in out[A]


def test_fetch_many_returns_an_entry_for_every_locator_asked_for(monkeypatch):
    """Every requested file being absent is NOT an outage.

    A parameter can legitimately ask only for a cond.txt that does not exist.
    The host answered — it just had nothing — so this must be an empty entry on
    a 200, never a 502.
    """
    _patch_ftp(monkeypatch, {})
    out = office._fetch_many({A: ["PRMS0001"], B: ["PRMS0002"]})
    assert out == {A: {}, B: {}}


def test_fetch_many_raises_when_the_host_itself_is_unreachable(monkeypatch):
    """The 502 the spec promises. HostFailure.remote_path is None when the
    failure happened before any specific file — connect, login or listing —
    which is the only reliable "tool is down" signal in the report."""
    from back_dev_home.msr_image.errors import SourceUnavailable

    downloader = _patch_ftp(monkeypatch, {})
    downloader.host_down = True
    with pytest.raises(SourceUnavailable):
        office._fetch_many({A: ["PRMS0001"]})


def test_fetch_many_skips_locators_with_no_names(monkeypatch):
    downloader = _patch_ftp(monkeypatch, {})
    assert office._fetch_many({A: []}) == {}
    assert downloader.calls == []


def test_fetch_many_deduplicates_a_repeated_name(monkeypatch):
    downloader = _patch_ftp(monkeypatch, {(A[0], _path(A, "PRMS0001")): b"a"})
    office._fetch_many({A: ["PRMS0001", "PRMS0001"]})
    assert downloader.calls[0][0].files == [_path(A, "PRMS0001")]


def test_fetch_raw_is_the_single_locator_case(monkeypatch):
    _patch_ftp(monkeypatch, {(A[0], _path(A, "PRMS0001")): b"a"})
    locator = {"eqp_ip": A[0], "class_name": A[1], "idw": A[2], "idp": A[3]}
    assert office._fetch_raw(locator, ["PRMS0001"]) == {"PRMS0001": b"a"}


# ── _list_raw_dirs ────────────────────────────────────────────────────────
#
# The discovery step HV-SEM requires (2026-08-08). Like _fetch_many, the FTP
# part is office-only but the RESULT ATTRIBUTION is pure bookkeeping — and a
# path attributed to the wrong locator reads as another recipe's images.


class _FakeHostListing:
    def __init__(self, host, paths):
        self.host, self.paths = host, paths


class _FakeListingReport:
    def __init__(self, listings, failures=()):
        self.listings, self.failures = listings, list(failures)

    def grouped(self):
        return {hl.host: hl.paths for hl in self.listings}


def _patch_listing(monkeypatch, listings, failures=()):
    downloader = _FakeDownloader({})
    downloader.listing_report = _FakeListingReport(
        [_FakeHostListing(h, p) for h, p in listings.items()], failures
    )
    downloader.list_dirs = lambda specs: downloader.listing_report
    monkeypatch.setattr(
        office, "_transport",
        lambda: office._Transport(object, _FakeSpec, _FakeListDir, "fake")
    )
    monkeypatch.setattr(office, "_downloader", lambda _cls, _cfg: downloader)
    return downloader


def test_list_raw_dirs_attributes_basenames_to_the_right_locator(monkeypatch):
    """Full NLST paths come back per HOST; each locator gets only its own
    folder's basenames, and the hidden .{name}/cond.txt sidecar entries (one
    level down) stay out of the image plan."""
    same_host_c = (A[0], "CLS", "IDW_C", "IDP_C")
    _patch_listing(monkeypatch, {
        A[0]: [
            _path(A, "IMMS0001-U.jpeg"),
            _path(A, "IMMS0001-L.jpeg"),
            _path(same_host_c, "IMMS0009.jpeg"),
            _path(A, ".IMMS0001-U.jpeg/cond.txt"),
        ],
        B[0]: [_path(B, "IMMS0002.jpeg")],
    })
    out = office._list_raw_dirs({A, B, same_host_c})

    assert out[A] == ["IMMS0001-U.jpeg", "IMMS0001-L.jpeg"]
    assert out[same_host_c] == ["IMMS0009.jpeg"]
    assert out[B] == ["IMMS0002.jpeg"]


def test_list_raw_dirs_marks_a_failed_host_unlisted_not_empty(monkeypatch):
    """None (fall back to derived names) is not the same as [] (listed, no
    match): a dead listing must not erase the derived-name plan."""
    _patch_listing(
        monkeypatch,
        {A[0]: [_path(A, "IMMS0001.jpeg")]},
        failures=[_FakeFailure(None, "ConnectionRefusedError", host=B[0])],
    )
    out = office._list_raw_dirs({A, B})
    assert out[A] == ["IMMS0001.jpeg"]
    assert out[B] is None


def test_list_raw_dirs_degrades_to_none_when_the_call_itself_raises(monkeypatch):
    downloader = _patch_listing(monkeypatch, {})
    def _boom(_specs):
        raise RuntimeError("proxy down")
    downloader.list_dirs = _boom
    assert office._list_raw_dirs({A, B}) == {A: None, B: None}
