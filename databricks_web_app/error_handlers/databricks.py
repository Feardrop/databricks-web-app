"""Databricks error handlers."""

import re
from collections.abc import Callable
from typing import cast

from databricks import sql

from . import (
    ErrorDetail,
    ErrorLink,
    RichErrorDialogBase,
    RichErrorDialogConfig,
)


class DatabricksInvalidAccessTokenErrorDialog(RichErrorDialogBase):
    """Rich modal dialog for invalid Databricks access-token errors."""

    def matches(self, exception: BaseException) -> bool:
        """Catch Databricks invalid access token errors."""
        message = str(exception).lower()
        exception_type = type(exception).__name__.lower()
        module_name = type(exception).__module__.lower()
        is_databricks_request_error = (
            "databricks" in module_name and "requesterror" in exception_type
        )

        return is_databricks_request_error and "invalid access token" in message

    def build_dialog_config(
        self,
        exception: BaseException,
        on_close: Callable[[], None] | None = None,
    ) -> RichErrorDialogConfig:
        """Build dialog content for an invalid Databricks access token."""
        return RichErrorDialogConfig(
            title="Databricks access token invalid",
            description=(
                "The Databricks access token is invalid and the data source "
                "cannot be queried. Make sure to use a valid access token."
            ),
            traceback_text=self.format_traceback(exception),
            on_close=on_close,
        )


class DatabricksPermissionErrorDialog(RichErrorDialogBase):
    """Rich modal dialog for Databricks access and permission errors."""

    def matches(self, exception: BaseException) -> bool:
        """Catch Databricks permission errors."""
        message = str(exception).lower()
        exception_type = type(exception).__name__.lower()
        module_name = type(exception).__module__.lower()
        databricks_error_indicators = (
            isinstance(exception, sql.exc.ServerOperationError)
            or "databricks" in module_name
            or "databricks" in message
            or "serveroperationerror" in exception_type
        )
        access_error_indicators = (
            "insufficient_permissions",
            "permission_denied",
            "unauthorized",
            "forbidden",
            "access denied",
            "insufficient privileges",
            "not authorized",
            "not permitted",
            "permission denied",
            "missing permission",
            "missing permissions",
            "does not have",
            "cannot access",
            "user does not have",
            "sqlstate: 42501",
            "sqlstate: 28000",
            "use schema",
            "select privilege",
            "select privileges",
        )

        return databricks_error_indicators and any(
            indicator in message for indicator in access_error_indicators
        )

    def build_dialog_config(
        self,
        exception: BaseException,
        on_close: Callable[[], None] | None = None,
    ) -> RichErrorDialogConfig:
        """Build dialog content for a Databricks permission failure."""
        details = self._extract_permission_details(str(exception))
        management_url = cast(str, self.app_config.data_access_management_url)
        packages_url = cast(
            str,
            self.app_config.databricks_access_packages_url,
        )

        return RichErrorDialogConfig(
            title="Missing Databricks permissions",
            description=(
                "You do not have the required access rights for the selected "
                "data source. The query requires Databricks permissions."
            ),
            details=details,
            instruction_title="How to resolve",
            instructions=[
                "Open the Data Access Management page.",
                "Follow the Databricks access instructions.",
                (
                    "Select the access package that matches the data source "
                    "you need on the Databricks Access Packages page."
                ),
                "After approval, reload this page and retry.",
            ],
            links=[
                ErrorLink(
                    label="Data Access Management",
                    url=management_url,
                ),
                ErrorLink(
                    label="Databricks Access Packages",
                    url=packages_url,
                ),
            ],
            traceback_text=None if details else self.format_traceback(exception),
            on_close=on_close,
        )

    @staticmethod
    def _extract_permission_details(message: str) -> list[ErrorDetail]:
        """Extract Databricks permission details from an error message."""
        patterns = {
            "Missing schema permission": r"Schema '([^']+)'",
            "Missing table permission": r"Table '([^']+)'",
            "Missing view permission": r"View '([^']+)'",
        }

        return [
            ErrorDetail(label=label, value=match.group(1))
            for label, pattern in patterns.items()
            if (match := re.search(pattern, message)) is not None
        ]
