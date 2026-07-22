"""Integration tests for examples/dev_app.

These import the example's src/ modules directly against the package
installed in this environment, so a breaking API change in
databricks_web_app surfaces here (and in the README examples it mirrors)
before it reaches a real consumer.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from databricks_web_app.connector import DatabricksUserAndM2MConnector

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

DEV_APP_SRC = Path(__file__).resolve().parent.parent / "examples" / "dev_app" / "src"


def _import_module(name: str, filename: str) -> ModuleType:
    """Import a module from examples/dev_app/src by file path."""
    spec = importlib.util.spec_from_file_location(name, DEV_APP_SRC / filename)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def dev_app_environ(monkeypatch: pytest.MonkeyPatch, valid_environ: dict[str, str]):
    """Export a valid AppConfig environ as real process environment variables."""
    for key, value in valid_environ.items():
        monkeypatch.setenv(key, value)


class TestDevAppDashboard:
    """Tests for examples/dev_app/src/dashboard.py."""

    def test_imports_and_wires_a_lazy_connector(self, dev_app_environ):
        dashboard = _import_module("dev_app_dashboard", "dashboard.py")

        handler = dashboard.app.databricks_handler

        assert isinstance(handler, DatabricksUserAndM2MConnector)
        assert handler.user_handler.config is dashboard.config

    def test_run_query_uses_the_lazy_connector(self, dev_app_environ, monkeypatch):
        dashboard = _import_module("dev_app_dashboard", "dashboard.py")

        calls: list[str] = []

        class _FakeUserHandler:
            def fetchall_df(self, statement: str):
                calls.append(statement)

                class _FakeFrame:
                    def to_string(self) -> str:
                        return "answer\n1"

                return _FakeFrame()

        monkeypatch.setattr(
            dashboard.app.databricks_handler,
            "user_handler",
            _FakeUserHandler(),
        )

        dashboard.run_query()

        assert calls == ["SELECT 1 AS answer"]
        assert dashboard.query_result.value == "answer\n1"


class TestDevAppServerApp:
    """Tests for examples/dev_app/src/server_app.py."""

    def test_exposes_a_starlette_app_with_expected_routes(self, dev_app_environ):
        server_app = _import_module("dev_app_server_app", "server_app.py")

        assert isinstance(server_app.app, Starlette)

        client = TestClient(server_app.app)
        response = client.get("/readyz")

        assert response.status_code == 200
