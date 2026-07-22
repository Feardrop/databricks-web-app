"""Error handling utilities."""

import html
import logging
import traceback
from abc import ABC, abstractmethod
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable, ClassVar, Optional
from urllib.parse import quote

from databricks_web_app import AppConfig

import solara

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class _DialogPalette:
    """Resolved colors for one theme (light or dark) used in dialog HTML."""

    body_text: str
    details_border: str
    details_bg: str
    traceback_border: str
    traceback_bg: str
    code_bg: str
    code_text: str
    muted_text: str
    secondary_button_bg: str
    primary_button_bg: str


_LIGHT_PALETTE = _DialogPalette(
    body_text="#1f2933",
    details_border="#d32f2f",
    details_bg="#fff5f5",
    traceback_border="#d9dee3",
    traceback_bg="#f8fafc",
    code_bg="#111827",
    code_text="#f9fafb",
    muted_text="#6b7280",
    secondary_button_bg="#6b7280",
    primary_button_bg="#1976d2",
)

_DARK_PALETTE = _DialogPalette(
    body_text="#e5e7eb",
    details_border="#f87171",
    details_bg="#3f1d1d",
    traceback_border="#374151",
    traceback_bg="#1f2937",
    code_bg="#0b0f19",
    code_text="#e5e7eb",
    muted_text="#9ca3af",
    secondary_button_bg="#4b5563",
    primary_button_bg="#2196f3",
)


def _resolve_palette(dark: bool) -> _DialogPalette:
    """Return the color palette for the given effective theme."""
    return _DARK_PALETTE if dark else _LIGHT_PALETTE


@dataclass(frozen=True)
class ErrorLink:
    """External documentation link rendered in the error dialog."""

    label: str
    url: str


@dataclass(frozen=True)
class ErrorDetail:
    """Single highlighted error detail rendered in the error dialog."""

    label: str
    value: str


@dataclass(frozen=True)
class RichErrorDialogConfig:
    """Content configuration for a rich error dialog."""

    title: str
    description: str
    details: Optional[list[ErrorDetail]] = None
    instruction_title: Optional[str] = None
    instructions: Optional[list[str]] = None
    links: Optional[list[ErrorLink]] = None
    traceback_text: Optional[str] = None
    on_close: Optional[Callable[[], None]] = None
    force_page_reload: bool = False

    def __post_init__(self) -> None:
        """Validate dependent instruction fields."""
        has_instruction_title = self.instruction_title is not None
        has_instructions = self.instructions is not None

        if has_instruction_title != has_instructions:
            raise ValueError(
                "instruction_title and instructions must either both be set "
                "or both be omitted."
            )


class RichErrorDialogBase(ABC):
    """Base handler and renderer for rich modal error dialogs."""

    clear_exception_on_close: ClassVar[bool] = True
    max_width: ClassVar[str] = "920px"

    def __init__(self, app_config: AppConfig) -> None:
        """Initialize the handler with its application configuration."""
        self.app_config = app_config

    @abstractmethod
    def matches(self, exception: BaseException) -> bool:
        """Return whether this handler accepts the exception."""
        raise NotImplementedError

    @abstractmethod
    def build_dialog_config(
        self,
        exception: BaseException,
        on_close: Callable[[], None] | None = None,
    ) -> RichErrorDialogConfig:
        """Build dialog content for the exception."""
        raise NotImplementedError

    def handle_exception(
        self,
        exception: BaseException,
        on_close: Callable[["RichErrorDialogBase"], None],
    ) -> bool:
        """Render the exception if this handler accepts it."""
        if not self.matches(exception):
            return False

        dialog_config = self.build_dialog_config(
            exception=exception,
            on_close=lambda: on_close(self),
        )
        dialog_config = self._redact_traceback_in_production(dialog_config)

        if not self.clear_exception_on_close:
            dialog_config = replace(
                dialog_config,
                force_page_reload=True,
            )

        RichErrorDialogComponent(
            dialog_config,
            self.app_config,
            max_width=self.max_width,
        )
        return True

    def _redact_traceback_in_production(
        self,
        dialog_config: RichErrorDialogConfig,
    ) -> RichErrorDialogConfig:
        """Log the traceback server-side, then hide it outside development.

        End users should not see raw Python tracebacks (internal paths,
        dependency versions, query/schema details) in production, but
        operators still need them -- so they're always logged here first,
        regardless of what ends up in the rendered dialog.
        """
        if dialog_config.traceback_text is None:
            return dialog_config

        log.error(
            "Unhandled error rendered by %s:\n%s",
            type(self).__name__,
            dialog_config.traceback_text,
        )

        if self.app_config.is_development:
            return dialog_config

        return replace(dialog_config, traceback_text=None)

    @staticmethod
    def format_traceback(exception: BaseException) -> str:
        """Format the complete traceback for display."""
        return "".join(
            traceback.format_exception(
                type(exception),
                exception,
                exception.__traceback__,
            )
        )

    @staticmethod
    def _details_html(details: list[ErrorDetail]) -> str:
        """Build HTML list items for highlighted error details."""
        return "\n".join(
            "<li><strong>"
            f"{html.escape(detail.label)}:</strong> "
            f"<code>{html.escape(detail.value)}</code></li>"
            for detail in details
        )

    @staticmethod
    def _links_by_label(links: list[ErrorLink]) -> dict[str, str]:
        """Return escaped URLs indexed by the link label."""
        return {link.label: html.escape(link.url, quote=True) for link in links}

    @staticmethod
    def _render_instruction_html(
        instruction: str,
        links_by_label: dict[str, str],
    ) -> str:
        """Render one instruction and replace known link labels with anchors."""
        escaped_instruction = html.escape(instruction)

        for label, escaped_url in links_by_label.items():
            escaped_label = html.escape(label)
            escaped_instruction = escaped_instruction.replace(
                escaped_label,
                (
                    f'<a href="{escaped_url}" target="_blank" '
                    f'rel="noopener noreferrer">{escaped_label}</a>'
                ),
            )

        return f"<li>{escaped_instruction}</li>"

    @classmethod
    def instructions_html(
        cls,
        instructions: list[str],
        links: list[ErrorLink],
    ) -> str:
        """Build ordered-list HTML for instructions."""
        links_by_label = cls._links_by_label(links)

        return "\n".join(
            cls._render_instruction_html(instruction, links_by_label)
            for instruction in instructions
        )

    @classmethod
    def _details_section_html(
        cls,
        details: Optional[list[ErrorDetail]],
        dark: bool = False,
    ) -> str:
        """Build the optional highlighted details section."""
        if not details:
            return ""

        details_html = cls._details_html(details)
        palette = _resolve_palette(dark)

        return f"""
            <div style="
                margin: 0 0 18px 0;
                padding: 12px 14px;
                border-left: 4px solid {palette.details_border};
                background: {palette.details_bg};
                border-radius: 4px;
            ">
                <ul style="margin: 0; padding-left: 20px;">
                    {details_html}
                </ul>
            </div>
        """

    @classmethod
    def _instructions_section_html(
        cls,
        config: RichErrorDialogConfig,
    ) -> str:
        """Build the optional instruction section."""
        if config.instruction_title is None or config.instructions is None:
            return ""

        instructions_html = cls.instructions_html(
            instructions=config.instructions,
            links=config.links or [],
        )

        return f"""
            <h3 style="
                margin: 0 0 8px 0;
                font-size: 17px;
                font-weight: 600;
            ">
                {html.escape(config.instruction_title)}
            </h3>

            <ol style="
                margin: 0 0 18px 0;
                padding-left: 22px;
            ">
                {instructions_html}
            </ol>
        """

    @staticmethod
    def _traceback_section_html(
        traceback_text: Optional[str],
        dark: bool = False,
    ) -> str:
        """Build the optional traceback section."""
        if traceback_text is None:
            return ""

        palette = _resolve_palette(dark)

        return f"""
            <details style="
                margin-top: 18px;
                border: 1px solid {palette.traceback_border};
                border-radius: 6px;
                background: {palette.traceback_bg};
            ">
                <summary style="
                    cursor: pointer;
                    padding: 10px 12px;
                    font-weight: 600;
                ">
                    Complete error details
                </summary>

                <pre style="
                    margin: 0;
                    padding: 12px;
                    overflow-x: auto;
                    white-space: pre-wrap;
                    word-break: break-word;
                    font-size: 12px;
                    line-height: 1.4;
                    background: {palette.code_bg};
                    color: {palette.code_text};
                    border-radius: 0 0 6px 6px;
                ">{html.escape(traceback_text)}</pre>
            </details>
        """

    @classmethod
    def body_html(cls, config: RichErrorDialogConfig, dark: bool = False) -> str:
        """Build the full dialog body as HTML."""
        palette = _resolve_palette(dark)
        details_section = cls._details_section_html(config.details, dark=dark)
        instructions_section = cls._instructions_section_html(config)
        traceback_section = cls._traceback_section_html(
            config.traceback_text, dark=dark
        )

        return f"""
            <div style="
                padding: 24px;
                line-height: 1.45;
                color: {palette.body_text};
            ">
                <h2 style="
                    margin: 0 0 12px 0;
                    font-size: 22px;
                    font-weight: 600;
                ">
                    {html.escape(config.title)}
                </h2>

                <p style="margin: 0 0 16px 0;">
                    {html.escape(config.description)}
                </p>

                {details_section}
                {instructions_section}
                {traceback_section}
            </div>
        """


def _get_mailto_link(
    dialog_config: RichErrorDialogConfig, app_config: AppConfig
) -> Optional[str]:
    """Build a mailto link containing the visible error details."""
    if not app_config.contact_email:
        log.error("No contact email configured for error dialog.")
        return None

    subject = (
        f"[{app_config.project_name}] {dialog_config.title} "
        f"({datetime.isoformat(datetime.now(timezone.utc), timespec='seconds')})"
    )
    body = (
        f"{dialog_config.title}\n\n"
        f"{dialog_config.description}\n\n"
        "Complete error details:\n"
        f"{dialog_config.traceback_text or 'No traceback available.'}"
    )

    return (
        f"mailto:{html.escape(app_config.contact_email, quote=True)}"
        f"?subject={quote(subject)}"
        f"&body={quote(body)}"
    )


@solara.component
def RichErrorDialogComponent(
    dialog_config: RichErrorDialogConfig,
    app_config: AppConfig,
    max_width: str = "920px",
):
    # pylint: disable=invalid-name
    """Render a reusable rich modal error dialog."""
    open_dialog, set_open_dialog = solara.use_state(True)
    dark = solara.lab.use_dark_effective()
    palette = _resolve_palette(dark)

    def close_dialog() -> None:
        """Close the dialog and clear the captured exception if configured."""
        set_open_dialog(False)

        if dialog_config.on_close is not None:
            dialog_config.on_close()

    with solara.v.Dialog(
        v_model=open_dialog,
        persistent=True,
        max_width=max_width,
    ):
        with solara.v.Card():
            solara.HTML(
                tag="div",
                unsafe_innerHTML=RichErrorDialogBase.body_html(
                    dialog_config, dark=dark
                ),
            )

            if dialog_config.force_page_reload:
                solara.HTML(
                    tag="div",
                    unsafe_innerHTML=f"""
                        <div style="
                            padding: 0 24px 12px 24px;
                            color: {palette.muted_text};
                            font-size: 13px;
                        ">
                            This error cannot be recovered automatically.
                            Reload the page. If this error persists, contact
                            the developers and include the complete error
                            details by clicking the corresponding button
                            below.
                        </div>
                    """,
                )

            with solara.Row(
                justify="end",
                style={"padding": "0 24px 20px 24px", "gap": "8px"},
            ):
                if dialog_config.force_page_reload:
                    mailto_link = _get_mailto_link(dialog_config, app_config)

                    button_style = """
                        height: 36px;
                        min-width: 64px;
                        padding: 0 16px;
                        border: none;
                        border-radius: 4px;
                        cursor: pointer;
                        font-family: Roboto, sans-serif;
                        font-size: 14px;
                        font-weight: 500;
                        line-height: 36px;
                        text-decoration: none;
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        box-sizing: border-box;
                        vertical-align: middle;
                        white-space: nowrap;
                    """

                    if mailto_link:
                        solara.HTML(
                            tag="span",
                            unsafe_innerHTML=f"""
                                <a
                                    href="{mailto_link}"
                                    style="
                                        {button_style}
                                        background: {palette.secondary_button_bg};
                                        color: white;
                                    "
                                >
                                    Contact developers
                                </a>
                            """,
                        )

                    solara.HTML(
                        tag="span",
                        unsafe_innerHTML=f"""
                            <button
                                type="button"
                                onclick="window.location.reload()"
                                style="
                                    {button_style}
                                    background: {palette.primary_button_bg};
                                    color: white;
                                "
                            >
                                Reload page
                            </button>
                        """,
                    )
                else:
                    solara.Button(
                        "Close",
                        color="primary",
                        on_click=close_dialog,
                    )
