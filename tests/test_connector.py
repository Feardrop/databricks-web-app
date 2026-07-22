"""Tests for databricks_web_app.connector."""

from __future__ import annotations

from databricks_web_app import AppConfig
from databricks_web_app.connector import (
    AbstractConnector,
    DatabricksUserAndM2MConnector,
)

import pytest


class _FakeHandler:
    """Handler stand-in that records the config it was built with."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config


class TestAbstractConnector:
    """Tests for the AbstractConnector base class."""

    def test_cannot_be_instantiated_directly(self, app_config: AppConfig):
        with pytest.raises(TypeError):
            AbstractConnector(app_config, _FakeHandler)  # type: ignore[abstract]


class TestDatabricksUserAndM2MConnector:
    """Tests for the default user + M2M connector."""

    def test_constructs_handlers_via_injected_factories(self, app_config: AppConfig):
        connector = DatabricksUserAndM2MConnector(
            app_config,
            user_handler_factory=_FakeHandler,
            m2m_handler_factory=_FakeHandler,
        )

        assert isinstance(connector.user_handler, _FakeHandler)
        assert isinstance(connector.m2m_handler, _FakeHandler)
        assert connector.user_handler.config is app_config
        assert connector.m2m_handler is not connector.user_handler

    def test_defaults_to_access_token_and_azure_sp_handlers(
        self, app_config: AppConfig
    ):
        from databricks_web_app.handlers import (
            AccessTokenUserHandler,
            AzureSPM2MOauthHandler,
        )

        connector = DatabricksUserAndM2MConnector(app_config)

        assert isinstance(connector.user_handler, AccessTokenUserHandler)
        assert isinstance(connector.m2m_handler, AzureSPM2MOauthHandler)
