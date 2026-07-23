"""Stable msr_image data seam. Picks mock/office via get_data_provider."""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.msr_image.contracts import FetchedImage, ImageLocator
from back_dev_home.msr_image.providers import mock as mock_provider


def provider_name() -> str:
    return "office" if get_data_provider("msr_image") == "office" else "mock"


def _provider():
    if provider_name() == "office":
        from back_dev_home.msr_image.providers import office
        return office
    return mock_provider


def list_images(eqp_ip: str, class_name: str, msr: str) -> list[str]:
    return _provider().list_images(eqp_ip, class_name, msr)


def fetch_image(locator: ImageLocator) -> FetchedImage:
    return _provider().fetch_image(locator)


def download_all(eqp_ip, class_name, msr, names, on_file, concurrency=6) -> None:
    _provider().download_all(eqp_ip, class_name, msr, names, on_file, concurrency)
