"""This module contains Databricks SQL access classes."""

import logging

from databricks import sql
from databricks.sql.auth.common import AuthType
from typing_extensions import TYPE_CHECKING

from ..auth import UserTokenProvider
from .abstract import AbstractHandler

if TYPE_CHECKING:
    from databricks.sql.client import Connection

log = logging.getLogger(__name__)


class AccessTokenUserHandler(AbstractHandler):
    """Execute SQL statements against Databricks as the signed-in user.

    Authenticates with the user's OAuth access token (or, in development,
    the configured ``DATABRICKS_TOKEN`` PAT) rather than a service principal.
    """

    def get_connection(self) -> "Connection":
        """Return a connection object for user authentication."""
        if self.config.is_development:
            token = self.config.databricks_token
            assert token, "DATABRICKS_TOKEN not found in .env-secrets"
            log.debug("Using DATABRICKS_TOKEN for development")
        else:
            token = UserTokenProvider(self.config).get_token()

        return sql.connect(
            server_hostname=self.config.databricks_host,
            http_path=self.config.databricks_http_path,
            access_token=token,
        )


class AzureSPM2MOauthHandler(AbstractHandler):
    """Execute SQL statements against Databricks as the app's service principal.

    Authenticates via Azure AD machine-to-machine (M2M) OAuth using the
    configured Azure Service Principal client ID/secret, independent of any
    signed-in user.
    """

    def get_connection(self) -> "Connection":
        """Return a connection object for application authentication."""
        return sql.connect(
            server_hostname=self.config.databricks_host,
            http_path=self.config.databricks_http_path,
            auth_type=AuthType.AZURE_SP_M2M.value,
            azure_client_id=self.config.m2m_client_id,
            azure_client_secret=self.config.m2m_client_secret,
        )
