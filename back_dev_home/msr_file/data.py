"""Stable MSR-file data seam with mock/office adapters."""

from back_dev_home._runtime.data_provider import get_data_provider
from back_dev_home.msr_file.providers import mock as mock_provider
from back_dev_home.msr_file.providers.mock import (
    AlignmentInfo,
    ExeDetailInfo,
    FdcParamSummary,
    MsrFileResponse,
    MsrFileRow,
    MsrParamSummary,
    SpmDict,
)


__all__ = [
    "MsrFileRow",
    "MsrParamSummary",
    "FdcParamSummary",
    "ExeDetailInfo",
    "AlignmentInfo",
    "SpmDict",
    "MsrFileResponse",
    "get_msr_file",
    "get_msr_image",
]


def _provider():
    if get_data_provider("msr_file") == "office":
        from back_dev_home.msr_file.providers import office
        return office
    return mock_provider


def get_msr_file(
    msr: str,
    class_name: str | None = None,
    total_images: int | None = None,
) -> MsrFileResponse | None:
    return _provider().get_msr_file(msr, class_name, total_images)


def get_msr_image(name: str) -> str:
    return _provider().get_msr_image(name)


# Preserve the established test/debug hook while keeping routes on this façade.
get_msr_file.cache_clear = mock_provider.get_msr_file.cache_clear  # type: ignore[attr-defined]
get_msr_image.cache_clear = mock_provider.get_msr_image.cache_clear  # type: ignore[attr-defined]

# Kept temporarily for existing characterization tests. Application code should
# consume summaries through ``get_msr_file`` rather than this mock detail.
_summaries = mock_provider._summaries
