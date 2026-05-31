"""Per-tool measurement spec ranges owned by the hardware feature.

The BM/PM Up gate compares a tool's post-PM CD_MONITORING value and its BSM
profile against the accepted spec window. Keeping the spec here, next to the
BM/PM and BSM mock sources, gives pm_planning one backend seam to import.
"""

import hashlib


__all__ = [
    "CD_MON_NOMINAL_NM",
    "get_cd_monitoring_spec",
    "get_spec_range",
    "get_bsm_spec",
    "bsm_in_spec",
]


CD_MON_NOMINAL_NM = 16.0
_CD_SPEC_HALF_WIDTH = 0.5

_BSM_SHARPNESS_LOWER = 7.85
_BSM_SHARPNESS_UPPER = 8.05
_BSM_NOISE_LOWER = 6.65
_BSM_NOISE_UPPER = 6.95


def _seed_for(eqp_id: str) -> int:
    digest = hashlib.md5(eqp_id.encode("utf-8")).hexdigest()
    return int(digest[:8], 16)


def get_cd_monitoring_spec(eqp_id: str) -> dict[str, float]:
    """Return that tool's CD_MONITORING target/lower/upper spec in nm."""
    offset = ((_seed_for(eqp_id) % 21) - 10) / 100.0
    target = round(CD_MON_NOMINAL_NM + offset, 3)
    return {
        "target": target,
        "lower": round(target - _CD_SPEC_HALF_WIDTH, 3),
        "upper": round(target + _CD_SPEC_HALF_WIDTH, 3),
    }


def get_bsm_spec() -> dict[str, float]:
    """Return the fleet-wide BSM acceptance band."""
    return {
        "sharpness_lower": _BSM_SHARPNESS_LOWER,
        "sharpness_upper": _BSM_SHARPNESS_UPPER,
        "noise_lower": _BSM_NOISE_LOWER,
        "noise_upper": _BSM_NOISE_UPPER,
    }


def get_spec_range(eqp_id: str) -> dict[str, dict[str, float]]:
    """Return all pm-planning spec ranges for one tool."""
    return {
        "cd_monitoring": get_cd_monitoring_spec(eqp_id),
        "bsm": get_bsm_spec(),
    }


def bsm_in_spec(sharpness_avg: float, noise_avg: float) -> bool:
    spec = get_bsm_spec()
    return (
        spec["sharpness_lower"] <= sharpness_avg <= spec["sharpness_upper"]
        and spec["noise_lower"] <= noise_avg <= spec["noise_upper"]
    )
