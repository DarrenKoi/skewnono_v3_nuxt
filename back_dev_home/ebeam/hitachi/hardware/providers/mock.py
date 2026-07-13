"""Phase 1 hardware mock provider — dispatch all six services."""

from datetime import datetime

from back_dev_home.ebeam.hitachi.hardware.contracts import HardwarePayload, ServiceKey
from back_dev_home.ebeam.hitachi.hardware.normalizers import (
    bm_pm_history_payload,
    docs_payload,
    now_iso,
    settings_payload,
    unavailable_payload,
)
from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm_mock import build_bm_pm_data
from back_dev_home.ebeam.hitachi.hardware.providers.beam_shape_mock import build_beam_shape_docs
from back_dev_home.ebeam.hitachi.hardware.providers.fdc_mock import build_fdc_docs
from back_dev_home.ebeam.hitachi.hardware.providers.mdc_mock import (
    build_mdc_history,
    build_mdc_settings,
)
from back_dev_home.ebeam.hitachi.hardware.providers.network_sharpness_mock import (
    build_network_sharpness_docs,
)
from back_dev_home.ebeam.hitachi.hardware.providers.reso_center_mock import build_reso_center_docs
from back_dev_home.ebeam.hitachi.hardware.providers.sce_mock import build_sce_settings


# bsm / reso-center / sce / sharpness are CD-SEM-only checks.
_CDSEM_ONLY: frozenset[str] = frozenset({"bsm", "reso-center", "sce", "sharpness"})

_CDSEM_ONLY_MSG: dict[str, str] = {
    "bsm": "BSM는 CD-SEM 장비에서만 제공됩니다.",
    "reso-center": "Reso Center는 CD-SEM 장비에서만 제공됩니다.",
    "sce": "SCE는 CD-SEM 장비에서만 제공됩니다.",
    "sharpness": "Sharpness는 CD-SEM 장비에서만 제공됩니다.",
}

_EMPTY_HINT: dict[str, str] = {
    "bsm": "장비를 선택하면 BSM 추세와 360° 빔 형상을 확인할 수 있습니다.",
    "reso-center": "장비를 선택하면 Reso Center 추세를 확인할 수 있습니다.",
    "fdc": "장비를 선택하면 FDC 신호/판정 추세를 확인할 수 있습니다.",
    "mdc": "장비를 선택하면 MDC 보정 계수와 동일 fab skew를 확인할 수 있습니다.",
    "sce": "장비를 선택하면 SCE 설정과 계수 곡선을 확인할 수 있습니다.",
    "bm-pm": "장비를 선택하면 BM/PM 작업 이력과 예정 작업을 확인할 수 있습니다.",
    "sharpness": "장비를 선택하면 chamber stub sharpness 추세와 360° 빔 형상을 확인할 수 있습니다.",
}


def _empty_available(
    tool_slug: str, service: ServiceKey, fab_name: str | None
) -> HardwarePayload:
    return {
        "tool_slug": tool_slug,
        "service": service,
        "eqp_id": None,
        "fab_name": fab_name,
        "available": True,
        "fetched_at": now_iso(),
        "summary": _EMPTY_HINT[service],
        "cards": [],
        "tables": [],
    }


def get_hardware_service(
    tool_slug: str,
    service: ServiceKey,
    eqp_id: str | None,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> HardwarePayload:
    # CD-SEM-only services are unavailable for hvsem.
    if service in _CDSEM_ONLY and tool_slug != "cdsem":
        return unavailable_payload(
            service, tool_slug, eqp_id, fab_name, _CDSEM_ONLY_MSG[service]
        )

    if eqp_id is None:
        # No tool picked yet — available-but-empty so the page shows a hint.
        return _empty_available(tool_slug, service, fab_name)

    if service == "bm-pm":
        data = build_bm_pm_data(eqp_id, end)
        return bm_pm_history_payload(
            tool_slug,
            eqp_id,
            fab_name,
            past_rows=data["past"],
            future_rows=data["future"],
            cards=data["cards"],
        )

    if service == "bsm":
        docs = build_beam_shape_docs(eqp_id, fab_name, start, end)
        return docs_payload(
            service, tool_slug, eqp_id, fab_name,
            docs=docs,
            summary="beam_shape(type:total) 원시 문서를 시간순으로 제공합니다. "
                    "filter/축을 선택해 추세와 360° 빔 형상을 확인하세요.",
        )

    if service == "reso-center":
        docs = build_reso_center_docs(eqp_id, fab_name, start, end)
        return docs_payload(
            service, tool_slug, eqp_id, fab_name,
            docs=docs,
            summary="reso_center_log 원시 문서를 시간순으로 제공합니다.",
        )

    if service == "fdc":
        docs = build_fdc_docs(eqp_id, fab_name, start, end)
        return docs_payload(
            service, tool_slug, eqp_id, fab_name,
            docs=docs,
            summary="network_fdc_cdsem 원시 문서(fdc_key별)를 시간순으로 제공합니다.",
        )

    if service == "sharpness":
        docs = build_network_sharpness_docs(eqp_id, fab_name, start, end)
        return docs_payload(
            service, tool_slug, eqp_id, fab_name,
            docs=docs,
            summary="network_sharpness_cdsem 원시 문서를 시간순으로 제공합니다.",
        )

    if service == "mdc":
        settings = build_mdc_settings(eqp_id, fab_name, end)
        history = build_mdc_history(eqp_id, start, end)
        return settings_payload(
            service, tool_slug, eqp_id, fab_name,
            settings=settings,
            as_of=end.strftime("%Y-%m-%d"),
            summary="선택 장비의 MDC 보정 이력(시계열)과 동일 fab 장비의 "
                    "스냅샷(as-of) 비교를 제공합니다.",
            docs=history,
        )

    # service == "sce"
    settings = build_sce_settings(eqp_id, fab_name, end)
    return settings_payload(
        service, tool_slug, eqp_id, fab_name,
        settings=settings,
        as_of=end.strftime("%Y-%m-%d"),
        summary="선택 장비와 동일 fab 장비의 SCE 설정/계수 스냅샷(as-of)을 제공합니다. "
                "SCE는 양산(M-fab)에서 활용됩니다.",
    )
