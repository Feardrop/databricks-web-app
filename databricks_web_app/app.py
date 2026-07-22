"""Module to define a generic Databricks application.

This module provides a class for managing Databricks connections and requests
through a generic handler mechanism.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Generic, TypeVar

from databricks_web_app.app_config import AppConfig

from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from databricks_web_app.connector import AbstractConnector

    from starlette.applications import Starlette
    from starlette.requests import Request


ACCESS_TOKEN_HEADERS = (
    "x-access-token",
    "x-forwarded-access-token",
)

SOLARA_SESSION_COOKIE = "solara-session-id"

Connector = TypeVar("Connector", bound="AbstractConnector")


class DatabricksApp(Generic[Connector]):
    """Application with lazy Databricks connector construction.

    Attributes:
        connector_class: Connector class to use for Databricks connections.
    """

    connector_class: type[Connector]

    def __init__(self, config: AppConfig) -> None:
        """Initialize the DatabricksApp.

        Args:
            config: AppConfig object containing Environment configuration.
        """
        self._databricks_config = config
        self._databricks_handler: Connector | None = None

    @property
    def databricks_handler(self) -> Connector:
        """Return a Databricks connector object."""
        if self._databricks_handler is None:
            # Concrete connectors accept only `config`; the extra
            # `handler_factory` argument on AbstractConnector.__init__ documents
            # the pattern subclasses follow rather than a call signature mypy
            # can verify against `type[Connector]`.
            self._databricks_handler = self.connector_class(
                self._databricks_config  # type: ignore[call-arg]
            )

        assert isinstance(self._databricks_handler, self.connector_class)
        return self._databricks_handler

    @databricks_handler.setter
    def databricks_handler(self, databricks_handler: Connector) -> None:
        """Never set the Databricks connector object directly."""
        raise AttributeError(
            "Cannot set databricks_handler directly. Set connector_class instead."
        )


def get_server_app() -> "Starlette":
    """Return a Starlette application representing the Backend.

    Usage:

        Place in a file called ``src/server_app.py``:

        .. code-block:: python

            from databricks_web_app.app import get_server_app

            app = get_server_app()

        Add these lines to your ``entrypoint_command.sh``:

        .. code-block:: bash

            #!/bin/sh
            set -eu

            SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
            cd "$SCRIPT_DIR"

            cd ./src

            if [ "${SOLARA_APP_ENV:-}" = "development" ]; then
                exec solara run ./dashboard.py --host=0.0.0.0 --production
            else
                # Frontend UI is defined through env. var. SOLARA_APP within Dockerfile.
                # server_app:app (defined in server_app.py) is the Python object
                # representing the backend.
                exec uvicorn --workers 1 --host 0.0.0.0 \
                    --port <your-preferred-port> \
                    server_app:app \
                    --ssl-keyfile=<path-to-priv-key.pem> \
                    --ssl-certfile=<path-to-fullchain.pem> \
                    --proxy-headers \
                    --root-path <path-to-server-app.py-file>
            fi

        And these to your ``Dockerfile`` (change root dir if necessary):

        .. code-block:: shell

            # Entrypoint permissions
            RUN chmod +x /web-app/entrypoint_command.sh

            WORKDIR /web-app/src

            SOLARA_APP_ENV SOLARA_APP=dashboard.py

            ENTRYPOINT ["/web-app/entrypoint_command.sh"]
    """
    import solara.server.starlette
    from starlette.applications import Starlette
    from starlette.responses import Response
    from starlette.routing import Mount, Route

    from .auth.token_store import TOKEN_BY_SESSION

    async def keepalive_backend(request: "Request") -> Response:
        """Catch a refreshed access token."""
        session_id = request.cookies.get(SOLARA_SESSION_COOKIE)
        token = _resolve_access_token(request.headers)

        if session_id and token:
            TOKEN_BY_SESSION[session_id] = token

        return Response(status_code=204)

    app = Starlette(
        routes=[
            Route(
                "/__keepalive_backend",
                endpoint=keepalive_backend,
                methods=["GET"],
            ),
            Mount("/", routes=solara.server.starlette.routes),
        ]
    )

    return app


def _resolve_access_token(
    headers: Mapping[str, str | Sequence[str]],
) -> str | None:
    """Resolve access token from supported headers."""
    for header_name in ACCESS_TOKEN_HEADERS:
        value = headers.get(header_name)

        if not value:
            continue

        if isinstance(value, str):
            return value

        token = value[0]
        if not isinstance(token, str):
            raise TypeError(
                f"Access token from {header_name} has type "
                f"{type(token)}. Expected str."
            )

        return token

    return None


def _require_access_token(
    headers: Mapping[str, str | Sequence[str]],
) -> str:
    """Resolve access token or raise if no supported header contains one."""
    token = _resolve_access_token(headers)

    if token is None:
        joined_headers = ", ".join(ACCESS_TOKEN_HEADERS)
        raise AttributeError(
            f"No access token found in supported headers: {joined_headers}."
        )

    return token
