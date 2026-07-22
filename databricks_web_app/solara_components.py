"""Solara integration helpers for OAuth/Databricks authenticated apps."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Optional

from databricks_web_app import AppConfig
from databricks_web_app.error_handlers import (
    ClientSecretExpiredErrorDialog,
    DatabricksInvalidAccessTokenErrorDialog,
    DatabricksPermissionErrorDialog,
    GenericApplicationErrorDialog,
    RichErrorDialogBase,
    TokenExpiredErrorDialog,
)

import solara


@dataclass(frozen=True)
class _SolaraUserInfo:
    """User information derived from OAuth/reverse-proxy headers."""

    oid: str
    email: str
    name: str
    short_name: str


_ERROR_DIALOG_HANDLER_TYPES: tuple[type[RichErrorDialogBase], ...] = (
    TokenExpiredErrorDialog,
    ClientSecretExpiredErrorDialog,
    DatabricksInvalidAccessTokenErrorDialog,
    DatabricksPermissionErrorDialog,
    GenericApplicationErrorDialog,
)
"""Handler order matters:
- Specific handlers must run before broad handlers.
- Authentication/token handlers run first because their messages can overlap
  with Databricks access failures.
- Databricks permission handlers run before the generic fallback so known
  user-facing access errors get targeted guidance.
- GenericApplicationErrorDialog must stay last because it matches every
  otherwise unhandled exception.
"""


def _jwt_payload(token: str) -> dict[str, Any]:
    """Decode JWT payload without checking the signature."""
    if not token:
        return {}

    parts = token.split(".")
    if len(parts) < 2:
        return {}

    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    payload = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))

    return json.loads(payload.decode("utf-8"))


def _get_solara_user_info(
    default_email: Optional[str] = None,
) -> _SolaraUserInfo:
    """Extract user information from Solara request headers."""
    if default_email is None:
        default_email = "mail@example.de"

    header_values = solara.lab.headers.value or {}  # type: ignore[attr-defined]

    email = default_email
    oid = ""

    mail_values = header_values.get("x-email")
    if mail_values:
        email = mail_values[0]

    access_tokens = header_values.get("x-access-token")
    if access_tokens:
        claims = _jwt_payload(access_tokens[0])
        oid = claims.get("oid", "")

    local_part = email.split("@", maxsplit=1)[0]
    name_parts = [part for part in local_part.split(".") if part]

    name = " ".join(part.capitalize() for part in name_parts)
    short_name = _build_short_name(name_parts=name_parts, fallback=local_part)

    return _SolaraUserInfo(
        oid=oid,
        email=email,
        name=name,
        short_name=short_name,
    )


def _build_short_name(name_parts: list[str], fallback: str) -> str:
    """Build a short display name from email-local-part components."""
    if len(name_parts) >= 2 and len(name_parts[0]) >= 2 and len(name_parts[1]) >= 2:
        return (
            name_parts[0][0].upper()
            + name_parts[0][1].lower()
            + name_parts[1][0].upper()
            + name_parts[1][1].lower()
        )

    return fallback[:4].capitalize()


@dataclass(frozen=True)
class SolaraUserInfoBinding:
    """App-owned state setters used to store authenticated user metadata.

    The connector owns header parsing and user-info normalization. The app only
    provides setter callbacks for the state it wants populated.

    Attributes:
        set_user_id: Stores the OAuth object ID claim.
        set_user_email: Stores the authenticated user's email address.
        set_user_name: Stores a display name derived from the email local part.
        set_user_short_name: Stores a compact display name for UI elements.
    """

    set_user_id: Callable[[str], None]
    set_user_email: Callable[[str], None]
    set_user_name: Callable[[str], None]
    set_user_short_name: Callable[[str], None]


def set_solara_user_info(
    binding: SolaraUserInfoBinding,
    default_email: Optional[str] = None,
) -> None:
    """Populate app-owned user state from Solara request headers.

    The function reads OAuth/reverse-proxy metadata from the current Solara
    request headers, normalizes it into a stable user-info structure, and writes
    the values through the provided app-owned setter callbacks.

    ``default_email`` is used when no email header is available, for example in
    local development or unauthenticated test runs.
    """
    info = _get_solara_user_info(default_email=default_email)

    binding.set_user_id(info.oid)
    binding.set_user_email(info.email)
    binding.set_user_name(info.name)
    binding.set_user_short_name(info.short_name)


class OAuthDatabricksErrorBoundaryController:
    """Dispatch exceptions to configured OAuth/Databricks error handlers."""

    def __init__(
        self,
        app_config: AppConfig,
        handler_types: tuple[type[RichErrorDialogBase], ...] = (
            _ERROR_DIALOG_HANDLER_TYPES
        ),
    ) -> None:
        """Construct ordered error-handler instances."""
        self.handlers = tuple(
            handler_type(app_config) for handler_type in handler_types
        )

    def render_known_error_or_raise(
        self,
        exception: BaseException,
        on_close: Callable[[RichErrorDialogBase], None],
    ) -> None:
        """Render a matching rich error dialog or re-raise the exception."""
        for handler in self.handlers:
            if handler.handle_exception(exception, on_close):
                return

        raise exception


@solara.component
def OAuthDatabricksErrorBoundary(  # pylint: disable=invalid-name
    children: Callable[[], solara.Element],
    fallback: Callable[[], solara.Element],
    on_clearable_error_close: Callable[[], None],
    app_config: AppConfig,
    user_info_binding: SolaraUserInfoBinding | None = None,
    default_email: Optional[str] = None,
) -> None:
    """Render content behind an OAuth/Databricks-aware Solara boundary.

    The boundary has two responsibilities:

    1. Initialize authenticated user metadata once for the current rendered
       page, if ``user_info_binding`` is provided.
    2. Catch render-time exceptions from ``children`` and display known
       OAuth/Databricks errors as rich modal dialogs.

    While an exception is active, ``fallback`` is rendered instead of
    ``children`` so the page keeps a stable layout behind the modal.

    If the matched dialog is marked as clearable, closing it calls
    ``on_clearable_error_close`` and then clears the captured exception.

    Example dashboard.py framework:

        .. code-block:: python
            # user information (import from Visualization)
            user_id = solara.Reactive("")
            user_name = solara.Reactive("")
            user_short_name = solara.Reactive("")
            user_email = solara.Reactive("")

            @solara.component
            def DashboardContent():
                return

            @solara.component
            def DashboardLayout(skip_main_content: bool = False):
                return

            # ---


            def reset_invalid_dashboard_state() -> None:
                "Reset app-specific invalid selection state after clearable errors."
                ...
                refresh_frontend()

            @solara.component
            def Page():
                # Place Header here

                DashboardErrorOverlayBoundary()

                # Place PopUps, Footer, PageStyling here


            @solara.component
            def DashboardErrorOverlayBoundary():
                "Render dashboard content behind OAuth/Databricks error handling."
                OAuthDatabricksErrorBoundary(
                    children=DashboardContent, # Main dashboard content
                    # This is the fallback layout or when an error
                    fallback=lambda: DashboardLayout(skip_main_content=True),
                    # Reset invalid dashboard state
                    on_clearable_error_close=reset_invalid_dashboard_state,
                    app_config=AppConfig(),
                    user_info_binding=SolaraUserInfoBinding(
                        set_user_id=user_id.set,
                        set_user_email=user_email.set,
                        set_user_name=user_name.set,
                        set_user_short_name=user_short_name.set,
                    ),
                    default_email="user@example.com")

    Arguments:
        children: The content to render when no exception is active.
        fallback: The content to render when an exception is active.
        on_clearable_error_close: Callback to run when an error dialog is closed.
        app_config: AppConfig instance containing OAuth/Databricks configuration.
        user_info_binding: Optional app-owned state setter callbacks for user metadata.
        default_email: Optional default email address to use when no email header
                       is available.
    """
    exception, clear_exception = solara.use_exception()
    show_error_dialog, set_show_error_dialog = solara.use_state(True)
    controller = OAuthDatabricksErrorBoundaryController(app_config)

    def initialize_user_info() -> None:
        if user_info_binding is None:
            return

        set_solara_user_info(
            binding=user_info_binding,
            default_email=default_email,
        )

    solara.use_effect(initialize_user_info, dependencies=[])

    def close_error_dialog(error_handler: RichErrorDialogBase) -> None:
        set_show_error_dialog(False)

        if not error_handler.clear_exception_on_close:
            return

        on_clearable_error_close()
        clear_exception()

    if exception:
        fallback()

        if show_error_dialog:
            controller.render_known_error_or_raise(
                exception=exception,
                on_close=close_error_dialog,
            )
        return

    if not show_error_dialog:
        set_show_error_dialog(True)

    children()
