"""Example Solara dashboard exercising the databricks_web_app public API.

Run it locally (no Docker) from the repository root:

    pip install -e .
    cp examples/dev_app/.env.example examples/dev_app/.env
    cp examples/dev_app/.env-secrets.example examples/dev_app/.env-secrets
    # fill in real values in both files, then:
    set -a && source examples/dev_app/.env && set +a
    SECRETS_FILE=examples/dev_app/.env-secrets SOLARA_APP_ENV=development \
        solara run examples/dev_app/src/dashboard.py

This module intentionally mirrors the wiring pattern documented on
``OAuthDatabricksErrorBoundary`` (see ``databricks_web_app/solara_components.py``)
so the two stay in sync. It also doubles as an integration fixture: the test
suite imports this file to catch drift between the README examples and the
real package API.
"""

from __future__ import annotations

from databricks_web_app import (
    AppConfig,
    DatabricksApp,
    DatabricksUserAndM2MConnector,
    OAuthDatabricksErrorBoundary,
    SolaraUserInfoBinding,
)

import solara

config = AppConfig()


class DevApp(DatabricksApp[DatabricksUserAndM2MConnector]):
    """Lazily construct the Databricks connector used by this example."""

    connector_class = DatabricksUserAndM2MConnector


app = DevApp(config)

user_id = solara.Reactive("")
user_email = solara.Reactive("")
user_name = solara.Reactive("")
user_short_name = solara.Reactive("")

query_result = solara.Reactive("")


def run_query() -> None:
    """Query Databricks as the signed-in user and store the result as text."""
    dataframe = app.databricks_handler.user_handler.fetchall_df("SELECT 1 AS answer")
    query_result.set(dataframe.to_string())


def reset_dashboard_state() -> None:
    """Reset app-specific state after a clearable error is dismissed."""
    query_result.set("")


@solara.component
def DashboardContent():  # pylint: disable=invalid-name
    """Render the example dashboard body."""
    solara.Title("databricks-web-app example")
    solara.Text(f"Signed in as {user_name.value or 'unknown user'}")
    solara.Button("Run test query", on_click=run_query)

    if query_result.value:
        solara.Text(query_result.value)


@solara.component
def DashboardFallback():  # pylint: disable=invalid-name
    """Render a stable layout while an error dialog is shown."""
    solara.Text("The dashboard is temporarily unavailable.")


@solara.component
def Page():  # pylint: disable=invalid-name
    """Render the example app behind the OAuth/Databricks error boundary."""
    OAuthDatabricksErrorBoundary(
        children=DashboardContent,
        fallback=DashboardFallback,
        on_clearable_error_close=reset_dashboard_state,
        app_config=config,
        user_info_binding=SolaraUserInfoBinding(
            set_user_id=user_id.set,
            set_user_email=user_email.set,
            set_user_name=user_name.set,
            set_user_short_name=user_short_name.set,
        ),
    )
