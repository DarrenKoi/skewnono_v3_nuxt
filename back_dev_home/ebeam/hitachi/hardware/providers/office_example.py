# TEMPLATE — copy to office.py at the office. Usually needs NO edits: it only
# dispatches to the per-tab office adapters (providers/<tab>/office.py).
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Office hardware dispatcher — one adapter per tab, connected step by step.

Each tab folder (`fdc/`, `sharpness/`, `bm_pm/`, `bsm/`, `reso_center/`,
`mdc/`, `sce/`) carries its own `office_example.py` → `office.py` pair. A tab
whose `office.py` has not been copied yet falls back to that tab's `mock.py`,
so `SKEWNONO_HARDWARE_PROVIDER=office` can be switched on once and each tab
picks itself up as its adapter lands. The page stays usable throughout the
migration instead of showing six errors while one tab is being verified.

This works because a tab's `office.py` and `mock.py` expose the SAME builder
names returning the SAME raw shapes — the contract that made the per-tab
split possible in the first place — so either module drops into the call
sites below unchanged.

The fallback is deliberately silent in the RESPONSE (no "mock ·" marker), so
the server log is the only record of which tabs are real: `_tab` logs one
INFO line per fallback. Check it, or `ls providers/*/office.py`, before
reading an office chart as 사내 data.

Raw data comes from the tab modules; this dispatcher normalizes it to the
canonical HardwarePayload via ``normalizers.py``, mirroring
``providers/mock.py`` exactly.
"""

from datetime import datetime
from importlib import import_module

# The module logger would inherit WARNING from root, silently swallowing the
# fallback line below — the one record that a tab is serving mock under an
# office switch. skewnono.providers carries its own INFO handler.
from back_dev_home._logging.providers import logger as _LOG
from back_dev_home.ebeam.hitachi.hardware.contracts import HardwarePayload, ServiceKey
from back_dev_home.ebeam.hitachi.hardware.normalizers import (
    bm_pm_history_payload,
    docs_payload,
    service_gate,
    settings_payload,
)


def _tab(name: str):
    """Import providers/<name>/office.py, or that tab's mock.py if absent.

    The ``exc.name`` guard matters more than it looks: it separates "this tab
    has no office.py yet" from "this tab's office.py is broken". Without it, a
    wired adapter that fails to import — a missing ``ops_store``, a typo in an
    import line — would quietly downgrade to mock and serve fabricated data
    under an office switch. Only the tab module's own absence falls back;
    anything else propagates.
    """
    module = f"{__package__}.{name}.office"
    try:
        return import_module(module)
    except ModuleNotFoundError as exc:
        if exc.name != module:
            raise  # a real missing dependency inside the tab adapter
    _LOG.info(
        "hardware/%s has no providers/%s/office.py — serving MOCK for this tab. "
        "cp providers/%s/office_example.py providers/%s/office.py to connect it.",
        name, name, name, name,
    )
    return import_module(f"{__package__}.{name}.mock")


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
            summary="sharpness_monitor_cdsem 원시 문서를 시간순으로 제공합니다.",
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
    sce = _tab("sce")
    settings = sce.build_sce_settings(eqp_id, fab_name, end)
    history = sce.build_sce_history(eqp_id, fab_name, start, end)
    return settings_payload(
        service, tool_slug, eqp_id, fab_name,
        settings=settings,
        as_of=end.strftime("%Y-%m-%d"),
        summary="선택 장비와 동일 fab 장비의 SCE 설정/계수 스냅샷(최신)과 "
                "격일 수집 이력(시계열)을 제공합니다. SCE는 양산(M-fab)에서 활용됩니다.",
        docs=history,
    )
