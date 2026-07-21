"""Authentication error handlers."""

import re
from collections.abc import Callable

from databricks_web_app.error_handlers.components import (
    RichErrorDialogBase,
    RichErrorDialogConfig,
)

import jwt
import requests


class TokenExpiredErrorDialog(RichErrorDialogBase):
    """Rich modal dialog for expired data-token errors."""

    def matches(self, exception: BaseException) -> bool:
        """Catch the error if the data token has expired."""
        return (
            isinstance(exception, jwt.exceptions.ExpiredSignatureError)
            and str(exception) == "Token for data has expired."
        )

    def build_dialog_config(
        self,
        exception: BaseException,
        on_close: Callable[[], None] | None = None,
    ) -> RichErrorDialogConfig:
        """Build dialog content for an expired data token."""
        return RichErrorDialogConfig(
            title="Data token expired",
            description=(
                "The token used to query data has expired. Reload this page "
                "to start a new session."
            ),
            traceback_text=self.format_traceback(exception),
            on_close=on_close,
        )


class ClientSecretExpiredErrorDialog(RichErrorDialogBase):
    """Rich modal dialog for expired client-secret errors."""

    def matches(self, exception: BaseException) -> bool:
        """Catch the error if the client secret has expired."""
        return (
            isinstance(exception, requests.exceptions.HTTPError)
            and re.fullmatch(
                r"401 Client Error: Unauthorized for url: "
                r"https://login\.microsoftonline\.com/"
                r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/oauth2/v2\.0/token",
                str(exception),
            )
            is not None
        )

    def build_dialog_config(
        self,
        exception: BaseException,
        on_close: Callable[[], None] | None = None,
    ) -> RichErrorDialogConfig:
        """Build dialog content for an expired client secret."""
        return RichErrorDialogConfig(
            title="Data access cannot be refreshed",
            description=(
                "The token used to query the tools tables cannot be refreshed "
                "because the corresponding client secret expired."
            ),
            instruction_title="How to resolve",
            instructions=["Ask an administrator to redeploy this app."],
            traceback_text=self.format_traceback(exception),
            on_close=on_close,
        )
