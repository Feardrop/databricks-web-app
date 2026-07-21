"""Shared fixtures for the test suite."""

from __future__ import annotations

from collections.abc import Mapping

import pytest


@pytest.fixture
def valid_environ() -> dict[str, str]:
    """Return a minimal environ mapping that satisfies AppConfig validation."""
    return {
        "DATABRICKS_HOST": "https://adb-1234567890123456.1.azuredatabricks.net",
        "DATABRICKS_WAREHOUSE_ID": "abc123def4567890",
        "PROJECT_NAME": "test-project",
        "AZURE_CLIENT_ID": "12345678-1234-1234-1234-123456789012",
        "AZURE_CLIENT_SECRET": "supersecretvalue",
        "DATA_ACCESS_MANAGEMENT_URL": "https://example.com/access-management",
        "DATA_ACCESS_PACKAGES_URL": "https://example.com/access-packages",
    }


def make_environ(base: Mapping[str, str], **overrides: str) -> dict[str, str]:
    """Return a copy of ``base`` with ``overrides`` applied."""
    merged = dict(base)
    merged.update(overrides)
    return merged
