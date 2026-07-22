"""Tests for databricks_web_app.app."""

from __future__ import annotations

from databricks_web_app import AppConfig, DatabricksApp
from databricks_web_app.app import get_server_app
from databricks_web_app.auth.token_store import TOKEN_BY_SESSION
from databricks_web_app.connector import AbstractConnector

import pytest
from starlette.testclient import TestClient


class _FakeConnector(AbstractConnector):
    """Minimal concrete connector used to test DatabricksApp's lazy property."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config


class _TrackingApp(DatabricksApp[_FakeConnector]):
    """DatabricksApp subclass bound to the fake connector for testing."""

    connector_class = _FakeConnector


class TestDatabricksApp:
    """Tests for the lazy connector-holding DatabricksApp class."""

    def test_lazily_constructs_connector_once(self, app_config: AppConfig):
        app = _TrackingApp(app_config)

        first = app.databricks_handler
        second = app.databricks_handler

        assert first is second
        assert isinstance(first, _FakeConnector)
        assert first.config is app_config

    def test_setter_raises(self, app_config: AppConfig):
        app = _TrackingApp(app_config)

        with pytest.raises(AttributeError):
            app.databricks_handler = _FakeConnector(app_config)


class TestGetServerApp:
    """Tests for the Starlette app returned by get_server_app."""

    def test_mounts_expected_routes(self):
        app = get_server_app()
        paths = {getattr(route, "path", None) for route in app.routes}

        assert "/__keepalive_backend" in paths
        assert "" in paths  # Solara's routes, mounted at the root.

    def test_keepalive_stores_access_token_by_session(self):
        TOKEN_BY_SESSION.clear()
        client = TestClient(get_server_app())
        client.cookies.set("solara-session-id", "session-1")

        response = client.get(
            "/__keepalive_backend",
            headers={"x-access-token": "token-1"},
        )

        assert response.status_code == 204
        assert TOKEN_BY_SESSION["session-1"] == "token-1"

    def test_keepalive_without_token_does_not_store(self):
        TOKEN_BY_SESSION.clear()
        client = TestClient(get_server_app())
        client.cookies.set("solara-session-id", "session-2")

        response = client.get("/__keepalive_backend")

        assert response.status_code == 204
        assert "session-2" not in TOKEN_BY_SESSION
