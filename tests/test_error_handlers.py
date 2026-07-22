"""Tests for databricks_web_app.error_handlers."""

from __future__ import annotations

import logging

from databricks_web_app import AppConfig
from databricks_web_app.error_handlers.authentication import (
    ClientSecretExpiredErrorDialog,
    TokenExpiredErrorDialog,
)
from databricks_web_app.error_handlers.components import (
    _DARK_PALETTE,
    _LIGHT_PALETTE,
    ErrorDetail,
    RichErrorDialogBase,
    RichErrorDialogConfig,
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
