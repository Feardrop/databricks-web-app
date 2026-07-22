"""Token providers for Databricks authentication."""

import logging
from abc import ABC, abstractmethod
from typing import cast

from databricks_web_app.app import _require_access_token
from databricks_web_app.app_config import (
    AZURE_TENANT_ID,
    AppConfig,
    ConfigurationError,
)
from databricks_web_app.auth.token_store import TOKEN_BY_SESSION

import jwt
import solara
from databricks.sql.auth.common import AzureAppId
from databricks.sql.client import Connection
from solara.lab import headers as solara_headers

DEBUG = False

log = logging.getLogger(__name__)


class TokenProvider(ABC):
    """Base class for Databricks token providers."""

    def __init__(self, config: AppConfig) -> None:
        """Initialize the TokenProvider."""
        self.config = config
        assert config.databricks_host, "AppConfig validation guarantees this is set."
        self.connection = Connection(
            server_hostname=config.databricks_host,
            http_path=config.databricks_http_path,
        )

    @abstractmethod
    def get_token(self) -> str:
        """Return a valid access token."""
        raise NotImplementedError

    @property
    def _tenant_id(self) -> str:
        session = getattr(self.connection, "session", None)

        if session is None:
            log.error("No session found in connection.")
        else:
            auth_provider = getattr(session, "auth_provider", None)

            if auth_provider is not None:
                fetched_tenant_id = getattr(auth_provider, "azure_tenant_id", None)

                if fetched_tenant_id:
                    return cast(str, fetched_tenant_id)

            log.error("No 'azure_tenant_id' found in connection auth provider.")

        default_tenant_id = self.config.azure_tenant_id

        if default_tenant_id is None:
            raise ConfigurationError(
                f"{AZURE_TENANT_ID} not found in .env but required here."
            )

        return default_tenant_id

    @abstractmethod
    def _acquire_token(self) -> str:
        """Acquire a new access token."""
        raise NotImplementedError

    @abstractmethod
    def _verify_token(self, token: str) -> str:
        """Verify the token and return it."""
        raise NotImplementedError

    @property
    def _jwks_client(self) -> jwt.PyJWKClient:
        """Return JWKS client for Entra signing keys."""
        return jwt.PyJWKClient(
            f"https://login.microsoftonline.com/{self._tenant_id}/discovery/v2.0/keys"
        )

    @property
    def _issuer(self) -> str:
        """Expected _issuer for Databricks access tokens."""
        return f"https://sts.windows.net/{self._tenant_id}/"


class UserTokenProvider(TokenProvider):
    """Supply and verify the current user's access token."""

    def get_token(self) -> str:
        """Return a valid user token from the x-access-token header."""
        token = self._acquire_token()
        return self._verify_token(token)

    def _acquire_token(self) -> str:
        """Retrieve user token from known sources."""
        try:
            print("Try retrieving token from in-memory dict.")
            sid = solara.get_session_id()
            return TOKEN_BY_SESSION[sid]
        except Exception:  # pylint: disable=broad-exception-caught
            print("Failed to retrieve access token from in-memory dict.")

        print("Fallback: Try retrieving access token from headers.")
        headers = solara_headers.value or {}  # type: ignore[attr-defined]

        return _require_access_token(headers)

    def _verify_token(self, token: str) -> str:
        """Verify JWT token."""
        if token.count(".") != 2:
            if DEBUG:
                print("Omit token verification as token is likely an opaque one.")
                print(f"{token=}")
            return token

        # Get public key with which JWT is signed from IdP.
        signing_key = self._jwks_client.get_signing_key_from_jwt(token)

        audience = self.config.databricks_token_audience or AzureAppId.PROD.value[1]

        try:
            decoded_token = jwt.decode(
                token,
                key=signing_key.key,
                # Entra always signs tokens with RS256 (RSA + SHA-256)
                algorithms=["RS256"],
                audience=audience,
                # The token version (v1 or v2) is determined by the requested resource (Databricks),
                # not the endpoint from which the token is retrieved (Entra).
                # _issuer=f"https://login.microsoftonline.com/{azure_tenant_id}/v2.0"
                # v2 token
                issuer=self._issuer,  # v1 token
            )
            if DEBUG:
                print(f"{decoded_token=}")
        except jwt.exceptions.ExpiredSignatureError as exc:
            raise jwt.exceptions.ExpiredSignatureError(
                "Token for data has expired."
            ) from exc
        return token
