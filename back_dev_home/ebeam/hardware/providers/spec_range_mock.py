"""Per-tool measurement spec ranges owned by the hardware feature.

The BM/PM Up gate compares a tool's post-PM CD_MONITORING value and its BSM
profile against the accepted spec window. Keeping the spec here, next to the
BM/PM and BSM mock sources, gives pm_planning one backend seam to import.
"""

from back_dev_home.ebeam.hardware.providers._siblings import seed_for


__all__ = [
    "CD_MON_NOMINAL_NM",
    "get_cd_monitoring_spec",
    "get_bsm_spec",
    "bsm_in_spec",
]


CD_MON_NOMINAL_NM = 16.0
_CD_SPEC_HALF_WIDTH = 0.5

_BSM_SHARPNESS_LOWER = 7.85
_BSM_SHARPNESS_UPPER = 8.05
_BSM_NOISE_LOWER = 6.65
_BSM_NOISE_UPPER = 6.95


def get_cd_monitoring_spec(eqp_id: str) -> dict[str, float]:
    """Return that tool's CD_MONITORING target/lower/upper spec in nm."""
    offset = ((seed_for(eqp_id) % 21) - 10) / 100.0
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


def bsm_in_spec(sharpness_avg: float, noise_avg: float) -> bool:
    spec = get_bsm_spec()
    return (
        spec["sharpness_lower"] <= sharpness_avg <= spec["sharpness_upper"]
        and spec["noise_lower"] <= noise_avg <= spec["noise_upper"]
    )
