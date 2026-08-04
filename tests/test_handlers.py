"""Tests for databricks_web_app.handlers.abstract.

Uses fake Connection/Cursor objects (mirroring databricks.sql.client's context
manager protocol, where __exit__ calls close()) to verify that AbstractHandler
always closes the connection it opens — including when the query raises.
"""

from __future__ import annotations

from databricks_web_app import AppConfig
from databricks_web_app.handlers.abstract import AbstractHandler

import pandas as pd
import pytest


class _FakeArrowTable:
    """Stand-in for the object returned by cursor.fetchall_arrow()."""

    def __init__(self, rows: list[tuple], description: list[tuple[str]]) -> None:
        self._rows = rows
        self._description = description

    def to_pandas(self) -> pd.DataFrame:
        columns = [desc[0] for desc in self._description]
        return pd.DataFrame(self._rows, columns=columns)


class _FakeCursor:
    """Fake cursor recording execute() calls and its own close() state."""

    def __init__(
        self,
        description: list[tuple[str]],
        rows: list[tuple],
        raise_on_execute: Exception | None = None,
    ) -> None:
        self.description = description
        self.rows = rows
        self.executed: list[str] = []
        self.closed = False
        self._raise_on_execute = raise_on_execute

    def execute(self, statement: str) -> None:
        self.executed.append(statement)

        if self._raise_on_execute is not None:
            raise self._raise_on_execute

    def fetchall(self) -> list[tuple]:
        return self.rows

    def fetchall_arrow(self) -> _FakeArrowTable:
        return _FakeArrowTable(self.rows, self.description)

    def __enter__(self) -> "_FakeCursor":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.closed = True


class _FakeConnection:
    """Fake Databricks SQL connection recording close() state."""

    def __init__(self, cursor: _FakeCursor) -> None:
        self._cursor = cursor
        self.closed = False

    def cursor(self) -> _FakeCursor:
        return self._cursor

    def close(self) -> None:
        self.closed = True

    def __enter__(self) -> "_FakeConnection":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()


class _FakeHandler(AbstractHandler):
    """Concrete handler that returns a pre-built fake connection."""

    def __init__(self, config: AppConfig, connection: _FakeConnection) -> None:
        super().__init__(config)
        self._connection = connection

    def get_connection(self) -> _FakeConnection:  # type: ignore[override]
        return self._connection


def _make_handler(
    app_config: AppConfig,
    *,
    rows: list[tuple] | None = None,
    description: list[tuple[str]] | None = None,
    raise_on_execute: Exception | None = None,
) -> tuple[_FakeHandler, _FakeConnection, _FakeCursor]:
    cursor = _FakeCursor(
        description=description or [("col1",), ("col2",)],
        rows=rows if rows is not None else [(1, 2), (3, 4)],
        raise_on_execute=raise_on_execute,
    )
    connection = _FakeConnection(cursor)
    handler = _FakeHandler(app_config, connection)
    return handler, connection, cursor


class TestGetDataframe:
    """Direct tests for AbstractHandler.get_dataframe (arrow and non-arrow)."""

    def test_arrow_path_returns_dataframe(self, app_config: AppConfig):
        _, connection, _ = _make_handler(app_config)

        with connection as conn:
            df = AbstractHandler.get_dataframe("SELECT 1", conn, arrow=True)

        assert list(df.columns) == ["col1", "col2"]
        assert df.to_dict("records") == [
            {"col1": 1, "col2": 2},
            {"col1": 3, "col2": 4},
        ]

    def test_non_arrow_path_returns_dataframe(self, app_config: AppConfig):
        _, connection, _ = _make_handler(app_config)

        with connection as conn:
            df = AbstractHandler.get_dataframe("SELECT 1", conn, arrow=False)

        assert list(df.columns) == ["col1", "col2"]
        assert df.to_dict("records") == [
            {"col1": 1, "col2": 2},
            {"col1": 3, "col2": 4},
        ]

    def test_executes_given_statement(self, app_config: AppConfig):
        _, connection, cursor = _make_handler(app_config)

        with connection as conn:
            AbstractHandler.get_dataframe("SELECT 42", conn)

        assert cursor.executed == ["SELECT 42"]


class TestFetchallDf:
    """Tests for AbstractHandler.fetchall_df (and get_dataframe)."""

    def test_closes_connection_on_success(self, app_config: AppConfig):
        handler, connection, cursor = _make_handler(app_config)

        df = handler.fetchall_df("SELECT 1")

        assert connection.closed is True
        assert cursor.executed == ["SELECT 1"]
        assert list(df.columns) == ["col1", "col2"]
        assert len(df) == 2

    def test_closes_connection_on_error(self, app_config: AppConfig):
        handler, connection, _ = _make_handler(
            app_config, raise_on_execute=RuntimeError("boom")
        )

        with pytest.raises(RuntimeError):
            handler.fetchall_df("SELECT 1")

        assert connection.closed is True

    def test_non_arrow_path_closes_connection(self, app_config: AppConfig):
        handler, connection, cursor = _make_handler(app_config)

        df = handler.fetchall_df("SELECT 1", arrow=False)

        assert connection.closed is True
        assert cursor.executed == ["SELECT 1"]
        assert list(df.columns) == ["col1", "col2"]
        assert len(df) == 2


class TestExecStatement:
    """Tests for AbstractHandler.exec_statement."""

    def test_closes_connection_on_success(self, app_config: AppConfig):
        handler, connection, cursor = _make_handler(app_config)

        handler.exec_statement("CREATE TABLE foo")

        assert connection.closed is True
        assert cursor.executed == ["CREATE TABLE foo"]

    def test_closes_connection_on_error(self, app_config: AppConfig):
        handler, connection, _ = _make_handler(
            app_config, raise_on_execute=RuntimeError("boom")
        )

        with pytest.raises(RuntimeError):
            handler.exec_statement("CREATE TABLE foo")

        assert connection.closed is True


class TestGetColumns:
    """Tests for AbstractHandler.get_columns."""

    def test_closes_connection_on_success(self, app_config: AppConfig):
        handler, connection, cursor = _make_handler(app_config)

        df = handler.get_columns("main.default.my_table", default_columns=("name",))

        assert connection.closed is True
        assert cursor.executed[0].startswith("SELECT * FROM main.default.my_table")
        assert list(df["name"]) == ["col1", "col2"]

    def test_closes_connection_on_error(self, app_config: AppConfig):
        handler, connection, _ = _make_handler(
            app_config, raise_on_execute=RuntimeError("boom")
        )

        with pytest.raises(RuntimeError):
            handler.get_columns("main.default.my_table", default_columns=("name",))

        assert connection.closed is True

    def test_uses_given_default_columns(self, app_config: AppConfig):
        handler, _, _ = _make_handler(app_config)

        df = handler.get_columns("main.default.my_table", default_columns=("name",))

        assert list(df.columns) == ["name"]

    @pytest.mark.parametrize(
        "data_source",
        [
            "my_table",
            "my_schema.my_table",
            "main.default.my_table",
            "`weird table`",
            "main.default.`weird table`",
        ],
    )
    def test_accepts_valid_identifiers(self, app_config: AppConfig, data_source: str):
        handler, _, cursor = _make_handler(app_config)

        handler.get_columns(data_source, default_columns=("name",))

        assert cursor.executed[0].startswith(f"SELECT * FROM {data_source}")

    @pytest.mark.parametrize(
        "data_source",
        [
            "main.default.my_table; DROP TABLE users--",
            "my_table WHERE 1=1",
            "a.b.c.d",
            "",
            "'; DROP TABLE users--",
        ],
    )
    def test_rejects_invalid_identifiers(self, app_config: AppConfig, data_source: str):
        handler, _, _ = _make_handler(app_config)

        with pytest.raises(ValueError, match="Invalid data_source identifier"):
            handler.get_columns(data_source, default_columns=("name",))


class TestQueryIdentifier:
    """Tests for tagging statements with a query_identifier SQL comment."""

    def test_fetchall_df_untagged_by_default(self, app_config: AppConfig):
        handler, _, cursor = _make_handler(app_config)

        handler.fetchall_df("SELECT 1")

        assert cursor.executed == ["SELECT 1"]

    def test_fetchall_df_tags_with_string_identifier(self, app_config: AppConfig):
        handler, _, cursor = _make_handler(app_config)

        handler.fetchall_df("SELECT 1", query_identifier="my-feature")

        assert cursor.executed == ["/* my-feature */\nSELECT 1"]

    def test_fetchall_df_tags_with_callable_identifier(self, app_config: AppConfig):
        handler, _, cursor = _make_handler(app_config)

        handler.fetchall_df(
            "SELECT 1", query_identifier=lambda statement: f"len={len(statement)}"
        )

        assert cursor.executed == ["/* len=8 */\nSELECT 1"]

    def test_exec_statement_tags_with_string_identifier(self, app_config: AppConfig):
        handler, _, cursor = _make_handler(app_config)

        handler.exec_statement("CREATE TABLE foo", query_identifier="my-feature")

        assert cursor.executed == ["/* my-feature */\nCREATE TABLE foo"]

    def test_get_dataframe_tags_with_string_identifier(self, app_config: AppConfig):
        _, connection, cursor = _make_handler(app_config)

        with connection as conn:
            AbstractHandler.get_dataframe(
                "SELECT 1", conn, query_identifier="my-feature"
            )

        assert cursor.executed == ["/* my-feature */\nSELECT 1"]

    def test_instance_default_identifier_used_when_no_override(
        self, app_config: AppConfig
    ):
        handler, _, cursor = _make_handler(app_config)
        handler.query_identifier = "instance-default"

        handler.fetchall_df("SELECT 1")

        assert cursor.executed == ["/* instance-default */\nSELECT 1"]

    def test_per_call_identifier_overrides_instance_default(
        self, app_config: AppConfig
    ):
        handler, _, cursor = _make_handler(app_config)
        handler.query_identifier = "instance-default"

        handler.fetchall_df("SELECT 1", query_identifier="per-call")

        assert cursor.executed == ["/* per-call */\nSELECT 1"]

    def test_empty_identifier_leaves_statement_unchanged(self, app_config: AppConfig):
        handler, _, cursor = _make_handler(app_config)

        handler.fetchall_df("SELECT 1", query_identifier="")

        assert cursor.executed == ["SELECT 1"]

    def test_rejects_identifier_containing_comment_terminator(
        self, app_config: AppConfig
    ):
        handler, _, _ = _make_handler(app_config)

        with pytest.raises(ValueError, match=r"must not contain '\*/'"):
            handler.fetchall_df("SELECT 1", query_identifier="oops */ DROP TABLE foo")
