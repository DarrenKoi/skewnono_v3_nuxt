"""Pure FTP path assembly + tool-IP validation (no network, no phase)."""

import ipaddress
from pathlib import PurePosixPath

from back_dev_home.msr_image.errors import InvalidToolIp

_ROOT = "/HITACHI/DEVICE/HD"


def image_dir(class_name: str, msr: str) -> str:
    return f"{_ROOT}/{class_name}/images/{msr}"


def image_path(class_name: str, msr: str, name: str) -> str:
    return f"{image_dir(class_name, msr)}/{name}"


def cond_path(image_path_str: str) -> str:
    """Hidden per-image sidecar: /dir/foo.jpeg -> /dir/.foo.jpeg/cond.txt."""
    p = PurePosixPath(image_path_str)
    return str(p.with_name(f".{p.name}") / "cond.txt")


def validate_tool_ip(ip: str, allowed_subnets: list[str] | None = None) -> str:
    """Return ``ip`` if it is a well-formed IPv4 (and, when a subnet allowlist
    is given, inside it). Raise InvalidToolIp otherwise. The backend opens an
    FTP session to whatever the client sends, so this is the SSRF guard."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError as exc:
        raise InvalidToolIp(f"not an IP address: {ip!r}") from exc
    if not isinstance(addr, ipaddress.IPv4Address):
        raise InvalidToolIp(f"not an IPv4 address: {ip!r}")
    if allowed_subnets:
        for cidr in allowed_subnets:
            if addr in ipaddress.ip_network(cidr.strip(), strict=False):
                return ip
        raise InvalidToolIp(f"IP outside allowed subnets: {ip!r}")
    return ip
