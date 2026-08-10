from types import SimpleNamespace

from back_dev_home.msr_image.contracts import ImageLocator
from back_dev_home.msr_image.providers import office_example as office


class FakeFleet:
    """Fake FtpFleetDownloader: same report shape, canned bytes. The real class
    is transport-selected at import time (proxy on Windows, direct elsewhere),
    but both expose this exact surface — which is all the template touches."""

    instances = []

    def __init__(self, **kw):
        self.kw = kw
        FakeFleet.instances.append(self)

    def _fetch(self, remote_path):
        if remote_path.endswith("cond.txt"):
            return b"mag=50000\nvac=0.8"
        return b"\xff\xd8jpeg:" + remote_path.encode()

    def list_dirs(self, specs):
        # Real listings return FULL remote paths, not basenames. Tools mix JPEG
        # previews with TIFF originals; both must survive the filter.
        #
        # The dot-prefixed entries are the hidden cond sidecar DIRECTORIES the
        # tool really serves, one per image (office 확인 2026-08-10). They were
        # missing from this fake, which is why an extension-only filter looked
        # correct at home: they end in `.jpeg` too, so they pass an extension
        # test and then 550 on RETR. A fake tidier than the tool hides exactly
        # this class of bug.
        spec = specs[0]
        base = spec.listings[0].remote_dir.rstrip("/")
        paths = [
            f"{base}/shot01.jpeg",
            f"{base}/.shot01.jpeg",
            f"{base}/shot02.jpeg",
            f"{base}/.shot02.jpeg",
            f"{base}/shot03.tif",
            f"{base}/.shot03.tif",
            f"{base}/notes.txt",
        ]
        return SimpleNamespace(
            listings=[SimpleNamespace(host=spec.host, paths=paths)], failures=[]
        )

    def download(self, specs, *, on_file=None):
        # Mirrors the real per-file semantics: in-order per spec, per-file
        # failure isolation, "<ExcName>: <msg>" error strings, streamed bytes
        # dropped from the report when on_file consumes them.
        files, failures = [], []
        for spec in specs:
            for path in spec.files:
                try:
                    data = self._fetch(path)
                except Exception as exc:
                    failures.append(
                        SimpleNamespace(
                            host=spec.host,
                            remote_path=path,
                            error=f"{type(exc).__name__}: {exc}",
                        )
                    )
                    continue
                if on_file is not None:
                    on_file(spec.host, path, data)
                    data = b""
                files.append(
                    SimpleNamespace(host=spec.host, remote_path=path, data=data)
                )
        return SimpleNamespace(files=files, failures=failures)


def test_list_images_filters_to_image_extensions(monkeypatch):
    monkeypatch.setattr(office, "FtpFleetDownloader", FakeFleet)
    names = office.list_images("10.0.0.1", "ADI", "MSR_1", _config=office._test_config())
    assert names == ["shot01.jpeg", "shot02.jpeg", "shot03.tif"]


def test_fetch_image_tif_gets_tiff_content_type(monkeypatch):
    monkeypatch.setattr(office, "FtpFleetDownloader", FakeFleet)
    img = office.fetch_image(
        ImageLocator("10.0.0.1", "ADI", "MSR_1", "shot03.tif"), _config=office._test_config()
    )
    assert img.content_type == "image/tiff"


def test_fetch_image_reads_image_and_cond(monkeypatch):
    monkeypatch.setattr(office, "FtpFleetDownloader", FakeFleet)
    img = office.fetch_image(
        ImageLocator("10.0.0.1", "ADI", "MSR_1", "shot01.jpeg"), _config=office._test_config()
    )
    assert img.content_type == "image/jpeg"
    assert img.data.startswith(b"\xff\xd8jpeg")
    assert img.cond == "mag=50000\nvac=0.8"


def test_download_all_reports_each(monkeypatch):
    monkeypatch.setattr(office, "FtpFleetDownloader", FakeFleet)
    seen = []
    office.download_all(
        "10.0.0.1", "ADI", "MSR_1", ["shot01.jpeg", "shot02.jpeg"],
        on_file=lambda n, f, e: seen.append((n, f is not None, e)),
        concurrency=2, _config=office._test_config(),
    )
    assert sorted(n for n, _, _ in seen) == ["shot01.jpeg", "shot02.jpeg"]
    assert all(ok and err is None for _, ok, err in seen)


def _last_downloader_kwargs(monkeypatch, run) -> dict:
    FakeFleet.instances.clear()
    monkeypatch.setattr(office, "FtpFleetDownloader", FakeFleet)
    run()
    assert FakeFleet.instances, "the template never built a downloader"
    return FakeFleet.instances[-1].kw


def test_single_fetch_uses_the_configured_host_timeout_floor(monkeypatch):
    cfg = office._test_config()
    kw = _last_downloader_kwargs(
        monkeypatch,
        lambda: office.fetch_image(
            ImageLocator("10.0.0.1", "ADI", "MSR_1", "shot03.tif"), _config=cfg
        ),
    )
    assert kw["host_timeout"] == cfg.ftp_host_timeout


def test_download_all_scales_host_timeout_with_files_per_connection(monkeypatch):
    """A job big enough to outlive the library's flat 60s default used to be
    abandoned mid-transfer, and an abandoned worker keeps calling back. The
    budget has to follow the work queued on the busiest connection.

    The job size is DERIVED from the per-image constant rather than written as
    a literal. It used to be 120 names (20 per connection), which outgrew the
    floor only because _SECONDS_PER_IMAGE was a 5.0 guess; measuring it at the
    office (2026-08-10) dropped it to 0.4 and that scenario silently stopped
    reaching the branch it names. Deriving the count means the next revision of
    the constant cannot quietly turn this into a test of the floor.
    """
    cfg = office._test_config()
    per_connection = int(cfg.ftp_host_timeout / office._SECONDS_PER_IMAGE) + 50
    names = [f"shot{i:04d}.jpeg" for i in range(per_connection * 6)]
    kw = _last_downloader_kwargs(
        monkeypatch,
        lambda: office.download_all(
            "10.0.0.1", "ADI", "MSR_1", names,
            on_file=lambda n, f, e: None, concurrency=6, _config=cfg,
        ),
    )
    assert kw["host_timeout"] == office._SECONDS_PER_IMAGE * per_connection
    assert kw["host_timeout"] > cfg.ftp_host_timeout


def test_the_proxy_transport_caps_the_budget_under_uwsgi_harakiri(monkeypatch):
    """One proxy request carries a BATCH of specs and its uWSGI kills the whole
    request at harakiri=75s (ftp_handler/proxy/wsgi.ini). A budget above that
    does not buy a longer download — it gets every spec in the batch killed at
    once, which is worse than the single-host timeout it was meant to avoid."""
    monkeypatch.setattr(office, "_VIA_PROXY", True)
    cfg = office._test_config()
    assert office._host_timeout(cfg, 200) == office._PROXY_HOST_TIMEOUT_CAP
    assert office._PROXY_HOST_TIMEOUT_CAP < 75.0, "must stay under wsgi.ini harakiri"


def test_the_direct_transport_is_uncapped(monkeypatch):
    """The cloud deploy talks to the tools directly — no uWSGI request wrapping
    the transfer, so nothing kills a long connection from outside."""
    monkeypatch.setattr(office, "_VIA_PROXY", False)
    cfg = office._test_config()
    assert office._host_timeout(cfg, 200) == office._SECONDS_PER_IMAGE * 200


def test_an_explicit_max_overrides_the_transport_default(monkeypatch):
    monkeypatch.setattr(office, "_VIA_PROXY", True)
    cfg = office.load_config({"SKEWNONO_TOOL_FTP_HOST_TIMEOUT_MAX": "300"})
    # Enough images that the raw budget exceeds the explicit max, so the max is
    # what binds. Derived from the constant for the same reason as above.
    images = int(300 / office._SECONDS_PER_IMAGE) + 100
    assert office._host_timeout(cfg, images) == 300.0


def test_a_cap_below_the_floor_never_shrinks_a_single_fetch(monkeypatch):
    """Contradictory settings must not make one image's budget smaller than the
    floor an operator explicitly configured for single fetches and listings."""
    monkeypatch.setattr(office, "_VIA_PROXY", True)
    cfg = office.load_config(
        {"SKEWNONO_TOOL_FTP_HOST_TIMEOUT": "90", "SKEWNONO_TOOL_FTP_HOST_TIMEOUT_MAX": "30"}
    )
    assert office._host_timeout(cfg, 1) == 90.0


def test_small_job_keeps_the_floor_rather_than_shrinking_below_it(monkeypatch):
    cfg = office._test_config()
    kw = _last_downloader_kwargs(
        monkeypatch,
        lambda: office.download_all(
            "10.0.0.1", "ADI", "MSR_1", ["a.jpeg", "b.jpeg"],
            on_file=lambda n, f, e: None, concurrency=6, _config=cfg,
        ),
    )
    assert kw["host_timeout"] == cfg.ftp_host_timeout


def test_download_all_missing_cond_still_reports_image(monkeypatch):
    import ftplib

    class NoCondFleet(FakeFleet):
        def _fetch(self, remote_path):
            if remote_path.endswith("cond.txt"):
                raise ftplib.error_perm("550 No such file")
            return super()._fetch(remote_path)

    monkeypatch.setattr(office, "FtpFleetDownloader", NoCondFleet)
    seen = []
    office.download_all(
        "10.0.0.1", "ADI", "MSR_1", ["shot01.jpeg", "shot02.jpeg"],
        on_file=lambda n, f, e: seen.append((n, f, e)),
        concurrency=1, _config=office._test_config(),
    )
    assert sorted(n for n, _, _ in seen) == ["shot01.jpeg", "shot02.jpeg"]
    assert all(f is not None and f.cond is None and e is None for _, f, e in seen)


def test_fetch_image_missing_raises_not_found(monkeypatch):
    import ftplib

    import pytest

    from back_dev_home.msr_image.errors import ImageNotFound

    class MissingFleet(FakeFleet):
        def _fetch(self, remote_path):
            raise ftplib.error_perm("550 No such file")

    monkeypatch.setattr(office, "FtpFleetDownloader", MissingFleet)
    with pytest.raises(ImageNotFound):
        office.fetch_image(
            ImageLocator("10.0.0.1", "ADI", "MSR_1", "shot01.jpeg"), _config=office._test_config()
        )


def test_fetch_image_tool_down_raises_source_unavailable(monkeypatch):
    import pytest

    from back_dev_home.msr_image.errors import SourceUnavailable

    class DeadFleet(FakeFleet):
        def download(self, specs, *, on_file=None):
            # connect/login failed: host-level failure, remote_path=None.
            return SimpleNamespace(
                files=[],
                failures=[
                    SimpleNamespace(
                        host=specs[0].host,
                        remote_path=None,
                        error="TimeoutError: connection timed out",
                    )
                ],
            )

    monkeypatch.setattr(office, "FtpFleetDownloader", DeadFleet)
    with pytest.raises(SourceUnavailable):
        office.fetch_image(
            ImageLocator("10.0.0.1", "ADI", "MSR_1", "shot01.jpeg"), _config=office._test_config()
        )
