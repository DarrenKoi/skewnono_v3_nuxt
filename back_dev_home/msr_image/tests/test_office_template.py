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
        # Real listings return FULL remote paths, not basenames.
        spec = specs[0]
        base = spec.listings[0].remote_dir.rstrip("/")
        paths = [f"{base}/shot01.jpeg", f"{base}/shot02.jpeg", f"{base}/notes.txt"]
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


def test_list_images_filters_jpeg(monkeypatch):
    monkeypatch.setattr(office, "FtpFleetDownloader", FakeFleet)
    names = office.list_images("10.0.0.1", "ADI", "MSR_1", _config=office._test_config())
    assert names == ["shot01.jpeg", "shot02.jpeg"]


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
