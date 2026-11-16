"""Per-request authorization boundary for future Global Admin API handlers.

This module is framework-neutral because the repository currently has no
separate HTTP API router. A future route must call authorize() on every
privileged request and must supply only a Principal from trusted auth
middleware. The config loader must read protected server-side configuration.
"""
from __future__ import annotations

from collections.abc import Callable

from core.global_owner import (
    GlobalOwnerConfig,
    GlobalOwnerConfigurationError,
    require_global_owner,
)
from core.identity import AuthorizationDenied, Principal


OwnerConfigLoader = Callable[[], GlobalOwnerConfig | None]


class GlobalAdminRequestAuthorizer:
    """Re-read owner configuration and authorize every privileged request.

    No owner/config/principal decision is cached. This means a server-side
    owner re-key or configuration removal is observed by the next request,
    provided the deployment config loader itself is fresh and authoritative.
    """

    def __init__(self, config_loader: OwnerConfigLoader) -> None:
        if not callable(config_loader):
            raise TypeError("A trusted server-side owner config loader is required.")
        self._config_loader = config_loader

    def authorize(self, principal: Principal | None) -> Principal:
        """Return the trusted owner principal or deny this request.

        Configuration errors and unexpected loader failures are deliberately
        converted to a generic denial; no configuration detail is exposed to
        the API caller. The original exception is not logged here because this
        boundary has no trusted audit sink.
        """
        try:
            config = self._config_loader()
        except (GlobalOwnerConfigurationError, OSError, RuntimeError, ValueError):
            raise AuthorizationDenied("Global Admin authorization is unavailable.") from None
        if not isinstance(config, GlobalOwnerConfig):
            raise AuthorizationDenied("Global Admin authorization is unavailable.")
        try:
            return require_global_owner(principal, config)
        except (AuthorizationDenied, PermissionError, TypeError, ValueError):
            raise AuthorizationDenied("Global Admin access is denied.") from None
