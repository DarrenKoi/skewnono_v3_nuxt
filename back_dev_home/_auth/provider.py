import importlib
from typing import Optional, Protocol

from flask import Request


class IdentityProvider(Protocol):
    def identify(self, request: Request) -> Optional[str]: ...
    def login_redirect_url(self, request: Request, next_path: str) -> Optional[str]: ...


class LocalIdentityProvider:
    """Local/home dev: reuse the LASTUSER cookie pattern from afm/routes.py."""

    def identify(self, request: Request) -> Optional[str]:
        return (
            request.cookies.get("LASTUSER")
            or request.cookies.get("LAST_USER")
            or "local-dev"
        )

    def login_redirect_url(self, request: Request, next_path: str) -> Optional[str]:
        return None


def _load_sso_class():
    """Return the cloud image's confirmed SSO class."""
    module_path = "hcputil.auth.sso"
    try:
        return importlib.import_module(module_path).SSO
    except ImportError as exc:
        raise ImportError(
            f"{module_path} is not importable; "
            "the cloud image must provide this SSO module."
        ) from exc


class CloudIdentityProvider:
    """Cloud production: validate via the cloud image's hcputil SSO. Imported
    lazily because hcputil is provided only by the cloud image."""

    _ID_ATTRS = ("user_id", "member_id", "userId", "memberId", "id")

    def __init__(self) -> None:
        self._SSO_cls = _load_sso_class()

    def _sso(self, request: Request):
        return self._SSO_cls(request)

    def identify(self, request: Request) -> Optional[str]:
        try:
            sso = self._sso(request)
        except Exception:
            return None
        for attr in self._ID_ATTRS:
            value = getattr(sso, attr, None)
            if value:
                return str(value)
        return None

    def login_redirect_url(self, request: Request, next_path: str) -> Optional[str]:
        try:
            sso = self._sso(request)
        except Exception:
            return None
        base = str(getattr(sso, "redirect_url", "")).rstrip("/")
        if not base:
            return None
        suffix = next_path if next_path.startswith("/") else f"/{next_path}"
        return f"{base}{suffix}"
