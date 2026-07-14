"""Stable Python contract for SEM equipment rows."""

from typing import Literal, TypedDict


__all__ = ["SemListRow"]


class SemListRow(TypedDict):
    fac_id: str
    eqp_id: str
    eqp_model_cd: str
    eqp_grp_id: str
    vendor_nm: Literal["HITACHI", "AMAT"]
    eqp_ip: str
    fab_name: str
    updt_dt: str
    available: Literal["On", "Off"]
    version: int
