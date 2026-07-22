"""Phase 1 hardware mock provider — dispatch each tab to its subfolder.

One subfolder per hardware tab (`fdc/`, `sharpness/`, `bm_pm/`, `bsm/`,
`reso_center/`, `mdc/`, `sce/`), each holding `mock.py` plus the office
adapter pair (`office_example.py` template → gitignored `office.py`). This
dispatcher only routes and normalizes; the tab modules build the raw data.
"""

from datetime import datetime

from back_dev_home.ebeam.hitachi.hardware.contracts import HardwarePayload, ServiceKey
from back_dev_home.ebeam.hitachi.hardware.normalizers import (
    bm_pm_history_payload,
    docs_payload,
    service_gate,
    settings_payload,
)
from back_dev_home.ebeam.hitachi.hardware.providers.bm_pm.mock import build_bm_pm_data
from back_dev_home.ebeam.hitachi.hardware.providers.bsm.mock import build_beam_shape_docs
from back_dev_home.ebeam.hitachi.hardware.providers.fdc.mock import build_fdc_docs
from back_dev_home.ebeam.hitachi.hardware.providers.mdc.mock import (
    build_mdc_history,
    build_mdc_settings,
)
from back_dev_home.ebeam.hitachi.hardware.providers.reso_center.mock import (
    build_reso_center_docs,
)
from back_dev_home.ebeam.hitachi.hardware.providers.sce.mock import build_sce_settings
from back_dev_home.ebeam.hitachi.hardware.providers.sharpness.mock import (
    build_network_sharpness_docs,
)


def get_hardware_service(
    tool_slug: str,
    service: ServiceKey,
    eqp_id: str | None,
    fab_name: str | None,
    start: datetime,
    end: datetime,
) -> HardwarePayload:
    gated = service_gate(tool_slug, service, eqp_id, fab_name)
    if gated is not None:
        return gated

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
