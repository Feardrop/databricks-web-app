"""Tests for databricks_web_app.error_handlers."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from urllib.parse import quote

from databricks_web_app import AppConfig
from databricks_web_app.error_handlers.authentication import (
    ClientSecretExpiredErrorDialog,
    TokenExpiredErrorDialog,
)
from databricks_web_app.error_handlers.components import (
    _DARK_PALETTE,
    _LIGHT_PALETTE,
    ErrorDetail,
    ErrorLink,
    RichErrorDialogBase,
    RichErrorDialogConfig,
    _get_mailto_link,
    _resolve_palette,
)
from databricks_web_app.error_handlers.databricks import (
    DatabricksInvalidAccessTokenErrorDialog,
    DatabricksPermissionErrorDialog,
)
from databricks_web_app.error_handlers.generic import GenericApplicationErrorDialog

import jwt
import pytest
import requests

from .conftest import make_environ


class TestRichErrorDialogConfig:
    """Tests for the dialog-content validation."""

    def test_requires_both_instruction_fields_together(self):
        with pytest.raises(ValueError):
            RichErrorDialogConfig(
                title="t",
                description="d",
                instruction_title="only title",
            )

    def test_allows_both_instruction_fields_omitted(self):
        config = RichErrorDialogConfig(title="t", description="d")

        assert config.instruction_title is None
        assert config.instructions is None

    def test_allows_both_instruction_fields_present(self):
        config = RichErrorDialogConfig(
            title="t",
            description="d",
            instruction_title="How to resolve",
            instructions=["Do this."],
        )

        assert config.instructions == ["Do this."]


class TestTokenExpiredErrorDialog:
    def test_matches_expired_data_token(self, app_config: AppConfig):
        handler = TokenExpiredErrorDialog(app_config)
        exception = jwt.exceptions.ExpiredSignatureError("Token for data has expired.")

        assert handler.matches(exception) is True

    def test_does_not_match_other_signature_errors(self, app_config: AppConfig):
        handler = TokenExpiredErrorDialog(app_config)
        exception = jwt.exceptions.ExpiredSignatureError("Some other message.")

        assert handler.matches(exception) is False

    def test_does_not_match_unrelated_exception(self, app_config: AppConfig):
        handler = TokenExpiredErrorDialog(app_config)

        assert handler.matches(ValueError("boom")) is False


class TestClientSecretExpiredErrorDialog:
    def test_matches_expired_client_secret_response(self, app_config: AppConfig):
        handler = ClientSecretExpiredErrorDialog(app_config)
        exception = requests.exceptions.HTTPError(
            "401 Client Error: Unauthorized for url: "
            "https://login.microsoftonline.com/"
            "12345678-1234-1234-1234-123456789012/oauth2/v2.0/token"
        )

        assert handler.matches(exception) is True

    def test_does_not_match_unrelated_http_error(self, app_config: AppConfig):
        handler = ClientSecretExpiredErrorDialog(app_config)
        exception = requests.exceptions.HTTPError("404 Client Error: Not Found")

        assert handler.matches(exception) is False


class TestDatabricksInvalidAccessTokenErrorDialog:
    def test_matches_invalid_access_token_message(self, app_config: AppConfig):
        handler = DatabricksInvalidAccessTokenErrorDialog(app_config)

        class DatabricksRequestError(Exception):
            pass

        DatabricksRequestError.__module__ = "databricks.sql.exc"
        exception = DatabricksRequestError("Error: invalid access token")

        assert handler.matches(exception) is True

    def test_does_not_match_generic_exception(self, app_config: AppConfig):
        handler = DatabricksInvalidAccessTokenErrorDialog(app_config)

        assert handler.matches(ValueError("boom")) is False


class TestDatabricksPermissionErrorDialog:
    def test_matches_permission_denied_message(self, app_config: AppConfig):
        handler = DatabricksPermissionErrorDialog(app_config)
        exception = Exception(
            "databricks error: permission_denied for Table 'main.default.foo'"
        )

        assert handler.matches(exception) is True

    def test_does_not_match_unrelated_exception(self, app_config: AppConfig):
        handler = DatabricksPermissionErrorDialog(app_config)

        assert handler.matches(ValueError("boom")) is False

    def test_extracts_table_detail_from_message(self, app_config: AppConfig):
        handler = DatabricksPermissionErrorDialog(app_config)
        exception = Exception(
            "databricks error: permission_denied for Table 'main.default.foo'"
        )

        dialog_config = handler.build_dialog_config(exception)

        assert dialog_config.details is not None
        assert any(
            detail.label == "Missing table permission"
            and detail.value == "main.default.foo"
            for detail in dialog_config.details
        )


class TestGenericApplicationErrorDialog:
    def test_matches_any_exception(self, app_config: AppConfig):
        handler = GenericApplicationErrorDialog(app_config)

        assert handler.matches(ValueError("boom")) is True

    def test_extracts_key_error_detail(self, app_config: AppConfig):
        handler = GenericApplicationErrorDialog(app_config)
        exception = KeyError("missing_column")

        dialog_config = handler.build_dialog_config(exception)

        assert dialog_config.details is not None
        assert any(
            detail.label == "Missing key or column" and detail.value == "missing_column"
            for detail in dialog_config.details
        )


class TestInstructionsHtml:
    """Tests for RichErrorDialogBase.instructions_html and its escaping."""

    def test_renders_one_list_item_per_instruction(self):
        html_out = RichErrorDialogBase.instructions_html(
            instructions=["Do this.", "Then do that."],
            links=[],
        )

        assert html_out.count("<li>") == 2
        assert "Do this." in html_out
        assert "Then do that." in html_out

    def test_escapes_instruction_text(self):
        html_out = RichErrorDialogBase.instructions_html(
            instructions=["<script>alert(1)</script>"],
            links=[],
        )

        assert "<script>" not in html_out
        assert "&lt;script&gt;" in html_out

    def test_replaces_link_label_with_anchor(self):
        html_out = RichErrorDialogBase.instructions_html(
            instructions=["See Data Access Management for details."],
            links=[
                ErrorLink(label="Data Access Management", url="https://example.com")
            ],
        )

        assert '<a href="https://example.com"' in html_out
        assert 'target="_blank"' in html_out
        assert ">Data Access Management</a>" in html_out


class TestDetailsSectionHtml:
    """Tests for RichErrorDialogBase._details_section_html."""

    def test_empty_when_no_details(self):
        assert RichErrorDialogBase._details_section_html(None) == ""
        assert RichErrorDialogBase._details_section_html([]) == ""

    def test_renders_escaped_label_and_value(self):
        details = [ErrorDetail(label="<b>Table</b>", value="main.default.foo")]

        html_out = RichErrorDialogBase._details_section_html(details)

        assert "&lt;b&gt;Table&lt;/b&gt;" in html_out
        assert "main.default.foo" in html_out


class TestTracebackSectionHtml:
    """Tests for RichErrorDialogBase._traceback_section_html."""

    def test_empty_when_no_traceback(self):
        assert RichErrorDialogBase._traceback_section_html(None) == ""

    def test_escapes_traceback_text(self):
        html_out = RichErrorDialogBase._traceback_section_html(
            "Traceback: <boom> & 'quote'"
        )

        assert "<boom>" not in html_out
        assert "&lt;boom&gt;" in html_out
        assert "&amp;" in html_out


class TestBodyHtml:
    """Tests for RichErrorDialogBase.body_html assembling the full dialog."""

    def test_includes_title_and_description(self):
        config = RichErrorDialogConfig(title="Something broke", description="Details.")

        html_out = RichErrorDialogBase.body_html(config)

        assert "Something broke" in html_out
        assert "Details." in html_out

    def test_omits_optional_sections_when_absent(self):
        config = RichErrorDialogConfig(title="t", description="d")

        html_out = RichErrorDialogBase.body_html(config)

        assert "Complete error details" not in html_out

    def test_includes_traceback_section_when_present(self):
        config = RichErrorDialogConfig(
            title="t", description="d", traceback_text="Traceback: boom"
        )

        html_out = RichErrorDialogBase.body_html(config)

        assert "Complete error details" in html_out
        assert "Traceback: boom" in html_out


class TestRedactTracebackInProduction:
    """Tests for RichErrorDialogBase._redact_traceback_in_production."""

    def test_redacts_traceback_in_production(
        self, app_config: AppConfig, caplog: pytest.LogCaptureFixture
    ):
        handler = GenericApplicationErrorDialog(app_config)
        config = RichErrorDialogConfig(
            title="t", description="d", traceback_text="Traceback: boom"
        )

        with caplog.at_level(logging.ERROR):
            redacted = handler._redact_traceback_in_production(config)

        assert redacted.traceback_text is None
        assert redacted.traceback_redacted is True
        assert redacted.occurred_at is not None
        assert "Traceback: boom" in caplog.text

    def test_keeps_traceback_in_development(self, valid_environ: dict[str, str]):
        environ = make_environ(
            valid_environ,
            SOLARA_APP_ENV="development",
            DATABRICKS_TOKEN="dapi" + "a" * 32 + "-2",
        )
        dev_config = AppConfig(environ=environ)
        handler = GenericApplicationErrorDialog(dev_config)
        config = RichErrorDialogConfig(
            title="t", description="d", traceback_text="Traceback: boom"
        )

        redacted = handler._redact_traceback_in_production(config)

        assert redacted.traceback_text == "Traceback: boom"
        assert redacted.traceback_redacted is False
        assert redacted.occurred_at is not None

    def test_noop_when_no_traceback(self, app_config: AppConfig):
        handler = GenericApplicationErrorDialog(app_config)
        config = RichErrorDialogConfig(title="t", description="d")

        redacted = handler._redact_traceback_in_production(config)

        assert redacted is config


class TestResolvePalette:
    """Tests for the light/dark color palette resolution."""

    def test_light_by_default(self):
        assert _resolve_palette(False) is _LIGHT_PALETTE

    def test_dark_when_requested(self):
        assert _resolve_palette(True) is _DARK_PALETTE

    def test_light_and_dark_palettes_differ(self):
        assert _LIGHT_PALETTE != _DARK_PALETTE


class TestThemeAwareHtml:
    """Tests that dialog HTML reflects the requested theme's colors."""

    def test_body_html_uses_light_colors_by_default(self):
        config = RichErrorDialogConfig(title="t", description="d")

        body = RichErrorDialogBase.body_html(config)

        assert _LIGHT_PALETTE.body_text in body
        assert _DARK_PALETTE.body_text not in body

    def test_body_html_uses_dark_colors_when_requested(self):
        config = RichErrorDialogConfig(title="t", description="d")

        body = RichErrorDialogBase.body_html(config, dark=True)

        assert _DARK_PALETTE.body_text in body
        assert _LIGHT_PALETTE.body_text not in body

    def test_details_section_uses_dark_colors_when_requested(self):
        details = [ErrorDetail(label="Table", value="main.default.foo")]

        details_html = RichErrorDialogBase._details_section_html(details, dark=True)

        assert _DARK_PALETTE.details_bg in details_html
        assert _LIGHT_PALETTE.details_bg not in details_html

    def test_traceback_section_uses_dark_colors_when_requested(self):
        traceback_html = RichErrorDialogBase._traceback_section_html(
            "Traceback: boom", dark=True
        )

        assert _DARK_PALETTE.code_bg in traceback_html
        assert _LIGHT_PALETTE.code_bg not in traceback_html


class TestGetMailtoLink:
    """Tests for _get_mailto_link, including the redacted-traceback case."""

    def _config_with_contact_email(self, valid_environ: dict[str, str]) -> AppConfig:
        environ = make_environ(valid_environ, CONTACT_EMAIL="dev@example.com")
        return AppConfig(environ=environ)

    def test_returns_none_without_contact_email(self, app_config: AppConfig):
        config = RichErrorDialogConfig(title="t", description="d")

        assert _get_mailto_link(config, app_config) is None

    def test_builds_mailto_link_with_subject_and_body(
        self, valid_environ: dict[str, str]
    ):
        config_with_contact = self._config_with_contact_email(valid_environ)
        dialog_config = RichErrorDialogConfig(
            title="Something broke",
            description="It broke because of X.",
            traceback_text="Traceback: boom",
        )

        link = _get_mailto_link(dialog_config, config_with_contact)

        assert link is not None
        assert link.startswith("mailto:dev@example.com?subject=")
        assert "Something%20broke" in link
        assert "Traceback%3A%20boom" in link

    def test_points_to_server_logs_when_traceback_redacted(
        self, valid_environ: dict[str, str]
    ):
        config_with_contact = self._config_with_contact_email(valid_environ)
        occurred_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
        dialog_config = RichErrorDialogConfig(
            title="t",
            description="d",
            traceback_text=None,
            occurred_at=occurred_at,
            traceback_redacted=True,
        )

        link = _get_mailto_link(dialog_config, config_with_contact)

        assert link is not None
        assert "logged%20server-side" in link
        # The timestamp used in the subject and body must match, so the
        # developer can correlate the email with the server-side log entry.
        assert link.count(quote("2026-01-02T03:04:05+00:00")) == 2

    def test_no_traceback_available_when_never_captured(
        self, valid_environ: dict[str, str]
    ):
        config_with_contact = self._config_with_contact_email(valid_environ)
        dialog_config = RichErrorDialogConfig(title="t", description="d")

        link = _get_mailto_link(dialog_config, config_with_contact)

        assert link is not None
        assert "No%20traceback%20available." in link
