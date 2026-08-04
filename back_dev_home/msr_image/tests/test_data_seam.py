import pytest

from back_dev_home.msr_image import data
from back_dev_home.msr_image.cache import DiskImageCache, make_cache
from back_dev_home.msr_image.config import load_config
from back_dev_home.msr_image.errors import ConfigError


def test_mock_provider_dispatch(monkeypatch):
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    names = data.list_images("10.0.0.1", "ADI", "MSR_1")
    # Office tools mix JPEG previews with TIFF originals; the mock mirrors that.
    assert names and all(n.endswith((".jpeg", ".tif")) for n in names)


def test_make_cache_mock_is_disk(tmp_path):
    cfg = load_config({"IMAGE_CACHE_DIR": str(tmp_path)})
    cache = make_cache(cfg, provider="mock")
    assert isinstance(cache, DiskImageCache)


def test_make_cache_office_requires_bucket():
    # Office mode with no SKEWNONO_IMAGE_CACHE_BUCKET must fail loud (500), not
    # silently fall back to minio_handler's default bucket.
    cfg = load_config({})
    with pytest.raises(ConfigError):
        make_cache(cfg, provider="office")


def test_make_cache_office_with_bucket_ok():
    cfg = load_config({"SKEWNONO_IMAGE_CACHE_BUCKET": "img-cache"})
    # Constructs a MinioImageCache with a lazy client — no connection here.
    cache = make_cache(cfg, provider="office")
    assert cache is not None


def test_make_cache_office_rejects_root_prefix():
    # A root/empty prefix would make purge enumerate the whole bucket.
    cfg = load_config({"SKEWNONO_IMAGE_CACHE_BUCKET": "b", "SKEWNONO_IMAGE_CACHE_PREFIX": "/"})
    with pytest.raises(ConfigError):
        make_cache(cfg, provider="office")


def test_list_images_seam_signature_is_three_args():
    """The ext filter lives in routes.py, deliberately, and must stay there.

    Pushing it into the provider would widen this signature, and every office
    checkout's gitignored providers/office.py is a COPY -- it would keep the
    old signature and the app factory would fail to boot until someone ran
    `python -m scripts.sync_office_adapters msr_image`. Filtering a returned
    list is presentation, not data access.
    """
    import inspect

    params = list(inspect.signature(data.list_images).parameters)
    assert params == ["eqp_ip", "class_name", "msr"]
