from back_dev_home.msr_image.contracts import ImageLocator
from back_dev_home.msr_image.providers import mock


def test_list_is_deterministic_and_image_typed():
    a = mock.list_images("10.0.0.1", "ADI", "MSR_1")
    b = mock.list_images("10.0.0.1", "ADI", "MSR_1")
    assert a == b
    assert len(a) >= 1
    assert all(n.endswith((".jpeg", ".tif")) for n in a)


def test_fetch_returns_svg_and_synthetic_cond():
    name = mock.list_images("10.0.0.1", "ADI", "MSR_1")[0]
    img = mock.fetch_image(ImageLocator("10.0.0.1", "ADI", "MSR_1", name))
    assert img.content_type == "image/svg+xml"
    assert b"<svg" in img.data
    assert img.cond and "mag" in img.cond.lower()


def test_download_all_invokes_callback_per_name():
    names = mock.list_images("10.0.0.1", "ADI", "MSR_1")
    seen = []
    mock.download_all(
        "10.0.0.1", "ADI", "MSR_1", names,
        on_file=lambda n, f, e: seen.append((n, f is not None, e)),
        concurrency=4,
    )
    assert sorted(n for n, _, _ in seen) == sorted(names)
    assert all(ok and err is None for _, ok, err in seen)
