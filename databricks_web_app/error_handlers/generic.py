"""Generic fallback error handlers."""

from collections.abc import Callable

from databricks_web_app.error_handlers.components import (
    ErrorDetail,
    RichErrorDialogBase,
    RichErrorDialogConfig,
)


class GenericApplicationErrorDialog(RichErrorDialogBase):
    """Rich modal dialog for unclassified application errors. Use last."""

    clear_exception_on_close = False

    def matches(self, exception: BaseException) -> bool:
        """Catch all unhandled application errors."""
        return True

    def build_dialog_config(
        self,
        exception: BaseException,
        on_close: Callable[[], None] | None = None,
    ) -> RichErrorDialogConfig:
        """Build dialog content for an unclassified application error."""
        return RichErrorDialogConfig(
            title="Application error",
            description=(
                "An unexpected error occurred while rendering or updating the "
                "dashboard. The current selection may no longer match the "
                "available data."
            ),
            details=self._extract_error_details(exception),
            instruction_title="How to resolve",
            instructions=[
                "Reset the current selection.",
                "Reload the data source if the error persists.",
            ],
            traceback_text=self.format_traceback(exception),
            on_close=on_close,
        )

    @staticmethod
    def _extract_error_details(exception: BaseException) -> list[ErrorDetail]:
        """Extract generic error details."""
        details = [
            ErrorDetail(
                label="Error type",
                value=type(exception).__name__,
            )
        ]

        if isinstance(exception, KeyError) and exception.args:
            details.append(
                ErrorDetail(
                    label="Missing key or column",
                    value=str(exception.args[0]),
                )
            )

        return details
