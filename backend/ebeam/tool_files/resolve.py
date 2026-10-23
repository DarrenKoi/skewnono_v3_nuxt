"""Which tool a request means, and how to log in to it. PURE over rows.

Everything comes from ONE sem_list row: the IP, the fab, the model and the
account. Taking the IP from the client or the account from a second roster read
is how credentials end up sent to the wrong host.
"""

import ipaddress
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from backend.ebeam._tool_specs import SLUG_TO_TOOL_TYPE, model_to_tool_type
from backend.ebeam.tool_files.errors import ToolFilesError
from backend.msr_image.config import ImageConfig
from backend.msr_image.ftp_accounts import account_for


@dataclass(frozen=True, slots=True)
class Tool:
    eqp_id: str
    fab_name: str
    tool_type: str
    host: str
    user: str
    password: str
    port: int
    timeout: float
    encoding: str
    # "tool" (eqp_ip) or "data" (Provision's separate data_ip).
    role: str = "tool"


# Only Provision keeps its data on a host apart from the tool; every other
# family's tool IP is its data IP.
_DATA_HOST_FAMILIES = frozenset({"provision"})


def resolve_tool(
    rows: Iterable[Mapping[str, Any]],
    tool_slug: str,
    fab_name: str,
    eqp_id: str,
    cfg: ImageConfig,
    role: str = "tool",
) -> Tool:
    if role not in ("tool", "data"):
        raise ToolFilesError(400, "bad_request", f"host must be tool or data, not {role!r}")
    matches = [row for row in rows if row["eqp_id"] == eqp_id]
    if not matches:
        raise ToolFilesError(404, "tool_not_found", f"{eqp_id} is not in sem_list")

    # The mock roster repeats ~10 ids with different IPs; the office one may
    # repeat a row verbatim. Identical rows are one tool, anything else is a
    # coin toss this must not make.
    distinct = {(r["eqp_ip"], r["fab_name"], r["eqp_model_cd"]) for r in matches}
    if len(distinct) > 1:
        raise ToolFilesError(
            409, "tool_ambiguous", f"{eqp_id} maps to {len(distinct)} different sem_list rows"
        )
    row = matches[0]

    tool_type = model_to_tool_type(row["eqp_model_cd"])
    if tool_type != SLUG_TO_TOOL_TYPE.get(tool_slug) or row["fab_name"] != fab_name:
        raise ToolFilesError(
            400, "tool_mismatch", f"{eqp_id} is not a {tool_slug} tool in {fab_name}"
        )

    if role == "data" and tool_type not in _DATA_HOST_FAMILIES:
        raise ToolFilesError(400, "bad_request", f"{tool_slug} has no separate data host")

    try:
        host = str(ipaddress.IPv4Address(row["data_ip" if role == "data" else "eqp_ip"].strip()))
    except ValueError:
        raise ToolFilesError(
            503, "tool_unreachable", f"{eqp_id} has no usable IP in sem_list"
        ) from None

    account = account_for([row], cfg.ftp_accounts, row["eqp_ip"])
    return Tool(
        eqp_id=eqp_id,
        fab_name=fab_name,
        tool_type=tool_type,
        host=host,
        user=account.get("user", cfg.ftp_user),
        password=account.get("password", cfg.ftp_password),
        port=cfg.ftp_port,
        timeout=cfg.ftp_timeout,
        encoding=cfg.ftp_encoding,
        role=role,
    )
