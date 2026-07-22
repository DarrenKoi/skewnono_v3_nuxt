# TEMPLATE — copy to office.py at the office. Usually needs NO edits: it only
# dispatches to the per-tab office adapters (providers/<tab>/office.py).
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office hardware dispatcher — one adapter per tab, connected step by step.

Each tab folder (`fdc/`, `sharpness/`, `bm_pm/`, `bsm/`, `reso_center/`,
`mdc/`, `sce/`) carries its own `office_example.py` → `office.py` pair. A tab
whose `office.py` has not been copied/implemented yet FAILS FAST with a
NotImplementedError naming that tab, while already-connected tabs keep
working — so the migration can land one tab at a time.

Raw data comes from the tab modules; this dispatcher normalizes it to the
canonical HardwarePayload via ``normalizers.py``, mirroring
``providers/mock.py`` exactly.
"""

from datetime import datetime
from importlib import import_module

from back_dev_home.ebeam.hitachi.hardware.contracts import HardwarePayload, ServiceKey
from back_dev_home.ebeam.hitachi.hardware.normalizers import (
    bm_pm_history_payload,
    docs_payload,
    service_gate,
    settings_payload,
)


def _tab(name: str):
    """Import providers/<name>/office.py, failing fast when not connected."""
    module = f"{__package__}.{name}.office"
    try:
        return import_module(module)
    except ModuleNotFoundError as exc:
        if exc.name != module:
            raise  # a real missing dependency inside the tab adapter
        raise NotImplementedError(
            f"hardware/{name} office adapter not connected yet — "
            f"cp providers/{name}/office_example.py providers/{name}/office.py "
            "and implement it (see hardware/MIGRATION.md)."
        ) from exc


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
        data = _tab("bm_pm").build_bm_pm_data(eqp_id, end)
        return bm_pm_history_payload(
            tool_slug,
            eqp_id,
            fab_name,
            past_rows=data["past"],
            future_rows=data["future"],
            cards=data["cards"],
        )

    if service == "bsm":
        docs = _tab("bsm").build_beam_shape_docs(eqp_id, fab_name, start, end)
        return docs_payload(
            service, tool_slug, eqp_id, fab_name,
            docs=docs,
            summary="beam_shape(type:total) 원시 문서를 시간순으로 제공합니다. "
                    "filter/축을 선택해 추세와 360° 빔 형상을 확인하세요.",
        )

    if service == "reso-center":
        docs = _tab("reso_center").build_reso_center_docs(eqp_id, fab_name, start, end)
        return docs_payload(
            service, tool_slug, eqp_id, fab_name,
            docs=docs,
            summary="reso_center_log 원시 문서를 시간순으로 제공합니다.",
        )

    if service == "fdc":
        docs = _tab("fdc").build_fdc_docs(eqp_id, fab_name, start, end)
        return docs_payload(
            service, tool_slug, eqp_id, fab_name,
            docs=docs,
            summary="network_fdc_cdsem 원시 문서(fdc_key별)를 시간순으로 제공합니다.",
        )

    if service == "sharpness":
        docs = _tab("sharpness").build_network_sharpness_docs(
            eqp_id, fab_name, start, end
        )
        return docs_payload(
            service, tool_slug, eqp_id, fab_name,
            docs=docs,
            summary="network_sharpness_cdsem 원시 문서를 시간순으로 제공합니다.",
        )

    if service == "mdc":
        mdc = _tab("mdc")
        settings = mdc.build_mdc_settings(eqp_id, fab_name, end)
        history = mdc.build_mdc_history(eqp_id, start, end)
        return settings_payload(
            service, tool_slug, eqp_id, fab_name,
            settings=settings,
            as_of=end.strftime("%Y-%m-%d"),
            summary="선택 장비의 MDC 보정 이력(시계열)과 동일 fab 장비의 "
                    "스냅샷(as-of) 비교를 제공합니다.",
            docs=history,
        )

    # service == "sce"
    settings = _tab("sce").build_sce_settings(eqp_id, fab_name, end)
    return settings_payload(
        service, tool_slug, eqp_id, fab_name,
        settings=settings,
        as_of=end.strftime("%Y-%m-%d"),
        summary="선택 장비와 동일 fab 장비의 SCE 설정/계수 스냅샷(as-of)을 제공합니다. "
                "SCE는 양산(M-fab)에서 활용됩니다.",
    )
