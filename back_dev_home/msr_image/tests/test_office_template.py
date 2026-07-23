from back_dev_home.msr_image.contracts import ImageLocator
from back_dev_home.msr_image.providers import office_example as office


class FakeFtp:
    """Records the paths requested; returns canned bytes. Context-manager like FtpClient."""

    instances = []

    def __init__(self, **kw):
        self.kw = kw
        self.listed = None
        FakeFtp.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def list_dir(self, remote_dir, pattern=None):
        self.listed = (remote_dir, pattern)
        return ["shot01.jpeg", "shot02.jpeg", "notes.txt"]

    def download(self, remote_path):
        if remote_path.endswith("cond.txt"):
            return b"mag=50000\nvac=0.8"
        return b"\xff\xd8jpeg:" + remote_path.encode()


def test_list_images_filters_jpeg(monkeypatch):
    monkeypatch.setattr(office, "FtpClient", FakeFtp)
    names = office.list_images("10.0.0.1", "ADI", "MSR_1", _config=office._test_config())
    assert names == ["shot01.jpeg", "shot02.jpeg"]


def test_fetch_image_reads_image_and_cond(monkeypatch):
    monkeypatch.setattr(office, "FtpClient", FakeFtp)
    img = office.fetch_image(
        ImageLocator("10.0.0.1", "ADI", "MSR_1", "shot01.jpeg"), _config=office._test_config()
    )
    assert img.content_type == "image/jpeg"
    assert img.data.startswith(b"\xff\xd8jpeg")
    assert img.cond == "mag=50000\nvac=0.8"


def test_download_all_reports_each(monkeypatch):
    monkeypatch.setattr(office, "FtpClient", FakeFtp)
    seen = []
    office.download_all(
        "10.0.0.1", "ADI", "MSR_1", ["shot01.jpeg", "shot02.jpeg"],
        on_file=lambda n, f, e: seen.append((n, f is not None, e)),
        concurrency=2, _config=office._test_config(),
    )
    assert sorted(n for n, _, _ in seen) == ["shot01.jpeg", "shot02.jpeg"]
    assert all(ok and err is None for _, ok, err in seen)
