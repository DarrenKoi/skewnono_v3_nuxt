"""The MSR artifact download — mock adapter, office adapter, and the route.

What is actually at risk here, and therefore what these tests pin:

1. The three outcomes must stay TELLABLE APART (404 unknown / 404 no path /
   410 expired). Retention deletes pickles at 61 days as a matter of routine,
   so "gone" is a normal answer; if it ever collapses into 404 the frontend
   loses the only way it can say 보존 기간 instead of 없는 측정.
2. The home pickle must carry the OFFICE column spelling. Nothing else checks
   this — the JSON endpoint reads normalized keys, so a drift here would only
   surface as a KeyError in someone's script at the office.
3. The office adapter must read the stored path as a KEY, not split it into
   bucket/key. That mistake produced a real InvalidBucketName once already.

Run from repo root:  .venv/bin/python -m pytest back_dev_home/msr_file
"""

import pickle

import pytest

from back_dev_home.msr_file.contracts import MsrArtifactError
from back_dev_home.msr_file.providers import mock


# A hand-seeded meas_hist row, so the parent lookup resolves (providers/mock.py).
_MSR = "20260509_ADI_CD_BIAS_001_6LD257421_ECXDX925"


# ── mock adapter ───────────────────────────────────────────────────────────


def test_raw_is_utf8_text_naming_the_measurement():
    artifact = mock.get_msr_artifact(_MSR, "raw")

    assert artifact["kind"] == "raw"
    assert artifact["filename"] == f"{_MSR}.MSR"
    assert artifact["content_type"] == "text/plain; charset=utf-8"
    text = artifact["data"].decode("utf-8")
    assert f"MSR\t{_MSR}" in text
    # The stand-in must announce itself. A file that looked like a tool export
    # would eventually be mistaken for one.
    assert "OFFICE-VERIFY" in text


def test_pkl_unpickles_to_the_office_document_shape():
    artifact = mock.get_msr_artifact(_MSR, "pkl")

    assert artifact["content_type"] == "application/octet-stream"
    document = pickle.loads(artifact["data"])
    assert set(document) == {
        "df_result_data",
        "exe_detail_info",
        "alignment",
        "spm_dict",
        "fixed_fdc",
        "dynamic_fdc",
    }


def test_pkl_columns_use_the_office_spelling_not_the_contract_spelling():
    """The renames in office_example._records must round-trip back out.

    A home-written parser keyed on "meas_condition_mag" would KeyError at the
    office, where the column is "meas_condition mag" — and nothing else in the
    suite would have caught it.
    """
    document = pickle.loads(mock.get_msr_artifact(_MSR, "pkl")["data"])
    columns = set(document["df_result_data"].columns)

    assert {"meas_condition mag", "meas_condition vac", "meas_condition pixel",
            "mp_image_name 01", "object"} <= columns
    assert not {"meas_condition_mag", "object_type"} & columns
    # mp_image_names is assembled by the contract from the numbered columns;
    # shipping it back would invent a column the pickle does not have.
    assert "mp_image_names" not in columns


def test_multi_image_rows_expand_into_numbered_columns():
    document = pickle.loads(mock.get_msr_artifact(_MSR, "pkl")["data"])
    records = document["df_result_data"].to_dict(orient="records")

    payload = mock.get_msr_file(_MSR)
    widest = max(payload["rows"], key=lambda row: len(row["mp_image_names"]))
    match = next(r for r in records if r["sequence"] == widest["sequence"])

    for index, name in enumerate(widest["mp_image_names"], start=1):
        assert match[f"mp_image_name {index:02d}"] == name


def test_unknown_kind_is_a_400_not_a_404():
    with pytest.raises(MsrArtifactError) as caught:
        mock.get_msr_artifact(_MSR, "xlsx")
    assert caught.value.status == 400


def test_unknown_msr_is_404():
    with pytest.raises(MsrArtifactError) as caught:
        mock.get_msr_artifact("", "raw")
    assert caught.value.status == 404


# ── route ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def client():
    from back_dev_home import create_app

    app = create_app()
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        test_client.set_cookie("LASTUSER", "local-dev")
        yield test_client


def test_route_serves_an_attachment_with_the_stores_filename(client):
    response = client.get(f"/api/msr-file/download?msr={_MSR}&kind=raw")

    assert response.status_code == 200
    disposition = response.headers["Content-Disposition"]
    assert disposition.startswith("attachment;")
    assert f"{_MSR}.MSR" in disposition
    # Non-ASCII office filenames need the RFC 5987 form alongside the plain one.
    assert "filename*=UTF-8''" in disposition
    assert response.data


def test_route_does_not_double_the_charset(client):
    """Flask adds a charset to any text/* mimetype; the adapter already set one.

    The duplicate is cosmetic here but the same mechanism would stamp UTF-8
    onto the office's charset-less text/plain, which is precisely the claim we
    must not make about an unverified .MSR encoding.
    """
    response = client.get(f"/api/msr-file/download?msr={_MSR}&kind=raw")
    assert response.headers["Content-Type"] == "text/plain; charset=utf-8"


def test_route_requires_both_params(client):
    assert client.get("/api/msr-file/download?kind=raw").status_code == 400
    assert client.get(f"/api/msr-file/download?msr={_MSR}").status_code == 400


def test_route_reports_an_unknown_kind_as_400(client):
    response = client.get(f"/api/msr-file/download?msr={_MSR}&kind=zip")
    assert response.status_code == 400


def test_route_is_not_cached(client):
    """Originals are immutable but deletable, so a cached copy outlives the file."""
    response = client.get(f"/api/msr-file/download?msr={_MSR}&kind=pkl")
    assert response.headers["Cache-Control"] == "no-cache"


# ── office adapter ─────────────────────────────────────────────────────────


@pytest.fixture()
def office(monkeypatch):
    """Import office_example under its adapter name so the module runs at home.

    Without this the file is only ever type-checked, never executed — see
    docs on importorskip hiding broken office tests.
    """
    from back_dev_home.msr_file.providers import office_example

    return office_example


class _FakeStore:
    def __init__(self, objects, error=None):
        self.objects = objects
        self.error = error
        self.asked = []

    def get(self, key):
        self.asked.append(key)
        if self.error is not None:
            raise self.error
        return self.objects[key]


class _S3Gone(Exception):
    code = "NoSuchKey"


def _install(monkeypatch, office, parent, store):
    monkeypatch.setattr(office, "_find_parent", lambda msr: parent)
    monkeypatch.setitem(
        __import__("sys").modules,
        "minio_handler",
        type("_M", (), {"MinioObject": lambda *a, **k: store}),
    )


def test_office_reads_the_stored_path_as_a_key_not_a_bucket_pair(monkeypatch, office):
    store = _FakeStore({"hitachi_sem/cdsem/raw_msr/2026/09/02/A.MSR": b"raw bytes"})
    _install(monkeypatch, office, {"minio_msr": "/hitachi_sem/cdsem/raw_msr/2026/09/02/A.MSR"}, store)

    artifact = office.get_msr_artifact(_MSR, "raw")

    # The leading segment is a FOLDER. Splitting it off as a bucket is the
    # InvalidBucketName mistake _fetch_payload documents.
    assert store.asked == ["hitachi_sem/cdsem/raw_msr/2026/09/02/A.MSR"]
    assert artifact["data"] == b"raw bytes"
    assert artifact["filename"] == "A.MSR"
    # No charset — the .MSR encoding is unverified.
    assert artifact["content_type"] == "text/plain"


def test_office_picks_the_field_matching_the_kind(monkeypatch, office):
    store = _FakeStore({"p/dict_pkl/B.pkl": b"pickled"})
    _install(monkeypatch, office, {
        "minio_msr": "p/raw_msr/B.MSR",
        "minio_pkl": "p/dict_pkl/B.pkl",
    }, store)

    assert office.get_msr_artifact(_MSR, "pkl")["data"] == b"pickled"
    assert store.asked == ["p/dict_pkl/B.pkl"]


def test_office_missing_path_field_is_404(monkeypatch, office):
    _install(monkeypatch, office, {"minio_pkl": "p/dict_pkl/B.pkl"}, _FakeStore({}))

    with pytest.raises(MsrArtifactError) as caught:
        office.get_msr_artifact(_MSR, "raw")
    assert caught.value.status == 404


def test_office_purged_object_is_410_not_404(monkeypatch, office):
    """61-day retention makes this the routine answer, not an error."""
    store = _FakeStore({}, error=_S3Gone())
    _install(monkeypatch, office, {"minio_pkl": "p/dict_pkl/B.pkl"}, store)

    with pytest.raises(MsrArtifactError) as caught:
        office.get_msr_artifact(_MSR, "pkl")
    assert caught.value.status == 410
    assert "보존 기간" in caught.value.message


def test_office_other_storage_errors_propagate(monkeypatch, office):
    """AccessDenied means misconfiguration, and must not read as 'expired'."""
    denied = type("_Denied", (Exception,), {"code": "AccessDenied"})()
    _install(monkeypatch, office, {"minio_pkl": "p/dict_pkl/B.pkl"}, _FakeStore({}, error=denied))

    with pytest.raises(Exception) as caught:
        office.get_msr_artifact(_MSR, "pkl")
    assert not isinstance(caught.value, MsrArtifactError)


def test_office_unknown_msr_is_404(monkeypatch, office):
    _install(monkeypatch, office, None, _FakeStore({}))

    with pytest.raises(MsrArtifactError) as caught:
        office.get_msr_artifact(_MSR, "raw")
    assert caught.value.status == 404
