"""Tests for databricks_web_app.app_config."""

from __future__ import annotations

from databricks_web_app.app_config import (
    AppConfig,
    ConfigurationError,
    _parse_databricks_token,
    _parse_email,
    _parse_environment,
    _parse_host,
    _parse_uuid,
    _parse_warehouse_id,
)

import pytest

from .conftest import make_environ


class TestParsers:
    """Tests for the standalone value-parsing helpers."""

    def test_parse_uuid_accepts_valid_uuid(self):
        assert (
            _parse_uuid("12345678-1234-1234-1234-123456789012")
            == "12345678-1234-1234-1234-123456789012"
        )

    def test_parse_uuid_rejects_invalid_uuid(self):
        with pytest.raises(ConfigurationError):
            _parse_uuid("not-a-uuid")

    def test_parse_email_accepts_valid_address(self):
        assert _parse_email("user@example.com") == "user@example.com"

    def test_parse_email_rejects_invalid_address(self):
        with pytest.raises(ConfigurationError):
            _parse_email("not-an-email")

    def test_parse_databricks_token_accepts_valid_token(self):
        token = "dapi" + "a" * 32 + "-2"
        assert _parse_databricks_token(token) == token

    @pytest.mark.parametrize(
        "token",
        [
            "not-a-token",
            "dapi" + "a" * 31 + "-2",  # too short
            "dapi" + "A" * 32 + "-2",  # uppercase not allowed
        ],
    )
    def test_parse_databricks_token_rejects_invalid_token(self, token: str):
        with pytest.raises(ConfigurationError):
            _parse_databricks_token(token)

    def test_parse_warehouse_id_accepts_valid_id(self):
        assert _parse_warehouse_id("abc123def4567890") == "abc123def4567890"

    @pytest.mark.parametrize("value", ["tooshort", "ABC123DEF4567890", ""])
    def test_parse_warehouse_id_rejects_invalid_id(self, value: str):
        with pytest.raises(ConfigurationError):
            _parse_warehouse_id(value)

    def test_parse_environment_normalizes_case(self):
        assert _parse_environment("PRODUCTION") == "production"

    def test_parse_environment_rejects_unknown_value(self):
        with pytest.raises(ConfigurationError):
            _parse_environment("staging")

    def test_parse_host_accepts_azure_databricks_url(self):
        host = "https://adb-1234567890123456.1.azuredatabricks.net"
        assert _parse_host(host) == host

    def test_parse_host_rejects_non_azuredatabricks_domain(self):
        with pytest.raises(ConfigurationError):
            _parse_host("https://example.com")


class TestAppConfig:
    """Tests for the AppConfig class."""

    def test_loads_from_environ(self, valid_environ: dict[str, str]):
        config = AppConfig(environ=valid_environ)

        assert config.databricks_host == valid_environ["DATABRICKS_HOST"]
        assert config.databricks_warehouse_id == "abc123def4567890"
        assert config.project_name == "test-project"
        assert config.m2m_client_id == valid_environ["AZURE_CLIENT_ID"]
        assert config.m2m_client_secret == "supersecretvalue"
        assert config.is_development is False

    def test_databricks_http_path(self, valid_environ: dict[str, str]):
        config = AppConfig(environ=valid_environ)

        assert config.databricks_http_path == "/sql/1.0/warehouses/abc123def4567890"

    def test_missing_required_field_raises(self, valid_environ: dict[str, str]):
        environ = dict(valid_environ)
        del environ["DATABRICKS_HOST"]

        with pytest.raises(ConfigurationError):
            AppConfig(environ=environ)

    def test_development_requires_databricks_token(self, valid_environ: dict[str, str]):
        environ = make_environ(valid_environ, SOLARA_APP_ENV="development")

        with pytest.raises(ConfigurationError):
            AppConfig(environ=environ)

    def test_development_with_token_succeeds(self, valid_environ: dict[str, str]):
        environ = make_environ(
            valid_environ,
            SOLARA_APP_ENV="development",
            DATABRICKS_TOKEN="dapi" + "a" * 32 + "-2",
        )

        config = AppConfig(environ=environ)

        assert config.is_development is True

    def test_unknown_constructor_argument_raises(self, valid_environ: dict[str, str]):
        with pytest.raises(TypeError):
            AppConfig(environ=valid_environ, does_not_exist="value")

    def test_as_dict_redacts_sensitive_by_default(self, valid_environ: dict[str, str]):
        config = AppConfig(environ=valid_environ)

        result = config.as_dict()

        assert result["m2m_client_secret"] == "***"

    def test_as_dict_includes_sensitive_when_requested(
        self, valid_environ: dict[str, str]
    ):
        config = AppConfig(environ=valid_environ)

        result = config.as_dict(include_sensitive=True)

        assert result["m2m_client_secret"] == "supersecretvalue"

    def test_debug_string_masks_sensitive_values(self, valid_environ: dict[str, str]):
        config = AppConfig(environ=valid_environ)

        debug_string = config.debug_string()

        assert "supersecretvalue" not in debug_string
        assert "m2m_client_secret" in debug_string

    def test_m2m_client_id_resolved_through_proxy(self, valid_environ: dict[str, str]):
        environ = dict(valid_environ)
        del environ["AZURE_CLIENT_ID"]
        environ["AZURE_CLIENT_ID_PROXY"] = "OTHER_CLIENT_ID"
        environ["OTHER_CLIENT_ID"] = "12345678-1234-1234-1234-123456789012"

        config = AppConfig(environ=environ)

        assert config.m2m_client_id == "12345678-1234-1234-1234-123456789012"

    def test_missing_m2m_client_id_raises(self, valid_environ: dict[str, str]):
        environ = dict(valid_environ)
        del environ["AZURE_CLIENT_ID"]

        with pytest.raises(ConfigurationError):
            AppConfig(environ=environ)
