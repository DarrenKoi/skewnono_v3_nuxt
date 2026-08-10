# TEMPLATE — copy to office.py at the office, then implement/verify the body.
# office.py is gitignored; this file (office_example.py) is the tracked skeleton.
"""Phase 2/3 MSR-file adapter: meas_hist doc -> ``minio_pkl`` pickle -> contract.

Data path (docs/datatables/meas_hist.txt + msr_file_pickle.txt):

* The meas_hist_{cdsem,hvsem} document found by ``msr.keyword`` carries two
  MinIO paths: ``minio_msr`` (the RAW .MSR text file) and ``minio_pkl`` (the
  post-processed pickle). This adapter reads ONLY ``minio_pkl`` — the pickle
  already holds the parsed structure the UI needs (``df_result_data`` +
  ``exe_detail_info`` + ``alignment`` + ``fixed_fdc`` + ``dynamic_fdc`` +
  ``spm_dict``); re-parsing the raw text here would duplicate the office
  post-processing pipeline.
* ``minio_pkl`` is a key relative to the configured ``PREFIX`` — NOT
  ``"bucket/key"``. Office-confirmed 2026-07-22: the stored
  ``hitachi_sem/...`` resolves to ``user/2067928/hitachi_sem/...``, so the
  bare key goes to a default-constructed client and both ``BUCKET`` and
  ``PREFIX`` come from ``minio_handler/minio_config.py`` — not from the path,
  and not from .env (see the warning in ``back_dev_home/.env.example``).
  Treating segment one as a bucket fails with ``InvalidBucketName``: S3 bucket
  names cannot contain underscores. Fetched via
  ``minio_handler.MinioObject().get_pickle``; the import is lazy so this
  module loads fine on hosts without a MinIO config.

Office-gated canonical metadata (contracts.ExeDetailInfo, enforced non-empty
by tests/test_contract_gate.py in office mode):

* ``site_layout_hash``       — sha1 over the layout-defining data: chip_array/
                               chip_pitch/wafer_size/map_origin + the sorted
                               (chip_number, dnum_group, mp_number) site set.
                               map_offset is EXCLUDED on purpose: if it carries
                               a per-run alignment correction it would fracture
                               one layout into many. Verify at the office.
* ``recipe_revision``        — a real revision key from the pickle's
                               exe_detail_info when one exists; otherwise a
                               ``fp-`` fingerprint over recipe identity +
                               layout + parameter set. The fingerprint splits
                               revisions that changed anything visible in the
                               pickle; revisions invisible to the pickle merge
                               — replace with the real field once located.
* ``coordinate_transform_version`` — pickle key if present, else the pinned
                               tag ``minio-pkl-v1`` naming the office pickle
                               pipeline's transform.
* ``sequence_timestamp``     — the parent doc's ``start_time`` (real
                               acquisition start; the pickle carries no
                               per-sequence clock).

At the office: fill in OPENSEARCH_* in ``back_dev_home/.env`` and
``minio_handler/minio_config.py``, ``cp office_example.py office.py``, set
``SKEWNONO_MSR_FILE_PROVIDER=office``, then run the Verify command in
MIGRATION.md.
"""

import hashlib
import logging
import math
from statistics import fmean, pstdev
from typing import Any

from back_dev_home.ebeam._office_meas_hist import (
    ALL_INDICES as _ALL_INDICES,
    search as _os_search,
    text as _text,
)
from back_dev_home.msr_file.contracts import (
    AlignmentInfo,
    ExeDetailInfo,
    FdcParamSummary,
    MsrFileResponse,
    MsrFileRow,
    MsrParamSummary,
    SpmDict,
)
# Cross-phase single sources: the FDC catalog (nominal/sigma/unit/category),
# the ok/warning/bad thresholds, and the per-parameter CD summaries all come
# from mock.py so Phase 1/2 can never disagree on what the numbers mean.
from back_dev_home.msr_file.providers.mock import (
    DYNAMIC_FDC_SPECS,
    FDC_BAD_SIGMA,
    FDC_CATEGORY_LABELS,
    _fdc_status,
    _summaries,
)


__all__ = ["get_msr_file", "build_response"]

_log = logging.getLogger(__name__)

_MSR_KW = "msr.keyword"

# Names a real revision might hide under in the pickle's exe_detail_info.
# Checked in order; extend at the office if the pipeline uses another key.
_REVISION_KEYS = ("recipe_revision", "revision", "recipe_rev", "rev_no")

_TRANSFORM_TAG = "minio-pkl-v1"


# ── scalar coercion (pickle values arrive as str/float/None/"None") ─────────


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _int_or_none(value: Any) -> int | None:
    text = _text(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _float_or_none(value: Any) -> float | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    return parsed if math.isfinite(parsed) else None


def _float_list(value: Any) -> list[float]:
    if not isinstance(value, (list, tuple)):
        return []
    out: list[float] = []
    for item in value:
        parsed = _float_or_none(item)
        if parsed is not None:
            out.append(parsed)
    return out


# ── fetchers (network — kept thin so build_response stays pure) ─────────────


def _find_parent(msr: str) -> dict[str, Any] | None:
    """The meas_hist _source for this MSR — searched across BOTH aliases."""
    body = {
        "query": {"bool": {"filter": [{"term": {_MSR_KW: msr}}]}},
        "size": 1,
    }
    hits = _os_search(_ALL_INDICES).search_raw(body).get("hits", {}).get("hits", [])
    return hits[0].get("_source", {}) if hits else None


def _fetch_payload(minio_pkl: str) -> Any:
    """Fetch the pickle at ``minio_pkl`` from the configured bucket.

    ``minio_pkl`` is a key RELATIVE TO the configured ``PREFIX``, not a
    ``"bucket/key"`` pair — office-confirmed 2026-07-22: the stored
    ``hitachi_sem/...`` resolves to ``user/2067928/hitachi_sem/...``. Its
    leading segment is a folder, and handing that to the client as a bucket
    fails with ``InvalidBucketName`` because S3 forbids underscores. Bucket
    and prefix both come from ``minio_config.py``, which is exactly what
    passing the bare key to a default-constructed client does.
    """
    # Lazy import: MinIO config is resolved at call time, module import stays
    # side-effect free (mirrors health/providers/office_example.py).
    from minio_handler import MinioObject

    return MinioObject().get_pickle(minio_pkl.lstrip("/"))


# ── normalization: pickle payload -> contract shapes ────────────────────────


def _records(df_result_data: Any) -> list[dict[str, Any]]:
    """df_result_data rows as dicts with NORMALIZED keys.

    The pickle's DataFrame columns use spaces ("mp_image_name 01",
    "meas_condition mag") — docs/datatables/msr_file_pickle.txt. Keys are
    lowercased and space->underscore so the row builder reads one spelling.
    Accepts a DataFrame or an already-listified payload.
    """
    if hasattr(df_result_data, "to_dict"):
        raw = df_result_data.to_dict(orient="records")
    elif isinstance(df_result_data, list):
        raw = df_result_data
    else:
        raw = []
    return [
        {str(key).strip().lower().replace(" ", "_"): value for key, value in rec.items()}
        for rec in raw
        if isinstance(rec, dict)
    ]


def _mp_image_names(rec: dict[str, Any]) -> list[str]:
    """Every ``mp_image_name NN`` column of one row, in NN order, empties dropped.

    The pickle numbers the columns 01..NN (as many as ``no_of_mp_image``).
    CD-SEM rows populate one; HV-SEM tools shoot several images per targeting
    point and populate 01, 02, 03, ... with stem-suffixed names
    (e.g. S04_M0004-01MP-U.jpeg / -T / -M / -L, sometimes .tif only —
    user-confirmed 2026-08-08). Until 2026-08-08 ``_row`` read only the 01
    column, which is why 스큐보아 could not show any non-first HV-SEM image.
    """
    named: list[tuple[int, str]] = []
    for key, value in rec.items():
        tail = str(key).removeprefix("mp_image_name_")
        if tail == str(key) or not tail.isdigit():
            continue
        name = _text(value)
        if name:
            named.append((int(tail), name))
    return [name for _, name in sorted(named)]


def _row(msr: str, rec: dict[str, Any]) -> MsrFileRow:
    meas_kind = _text(rec.get("meas_kind")) or None
    return MsrFileRow(
        msr=msr,
        sequence=_int(rec.get("sequence")),
        chip_number=_text(rec.get("chip_number")),
        # Contract gap: the office pickle has no chip_coordinate column
        # (msr_file_pickle.txt) — "" when absent, mirroring other unmapped
        # office fields (e.g. meas_hist lot_cd).
        chip_coordinate=_text(rec.get("chip_coordinate")),
        stage_coordinate=_text(rec.get("stage_coordinate")),
        dnum_group=_text(rec.get("dnum_group")),
        mp_number=_int(rec.get("mp_number"), default=-1),
        parameter=_text(rec.get("parameter")),
        cd_value=_float_or_none(rec.get("cd_value")),
        no_of_mp_image=_int(rec.get("no_of_mp_image")),
        mp_image_name_01=_text(rec.get("mp_image_name_01")),
        mp_image_names=_mp_image_names(rec),
        meas_condition_mag=_int(rec.get("meas_condition_mag")),
        meas_condition_vac=_int(rec.get("meas_condition_vac")),
        meas_condition_pixel=_text(rec.get("meas_condition_pixel")),
        addressing1_score=_int_or_none(rec.get("addressing1_score")),
        addressing2_score=_int_or_none(rec.get("addressing2_score")),
        measurement_score=_int_or_none(rec.get("measurement_score")),
        meas_method=_text(rec.get("meas_method")),
        object_type=_text(rec.get("object")),  # `object` shadows the builtin
        meas_kind=meas_kind,
    )


def _site_layout_hash(exe: ExeDetailInfo, rows: list[MsrFileRow]) -> str:
    sites = sorted({(r["chip_number"], r["dnum_group"], r["mp_number"]) for r in rows})
    basis = "|".join([
        exe["chip_array"],
        exe["chip_pitch"],
        exe["wafer_size"],
        exe["map_origin"],
        *[f"{chip}:{dnum}:{mp}" for chip, dnum, mp in sites],
    ])
    return "sl-" + hashlib.sha1(basis.encode()).hexdigest()[:16]


def _recipe_revision(exe_raw: dict[str, Any], exe: ExeDetailInfo, layout_hash: str, rows: list[MsrFileRow]) -> str:
    for key in _REVISION_KEYS:
        real = _text(exe_raw.get(key))
        if real:
            return real
    params = sorted({r["parameter"] for r in rows if r["parameter"]})
    basis = "|".join([exe["recipe_name"], exe["idp_name"], exe["idw_name"], layout_hash, *params])
    return "fp-" + hashlib.sha1(basis.encode()).hexdigest()[:12]


def _exe_detail(
    exe_raw: dict[str, Any],
    parent: dict[str, Any],
    rows: list[MsrFileRow],
    class_name: str,
) -> ExeDetailInfo:
    exe = ExeDetailInfo(
        class_name=_text(exe_raw.get("class")) or class_name,  # `class` is a keyword
        recipe_name=_text(exe_raw.get("recipe_name")) or _text(parent.get("recipe_name")),
        idp_name=_text(exe_raw.get("idp_name")) or _text(parent.get("idp_name")),
        lot_id=_text(exe_raw.get("lot_id")) or _text(parent.get("lot_id")),
        process=_text(exe_raw.get("process")),
        wafer_id=_text(exe_raw.get("wafer_id")),
        idw_name=_text(exe_raw.get("idw_name")) or _text(parent.get("idw_name")),
        chip_array=_text(exe_raw.get("chip_array")),
        chip_pitch=_text(exe_raw.get("chip_pitch")),
        wafer_size=_text(exe_raw.get("wafer_size")),
        map_offset=_text(exe_raw.get("map_offset")),
        map_origin=_text(exe_raw.get("map_origin")),
    )
    layout_hash = _site_layout_hash(exe, rows)
    exe["site_layout_hash"] = layout_hash
    exe["recipe_revision"] = _recipe_revision(exe_raw, exe, layout_hash, rows)
    exe["coordinate_transform_version"] = (
        _text(exe_raw.get("coordinate_transform_version")) or _TRANSFORM_TAG
    )
    exe["sequence_timestamp"] = (
        _text(parent.get("start_time")) or _text(parent.get("timestamp"))
    )
    return exe


def _alignment(raw: Any) -> AlignmentInfo:
    raw = raw if isinstance(raw, dict) else {}
    image_file = raw.get("image_file") if isinstance(raw.get("image_file"), dict) else {}
    offset = raw.get("offset") if isinstance(raw.get("offset"), dict) else {}
    score = raw.get("score") if isinstance(raw.get("score"), dict) else {}
    return AlignmentInfo(
        image_file={str(k): _text(v) for k, v in image_file.items()},
        offset={
            str(k): [_text(item) for item in v] if isinstance(v, (list, tuple)) else []
            for k, v in offset.items()
        },
        score={str(k): _text(v) for k, v in score.items()},
    )


def _spm(raw: Any) -> SpmDict:
    raw = raw if isinstance(raw, dict) else {}
    return SpmDict(
        vave=_float_list(raw.get("vave")),
        Vol=_float_list(raw.get("Vol")),
        wf_len=_float_list(raw.get("wf_len")),
    )


def _fdc(
    payload: dict[str, Any],
) -> tuple[dict[str, float], dict[str, dict[str, float]], list[FdcParamSummary]]:
    """Pass real FDC values through; summarize the CATALOGED dynamic params.

    fixed_fdc/dynamic_fdc carry EVERY numeric value the pickle has ("so many
    parameters" — msr_file_pickle.txt), so charts lose nothing. Summary rows
    (nominal / drift_sigma / status) are only meaningful against a baseline,
    and DYNAMIC_FDC_SPECS is the shared baseline catalog — params without a
    catalog entry get raw values but no verdict, rather than a fabricated
    nominal. Extend the catalog in mock.py as office baselines are agreed.
    """
    fixed_raw = payload.get("fixed_fdc")
    fixed_fdc: dict[str, float] = {}
    if isinstance(fixed_raw, dict):
        for name, value in fixed_raw.items():
            parsed = _float_or_none(value)
            if parsed is not None:
                fixed_fdc[str(name)] = parsed

    dynamic_raw = payload.get("dynamic_fdc")
    dynamic_fdc: dict[str, dict[str, float]] = {}
    if isinstance(dynamic_raw, dict):
        for seq, params in dynamic_raw.items():
            if not isinstance(params, dict):
                continue
            clean: dict[str, float] = {}
            for name, value in params.items():
                parsed = _float_or_none(value)
                if parsed is not None:
                    clean[str(name)] = parsed
            if clean:
                dynamic_fdc[str(seq)] = clean

    # One pass over the sequences, keyed by param, instead of re-walking every
    # sequence per cataloged param. Order is not kept: the summary stats below
    # (mean/std/min/max) are all order-invariant, so sorting here would be dead
    # work that also implies `values` is a time series when nothing treats it
    # as one. Sort at the point of use if a slope metric is ever added.
    by_name: dict[str, list[float]] = {}
    for params in dynamic_fdc.values():
        for name, value in params.items():
            by_name.setdefault(name, []).append(value)

    summaries: list[FdcParamSummary] = []
    for name, spec in DYNAMIC_FDC_SPECS.items():
        values = by_name.get(name)
        if not values:
            continue
        mean = fmean(values)
        std = pstdev(values) if len(values) > 1 else 0.0
        drift_sigma = spec.drift_sigma(mean)
        summaries.append(FdcParamSummary(
            name=name,
            category=spec.category,
            category_label=FDC_CATEGORY_LABELS[spec.category],
            unit=spec.unit,
            nominal=spec.nominal,
            mean=round(mean, 3),
            std=round(std, 3),
            min=round(min(values), 3),
            max=round(max(values), 3),
            drift_sigma=drift_sigma,
            status=_fdc_status(drift_sigma),
        ))
    return fixed_fdc, dynamic_fdc, summaries


def build_response(
    msr: str,
    parent: dict[str, Any],
    payload: dict[str, Any],
    class_name: str | None = None,
    total_images: int | None = None,
) -> MsrFileResponse:
    """Pure pickle-payload -> MsrFileResponse normalization (no network).

    Tracked-template testable: tests/test_office_template.py feeds a synthetic
    payload through this exact function, so key renames and the gated-metadata
    derivations are pinned at home before the office ever runs it.
    """
    resolved_class = (
        (class_name or "").strip()
        or _text(payload.get("exe_detail_info", {}).get("class") if isinstance(payload.get("exe_detail_info"), dict) else "")
        or _text(parent.get("class_name"))
    )
    rows = [_row(msr, rec) for rec in _records(payload.get("df_result_data"))]
    sequences = sorted({row["sequence"] for row in rows})

    fixed_fdc, dynamic_fdc, fdc_params = _fdc(payload)
    # One row is one measurement and dynamic_fdc holds that measurement's tool
    # state keyed by that row's sequence, so the two must agree on IDENTITY,
    # not just count. Office-confirmed 2026-07-27
    # (docs/datatables/msr_file_pickle.txt). This has to be a SET comparison,
    # not len(rows) != len(dynamic_fdc): the frontend's scoped FDC axis
    # (utils/skewvoirAnalysis/sequence.ts) builds fdcBySeq — and derives
    # fdcKeys, which gates whether any FDC pane renders at all — from entries
    # keyed by the on-axis sequence set. A payload with the right COUNT but
    # the wrong SET of keys (off-by-one keying, a re-indexed pipeline, dummy
    # rows keyed differently) would pass a count check silently and then
    # render "FDC 없음" for a measurement that actually has FDC data. Warn
    # rather than raise: a diagnosable data fault should be named in the log,
    # not turned into a 500 for the whole page. The frontend surfaces the
    # same mismatch as a badge (SequenceModel.integrity).
    expected = {str(r["sequence"]) for r in rows}
    actual = set(dynamic_fdc)
    if expected != actual:
        _log.warning(
            "msr_file %s: dynamic_fdc keys do not match the row sequences — "
            "%d rows, %d dynamic_fdc entries, %d rows without an entry, %d entries without a row",
            msr, len(rows), len(dynamic_fdc),
            len(expected - actual), len(actual - expected),
        )
    # Office health is DERIVED from the telemetry it summarizes: the worst
    # drift, scaled so 3.5 sigma (the "bad" threshold) saturates to 1.0 — the
    # same [0, 1] reading the mock's synthetic scalar feeds the UI.
    worst = max((s["drift_sigma"] for s in fdc_params), default=0.0)
    health = round(min(1.0, worst / FDC_BAD_SIGMA), 3)

    exe_raw = payload.get("exe_detail_info")
    exe_raw = exe_raw if isinstance(exe_raw, dict) else {}

    return MsrFileResponse(
        msr=msr,
        class_name=resolved_class,
        # The meas_hist _source carries eqp_ip (docs/datatables/meas_hist.txt),
        # and _find_parent returns the whole _source — so the tool address the
        # msr_image FTP session needs rides along at no extra query.
        eqp_ip=_text(parent.get("eqp_ip")),
        # The caller's value wins when it gave one, with the parent row as the
        # fallback -- the mock's precedence. This used to be the other way
        # round, so the skewvoir UI could pass total_images from the row it had
        # selected and have the parent lookup silently override it, making the
        # parameter decorative office-side and load-bearing at home.
        # The caller's value wins when it gave one, with the parent row as the
        # fallback -- the mock's precedence. This used to be the other way
        # round, so the skewvoir UI could pass total_images from the row it had
        # selected and have the parent lookup silently override it, making the
        # parameter decorative office-side and load-bearing at home.
        total_images=(
            total_images
            if total_images is not None
            else _int(parent.get("total_images"), default=0)
        ),
        sequence_count=sequences[-1] if sequences else 0,
        health=health,
        parameters=_param_summaries(rows),
        fdc_params=fdc_params,
        fixed_fdc=fixed_fdc,
        dynamic_fdc=dynamic_fdc,
        exe_detail_info=_exe_detail(exe_raw, parent, rows, resolved_class),
        alignment=_alignment(payload.get("alignment")),
        spm_dict=_spm(payload.get("spm_dict")),
        total=len(rows),
        rows=rows,
    )


def _param_summaries(rows: list[MsrFileRow]) -> list[MsrParamSummary]:
    # mock._summaries is the shared stats implementation (measured-rows-only
    # gate, sample stdev matching the frontend) — see its docstring.
    return _summaries(rows)


# ── Endpoints ────────────────────────────────────────────────────────────────


def get_msr_file(
    msr: str,
    class_name: str | None = None,
    total_images: int | None = None,
) -> MsrFileResponse | None:
    msr = (msr or "").strip()
    if not msr:
        return None

    parent = _find_parent(msr)
    if parent is None:
        return None  # unknown MSR -> route 404s, same as the mock

    minio_pkl = _text(parent.get("minio_pkl"))
    if not minio_pkl:
        # msr_check "No" rows have no stored file; 404 is the honest answer.
        return None

    payload = _fetch_payload(minio_pkl)
    if not isinstance(payload, dict):
        return None

    return build_response(msr, parent, payload, class_name, total_images)


if __name__ == "__main__":
    # Standalone smoke test — run FROM THE REPO ROOT with:
    #     .venv/bin/python -m back_dev_home.msr_file.providers.office
    # Finds a recent doc that has a minio_pkl path, fetches its pickle, and
    # prints the normalized response's shape.
    body = {
        "query": {"bool": {"filter": [{"exists": {"field": "minio_pkl"}}]}},
        "sort": [{"timestamp": "desc"}],
        "size": 1,
    }
    hits = _os_search(_ALL_INDICES).search_raw(body).get("hits", {}).get("hits", [])
    if not hits:
        raise SystemExit("no meas_hist doc with a minio_pkl path — check ingestion")

    probe_src = hits[0].get("_source", {})
    probe_msr = _text(probe_src.get("msr"))
    probe_path = _text(probe_src.get("minio_pkl"))
    print(f"probe msr: {probe_msr!r}")

    # Print where we are actually going to look. The stored path is a KEY, not
    # a bucket/key pair — if this ever regresses to splitting on "/", the
    # bucket line below shows a folder name and MinIO answers InvalidBucketName.
    print(f"minio_pkl (stored): {probe_path!r}")
    try:
        from minio_handler import MinioObject

        probe_key = probe_path.lstrip("/")
        _probe_store = MinioObject()
        # NOTE: MinioObject(prefix=None) does NOT disable the prefix — the
        # constructor reads None as "use the configured default". Only
        # prefix="" or .use_prefix(None) clears it. Getting this wrong makes
        # the two lines below silently measure the same thing.
        _unprefixed = MinioObject(prefix="")
        print(f"  configured bucket : {_probe_store.default_bucket!r}")
        print(f"  configured prefix : {_probe_store.default_prefix!r}")
        print(f"  resolved key      : {_probe_store._resolve_key(probe_key)!r}")
        print(f"  exists (prefixed) : {_probe_store.exists(probe_key)}")
        # The raw line often CANNOT be answered at the office: credentials are
        # scoped to the user prefix (user/<id>/...), and S3 answers AccessDenied
        # (not NotFound) for keys outside the grant — office-confirmed
        # 2026-07-24. That denial is itself the expected answer, so report it
        # per-line instead of letting it mask the successful probes above.
        try:
            print(f"  exists (raw)      : {_unprefixed.exists(probe_key)}")
        except Exception as raw_exc:
            print(
                f"  exists (raw)      : unanswerable"
                f" ({type(raw_exc).__name__}: key outside the granted prefix?)"
            )
    except Exception as exc:  # diagnostics only — never block the smoke test
        print(f"  (minio probe unavailable: {type(exc).__name__}: {exc})")

    result = get_msr_file(probe_msr)
    if result is None:
        raise SystemExit("get_msr_file returned None for a doc that has minio_pkl")

    exe = result["exe_detail_info"]
    print(f"rows={result['total']}  sequences={result['sequence_count']}  health={result['health']}")
    print(f"parameters: {[p['parameter'] for p in result['parameters']]}")
    print(f"fdc summaries: {[(s['name'], s['status']) for s in result['fdc_params']]}")
    print(f"dynamic_fdc params (raw): {sorted({k for v in result['dynamic_fdc'].values() for k in v})[:10]}")
    print("gated metadata:")
    for key in ("site_layout_hash", "recipe_revision", "coordinate_transform_version", "sequence_timestamp"):
        print(f"  {key} = {exe.get(key)!r}")
    missing = [k for k in ("site_layout_hash", "recipe_revision", "coordinate_transform_version", "sequence_timestamp") if not exe.get(k)]
    print("gate:", "OK" if not missing else f"MISSING {missing}")
