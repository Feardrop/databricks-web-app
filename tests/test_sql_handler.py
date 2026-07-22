"""Tests for databricks_web_app.handlers.sql_handler."""

from __future__ import annotations

from databricks_web_app import AppConfig
from databricks_web_app.handlers import sql_handler as sql_handler_module
from databricks_web_app.handlers.sql_handler import (
    AccessTokenUserHandler,
    AzureSPM2MOauthHandler,
)

import pytest
from databricks.sql.auth.common import AuthType

from .conftest import make_environ


class _FakeConnection:
    """Stand-in for the object returned by databricks.sql.connect."""


class TestAccessTokenUserHandlerGetConnection:
    """Tests for AccessTokenUserHandler.get_connection."""

    def test_development_uses_databricks_token(
        self, monkeypatch: pytest.MonkeyPatch, valid_environ: dict[str, str]
    ):
        environ = make_environ(
            valid_environ,
            SOLARA_APP_ENV="development",
            DATABRICKS_TOKEN="dapi" + "a" * 32 + "-2",
        )
        config = AppConfig(environ=environ)
        handler = AccessTokenUserHandler(config)

        calls = []
        monkeypatch.setattr(
            sql_handler_module.sql,
            "connect",
            lambda **kwargs: calls.append(kwargs) or _FakeConnection(),
        )

        connection = handler.get_connection()

        assert isinstance(connection, _FakeConnection)
        assert len(calls) == 1
        assert calls[0]["access_token"] == "dapi" + "a" * 32 + "-2"
        assert calls[0]["server_hostname"] == config.databricks_host
        assert calls[0]["http_path"] == config.databricks_http_path

    def test_production_uses_user_token_provider(
        self, monkeypatch: pytest.MonkeyPatch, app_config: AppConfig
    ):
        handler = AccessTokenUserHandler(app_config)

        class _FakeUserTokenProvider:
            def __init__(self, config: AppConfig) -> None:
                self.config = config

            def get_token(self) -> str:
                return "token-from-provider"

        monkeypatch.setattr(
            sql_handler_module, "UserTokenProvider", _FakeUserTokenProvider
        )

        calls = []
        monkeypatch.setattr(
            sql_handler_module.sql,
            "connect",
            lambda **kwargs: calls.append(kwargs) or _FakeConnection(),
        )

        connection = handler.get_connection()

        assert isinstance(connection, _FakeConnection)
        assert calls[0]["access_token"] == "token-from-provider"


class TestAzureSPM2MOauthHandlerGetConnection:
    """Tests for AzureSPM2MOauthHandler.get_connection."""

    def test_uses_service_principal_credentials(
        self, monkeypatch: pytest.MonkeyPatch, app_config: AppConfig
    ):
        handler = AzureSPM2MOauthHandler(app_config)

        calls = []
        monkeypatch.setattr(
            sql_handler_module.sql,
            "connect",
            lambda **kwargs: calls.append(kwargs) or _FakeConnection(),
        )

        connection = handler.get_connection()

        assert isinstance(connection, _FakeConnection)
        assert calls[0]["auth_type"] == AuthType.AZURE_SP_M2M.value
        assert calls[0]["azure_client_id"] == app_config.m2m_client_id
        assert calls[0]["azure_client_secret"] == app_config.m2m_client_secret
