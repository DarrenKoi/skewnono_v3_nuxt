from back_dev_home.msr_image import data
from back_dev_home.msr_image.cache import DiskImageCache, make_cache
from back_dev_home.msr_image.config import load_config


def test_mock_provider_dispatch(monkeypatch):
    monkeypatch.setenv("SKEWNONO_MSR_IMAGE_PROVIDER", "mock")
    names = data.list_images("10.0.0.1", "ADI", "MSR_1")
    assert names and all(n.endswith(".jpeg") for n in names)


def test_make_cache_mock_is_disk(tmp_path):
    cfg = load_config({"IMAGE_CACHE_DIR": str(tmp_path)})
    cache = make_cache(cfg, provider="mock")
    assert isinstance(cache, DiskImageCache)
