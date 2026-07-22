"""Tests for databricks_web_app.auth.token_providers.

TokenProvider.__init__ constructs a real databricks.sql.client.Connection,
which performs live OAuth discovery network calls. All tests here replace
that Connection with a lightweight fake before constructing a provider.
"""

from __future__ import annotations

from typing import Any, Optional

from databricks_web_app import AppConfig
from databricks_web_app.app_config import ConfigurationError
from databricks_web_app.auth import token_providers as token_providers_module
from databricks_web_app.auth.token_providers import UserTokenProvider

import jwt
import pytest

from .conftest import make_environ


class _FakeAuthProvider:
    def __init__(self, azure_tenant_id: Optional[str] = None) -> None:
        self.azure_tenant_id = azure_tenant_id


class _FakeSession:
    def __init__(self, auth_provider: Optional[_FakeAuthProvider] = None) -> None:
        self.auth_provider = auth_provider


class _FakeConnection:
    """Stand-in for databricks.sql.client.Connection, avoiding real network I/O."""

    def __init__(self, session: Optional[_FakeSession] = None, **_: Any) -> None:
        self.session = session


class _FakeSigningKey:
    def __init__(self, key: str) -> None:
        self.key = key


def _make_provider(
    monkeypatch: pytest.MonkeyPatch,
    config: AppConfig,
    session: Optional[_FakeSession] = None,
) -> UserTokenProvider:
    monkeypatch.setattr(
        token_providers_module,
        "Connection",
        lambda **kwargs: _FakeConnection(session=session),
    )
    return UserTokenProvider(config)


class TestTenantId:
    """Tests for TokenProvider._tenant_id resolution and fallback."""

    def test_uses_session_auth_provider_tenant_id(
        self, monkeypatch: pytest.MonkeyPatch, app_config: AppConfig
    ):
        session = _FakeSession(
            auth_provider=_FakeAuthProvider(azure_tenant_id="tenant-from-session")
        )
        provider = _make_provider(monkeypatch, app_config, session=session)

        assert provider._tenant_id == "tenant-from-session"

    def test_falls_back_to_config_when_no_session(
        self, monkeypatch: pytest.MonkeyPatch, valid_environ: dict[str, str]
    ):
        environ = make_environ(valid_environ, AZURE_TENANT_ID="tenant-from-config")
        config = AppConfig(environ=environ)

        provider = _make_provider(monkeypatch, config, session=None)

        assert provider._tenant_id == "tenant-from-config"

    def test_falls_back_to_config_when_no_auth_provider(
        self, monkeypatch: pytest.MonkeyPatch, valid_environ: dict[str, str]
    ):
        environ = make_environ(valid_environ, AZURE_TENANT_ID="tenant-from-config")
        config = AppConfig(environ=environ)
        session = _FakeSession(auth_provider=None)

        provider = _make_provider(monkeypatch, config, session=session)

        assert provider._tenant_id == "tenant-from-config"

    def test_falls_back_to_config_when_tenant_id_falsy(
        self, monkeypatch: pytest.MonkeyPatch, valid_environ: dict[str, str]
    ):
        environ = make_environ(valid_environ, AZURE_TENANT_ID="tenant-from-config")
        config = AppConfig(environ=environ)
        session = _FakeSession(auth_provider=_FakeAuthProvider(azure_tenant_id=""))

        provider = _make_provider(monkeypatch, config, session=session)

        assert provider._tenant_id == "tenant-from-config"

    def test_raises_when_no_fallback_configured(
        self, monkeypatch: pytest.MonkeyPatch, app_config: AppConfig
    ):
        provider = _make_provider(monkeypatch, app_config, session=None)

        with pytest.raises(ConfigurationError):
            provider._tenant_id  # noqa: B018 (property access is the point)


class TestVerifyToken:
    """Tests for UserTokenProvider._verify_token."""

    def test_opaque_token_returned_without_verification(
        self, monkeypatch: pytest.MonkeyPatch, app_config: AppConfig
    ):
        provider = _make_provider(monkeypatch, app_config)

        def _fail_if_called(*args: object, **kwargs: object) -> None:
            raise AssertionError("JWKS client must not be used for opaque tokens")

        monkeypatch.setattr(
            jwt.PyJWKClient, "get_signing_key_from_jwt", _fail_if_called
        )

        assert provider._verify_token("opaque-token-no-dots") == "opaque-token-no-dots"

    def test_verifies_rs256_token_and_returns_it_unchanged(
        self, monkeypatch: pytest.MonkeyPatch, valid_environ: dict[str, str]
    ):
        environ = make_environ(valid_environ, AZURE_TENANT_ID="tenant-from-config")
        config = AppConfig(environ=environ)
        provider = _make_provider(monkeypatch, config)
        token = "header.payload.signature"

        monkeypatch.setattr(
            jwt.PyJWKClient,
            "get_signing_key_from_jwt",
            lambda self, token: _FakeSigningKey(key="fake-public-key"),
        )

        decode_calls = []

        def _fake_decode(token_arg: str, **kwargs: object) -> dict:
            decode_calls.append((token_arg, kwargs))
            return {"sub": "user"}

        monkeypatch.setattr(jwt, "decode", _fake_decode)

        result = provider._verify_token(token)

        assert result == token
        assert len(decode_calls) == 1
        decoded_token_arg, kwargs = decode_calls[0]
        assert decoded_token_arg == token
        assert kwargs["key"] == "fake-public-key"
        assert kwargs["algorithms"] == ["RS256"]

    def test_remaps_expired_signature_message(
        self, monkeypatch: pytest.MonkeyPatch, valid_environ: dict[str, str]
    ):
        environ = make_environ(valid_environ, AZURE_TENANT_ID="tenant-from-config")
        config = AppConfig(environ=environ)
        provider = _make_provider(monkeypatch, config)
        token = "header.payload.signature"

        monkeypatch.setattr(
            jwt.PyJWKClient,
            "get_signing_key_from_jwt",
            lambda self, token: _FakeSigningKey(key="fake-public-key"),
        )

        def _raise_expired(*args: object, **kwargs: object) -> None:
            raise jwt.exceptions.ExpiredSignatureError("Signature has expired")

        monkeypatch.setattr(jwt, "decode", _raise_expired)

        with pytest.raises(
            jwt.exceptions.ExpiredSignatureError, match="Token for data has expired."
        ):
            provider._verify_token(token)
