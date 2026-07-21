"""Tests for databricks_web_app.error_handlers."""

from __future__ import annotations

from databricks_web_app import AppConfig
from databricks_web_app.error_handlers.authentication import (
    ClientSecretExpiredErrorDialog,
    TokenExpiredErrorDialog,
)
from databricks_web_app.error_handlers.components import RichErrorDialogConfig
from databricks_web_app.error_handlers.databricks import (
    DatabricksInvalidAccessTokenErrorDialog,
    DatabricksPermissionErrorDialog,
)
from databricks_web_app.error_handlers.generic import GenericApplicationErrorDialog

import jwt
import pytest
import requests


@pytest.fixture
def app_config(valid_environ: dict[str, str]) -> AppConfig:
    return AppConfig(environ=valid_environ)


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
