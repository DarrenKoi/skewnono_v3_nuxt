"""Stable response contracts for msr_file endpoints (provider-independent gate).

PARALLEL CONTRACT NOTICE. msr_file's 7 response TypedDicts already live in
providers/mock.py, but mock.py is intentionally left untouched (see its
module docstring — it carries a fragile cache_clear hook data.py depends on,
and tests/test_contract.py imports it directly as a mock-pin linchpin). This
module therefore duplicates those 7 TypedDicts verbatim as the provider-
independent canonical contract, with ExeDetailInfo additionally augmented by
the 4 office-gated metadata keys (as NotRequired) that mock.py deliberately
omits and office.py is required to emit once connected. This is an accepted,
controller-approved deviation from the usual "move contracts out of mock.py"
pattern, scoped to this feature only.
"""

from typing import NotRequired, TypedDict


__all__ = [
    "MsrFileRow",
    "MsrParamSummary",
    "FdcParamSummary",
    "ExeDetailInfo",
    "AlignmentInfo",
    "SpmDict",
    "MsrFileResponse",
]


class MsrFileRow(TypedDict):
    msr: str
    sequence: int
    chip_number: str
    chip_coordinate: str
    stage_coordinate: str
    dnum_group: str
    mp_number: int
    parameter: str
    # NULLABLE (docs §df_result_data: "cd_value": 43.14, None). None exactly when
    # mp_number < 0 — a point with no data has no measurement.
    cd_value: float | None
    no_of_mp_image: int
    mp_image_name_01: str
    # ALL of the row's image files, in pickle column order (mp_image_name_01,
    # _02, ... — as many as no_of_mp_image). CD-SEM rows carry one; HV-SEM rows
    # carry several, one per targeting sub-position, distinguished by a stem
    # suffix (e.g. S04_M0004-01MP-U.jpeg / -T / -M / -L; sometimes only a .tif
    # exists — user-confirmed 2026-08-08). mp_image_name_01 stays as the
    # representative first image; consumers that render or warm images must
    # read THIS list or they silently drop every non-first HV-SEM image.
    mp_image_names: list[str]
    meas_condition_mag: int      # pickle "meas_condition mag"
    meas_condition_vac: int      # pickle "meas_condition vac"
    meas_condition_pixel: str    # pickle "meas_condition pixel"
    addressing1_score: int | None
    addressing2_score: int | None
    measurement_score: int | None
    meas_method: str             # Score | Width | Edge
    object_type: str             # pickle "object" — renamed, `object` shadows the builtin
    meas_kind: str | None        # Multi Point | Single Point | None


class MsrParamSummary(TypedDict):
    parameter: str
    count: int
    mean: float
    std: float
    min: float
    max: float
    # DERIVED from the parameter name, not read from the pickle — there is no
    # unit column in df_result_data. Must never be "": the frontend reads a
    # blank unit as UNKNOWN and excludes the MSR from cross-MSR analysis as
    # `metadata-missing`. An unrecognised parameter is nm (user-confirmed
    # 2026-08-08) — the office values are "just a number" because nm is the
    # assumed unit. Both providers get this from mock._unit via mock._summaries.
    unit: str


class FdcParamSummary(TypedDict):
    name: str
    category: str
    category_label: str
    unit: str
    nominal: float
    mean: float
    std: float
    min: float
    max: float
    # |mean - nominal| in units of the normal sigma; the abnormality magnitude.
    drift_sigma: float
    status: str  # ok | warning | bad


class ExeDetailInfo(TypedDict):
    """docs §exe_detail_info. `class` is a Python keyword -> `class_name`.

    The 4 trailing keys are office-gated canonical metadata: mock.py never
    emits them (tests/test_contract.py pins their absence there), while the
    office adapter MUST emit them before layout-dependent analyses (multi-MSR
    delta, site variability, same-site gallery) can leave `unavailable`. They
    are declared NotRequired so both mock and office responses pass this gate.
    """
    class_name: str
    recipe_name: str
    idp_name: str
    lot_id: str
    process: str
    wafer_id: str
    idw_name: str
    chip_array: str
    chip_pitch: str
    wafer_size: str
    map_offset: str
    map_origin: str
    site_layout_hash: NotRequired[str]
    recipe_revision: NotRequired[str]
    coordinate_transform_version: NotRequired[str]
    sequence_timestamp: NotRequired[str]


class AlignmentInfo(TypedDict):
    """docs §alignment. Keys "1".."3" are the alignment points."""
    image_file: dict[str, str]
    offset: dict[str, list[str]]   # [method, x, y] e.g. ["OM", "365", "3525"]
    score: dict[str, str]


class SpmDict(TypedDict):
    """docs §spm_dict. A 32-point profile: Vol (signal) against wf_len (nm)."""
    vave: list[float]
    Vol: list[float]
    wf_len: list[float]


class MsrFileResponse(TypedDict):
    msr: str
    class_name: str
    # The tool that ran this measurement, as an IPv4 string — the third leg of
    # the (eqp_ip, class_name, msr) address msr_image is fetched by. Carried
    # here because both adapters already resolve the parent meas_hist row for
    # class_name/total_images, so a caller holding only the msr can still build
    # an image URL (a shared deep link, or a search hit that was never in the
    # landing list the frontend caches). Empty string when the MSR has no parent
    # row — an unknown tool must read as unknown, never as a fabricated address.
    eqp_ip: str
    total_images: int
    sequence_count: int
    health: float
    parameters: list[MsrParamSummary]
    fdc_params: list[FdcParamSummary]
    # Per-MSR scalar FDC (docs §fixed_fdc): one value for the whole measurement.
    fixed_fdc: dict[str, float]
    # Per-sequence FDC (docs §dynamic_fdc): keyed by sequence string → {param: value}.
    dynamic_fdc: dict[str, dict[str, float]]
    exe_detail_info: ExeDetailInfo
    alignment: AlignmentInfo
    spm_dict: SpmDict
    total: int
    rows: list[MsrFileRow]
