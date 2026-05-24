"""Phase 1 hardware mock provider."""

from back_dev_home.ebeam.hitachi.hardware.contracts import HardwarePayload, ServiceKey
from back_dev_home.ebeam.hitachi.hardware.normalizers import (
    bm_pm_history_payload,
    bsm_payload,
    now_iso,
    unavailable_payload,
)
from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm_mock import build_bm_pm_data
from back_dev_home.ebeam.hitachi.hardware.providers.bsm_mock import build_bsm_data


_UNAVAILABLE_SUMMARIES: dict[ServiceKey, str] = {
    "bsm": "BSM data is only available for selected equipment. Office wiring will provide the real source.",
    "fdc": "FDC signal and alarm trends will appear after office data wiring is connected.",
    "bm-pm": "BM/PM data is available.",
}


def get_hardware_service(
    tool_slug: str,
    service: ServiceKey,
    eqp_id: str | None,
    fab_id: str | None,
) -> HardwarePayload:
    if service == "bm-pm":
        if eqp_id is None:
            # No tool picked yet — return an available-but-empty payload so the
            # page shows the "select equipment" hint instead of an error.
            return {
                "tool_slug": tool_slug,
                "service": "bm-pm",
                "eqp_id": None,
                "fab_id": fab_id,
                "available": True,
                "fetched_at": now_iso(),
                "summary": "장비를 선택하면 BM/PM 작업 이력과 예정 작업을 확인할 수 있습니다.",
                "cards": [],
                "tables": [],
            }
        data = build_bm_pm_data(eqp_id)
        return bm_pm_history_payload(
            tool_slug,
            eqp_id,
            fab_id,
            past_rows=data["past"],
            future_rows=data["future"],
            cards=data["cards"],
        )
    if service == "bsm":
        # BSM is a CD-SEM-only check; other tools have no source for it.
        if tool_slug != "cdsem":
            return unavailable_payload(
                service,
                tool_slug,
                eqp_id,
                fab_id,
                "BSM는 CD-SEM 장비에서만 제공됩니다.",
            )
        if eqp_id is None:
            # No tool picked yet — available-but-empty so the page shows the
            # "select equipment" hint instead of an error (mirrors bm-pm).
            return {
                "tool_slug": tool_slug,
                "service": "bsm",
                "eqp_id": None,
                "fab_id": fab_id,
                "available": True,
                "fetched_at": now_iso(),
                "summary": "장비를 선택하면 BSM 추세와 360° 빔 형상을 확인할 수 있습니다.",
                "cards": [],
                "tables": [],
            }
        return bsm_payload(tool_slug, eqp_id, fab_id, bsm=build_bsm_data(eqp_id))
    return unavailable_payload(
        service,
        tool_slug,
        eqp_id,
        fab_id,
        _UNAVAILABLE_SUMMARIES[service],
    )
