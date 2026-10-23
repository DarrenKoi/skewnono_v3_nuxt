"""Stable Python contracts for SEM equipment rows."""

from typing import Literal, TypedDict


__all__ = ["PendingToolRow", "ProvisionFields", "SemListRow"]


class ProvisionFields(TypedDict, total=False):
    """Present on PROVISION rows only, in both the fleet and the pending list.

    A Provision's data lives on a separate data host, not the tool, so it has
    two reachabilities: the tool IP (``eqp_ip``, probed by downloading
    ``/D_drive/Qrelease/current_version.ini`` -> ``v3_df_provision_version``)
    and the data IP (``data_ip``, probed by listing the P-drive ->
    ``v3_df_provision_hosts``). Both keys call their column ``available``; they
    are renamed here so neither can be mistaken for the other.

    ``""`` in an availability means the tool is absent from that key, which
    is "not probed", not "Off". See docs/datatables/provision/provision_hosts.txt.
    """

    data_ip: str
    # Only "data-ip confirmed" is trustworthy for extraction; every other value
    # (or "" when the tool is missing from v3_df_provision_hosts) is 미연결.
    ip_note: str
    data_available: Literal["On", "Off", ""]
    tool_available: Literal["On", "Off", ""]
    # UTC ISO stamp of the last v3_df_provision_hosts run; one for all rows.
    checked_at: str


class SemListRow(ProvisionFields):
    fac_id: str
    eqp_id: str
    eqp_model_cd: str
    eqp_grp_id: str
    vendor_nm: Literal["HITACHI", "AMAT"]
    eqp_ip: str
    fab_name: str
    # ISO string. The tool's FIRST ARRIVAL time at the fab, not a roster
    # update time; imprecise for old tools, trustworthy for recent ones
    # (user-confirmed 2026-07-30).
    updt_dt: str
    available: Literal["On", "Off"]
    # Free-form string (digits + letters), e.g. "1A". "" (empty) when the
    # fleet row has no matching entry in the office version store
    # (see sem_list/MIGRATION.md).
    version: str


class PendingToolRow(ProvisionFields):
    """A tool in the company roster that skewnono cannot reach yet.

    Every tool is firewalled when it is first installed in the fab, so this
    is the normal initial state of every tool rather than a fault. A row
    leaves this list when IT opens its IP and it starts appearing in
    ``v3_df_sem_avail``.

    Deliberately NOT a widened ``SemListRow``:

    * no ``available`` / ``version`` — both come from Redis keys this tool is
      not in yet, so there is no value the office could supply and a sentinel
      would be a fiction the contract invented.
    * ``vendor_nm`` carries no ``Literal`` constraint, unlike ``SemListRow``.
      The office adapter raises on an unknown vendor for the connected fleet,
      which is right there and wrong here: this screen exists to surface tools
      we have not onboarded, so a new vendor must show up on it, not 502 it.
    """

    fac_id: str
    eqp_id: str
    eqp_model_cd: str
    eqp_grp_id: str
    vendor_nm: str
    # Always populated: assigned at fab installation (user-confirmed
    # 2026-07-30). This is the value the IT firewall request is made of.
    eqp_ip: str
    # "" when the tool has no fab assignment yet; the UI buckets those as 미배정
    # rather than dropping them.
    fab_name: str
    updt_dt: str
