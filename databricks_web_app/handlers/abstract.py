"""Abstract class to build SQL queries sender."""

import logging
import re
from abc import ABC, abstractmethod
from typing import Iterable

from databricks_web_app.app_config import AppConfig

import pandas as pd
from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from databricks.sql.client import Connection

log = logging.getLogger(__name__)

_IDENTIFIER_PART = r"(?:`[^`]+`|[A-Za-z_][A-Za-z0-9_]*)"
_IDENTIFIER_PATTERN = re.compile(
    rf"^{_IDENTIFIER_PART}(?:\.{_IDENTIFIER_PART}){{0,2}}$"
)


def _validate_identifier(data_source: str) -> str:
    """Validate that ``data_source`` looks like a trusted table identifier.

    Accepts ``table``, ``schema.table``, or ``catalog.schema.table``, each
    part either a plain SQL identifier or backtick-quoted. This rejects
    obvious injection attempts (whitespace, quotes, statement separators)
    before the value is interpolated into a query, but it is not a
    substitute for treating ``data_source`` as trusted input.
    """
    if not _IDENTIFIER_PATTERN.match(data_source):
        raise ValueError(
            f"Invalid data_source identifier: {data_source!r}. Expected "
            "'table', 'schema.table', or 'catalog.schema.table', each part "
            "a valid SQL identifier optionally wrapped in backticks."
        )

    return data_source


class AbstractHandler(ABC):
    """Abstract class to build SQL queries sender."""

    def __init__(self, config: AppConfig) -> None:
        """Initializes the class with the provided configuration.

        Args:
            config (AppConfig): Configuration object containing necessary settings.
        """
        self.config = config

    @abstractmethod
    def get_connection(self) -> "Connection":
        """Return a connection object for user authentication."""
        raise NotImplementedError

    def fetchall_df(
        self,
        statement: str,
        arrow: bool = True,
    ) -> pd.DataFrame:
        """Fetch query result via user authentication."""
        with self.get_connection() as connection:
            return self.get_dataframe(statement, connection, arrow)

    def exec_statement(self, statement: str) -> None:
        """Execute a statement via user authentication."""
        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement)

    @staticmethod
    def get_dataframe(
        statement: str,
        connection: "Connection",
        arrow: bool = True,
    ) -> pd.DataFrame:
        """Fetch query result as pandas DataFrame.

        If ``arrow`` is True, return as an arrow table.
        """
        with connection.cursor() as cursor:
            cursor.execute(statement)

            if arrow:
                return cursor.fetchall_arrow().to_pandas()

            data = cursor.fetchall()

            assert cursor.description is not None
            # noinspection PyTypeChecker
            columns = [desc[0] for desc in cursor.description]

        return pd.DataFrame(data, columns=columns)

    def get_columns(
        self,
        data_source: str,
        default_columns: Iterable,
    ) -> pd.DataFrame:
        """Return column names for a data source.

        Args:
            data_source: Table identifier (``table``, ``schema.table``, or
                ``catalog.schema.table``). Must be a trusted value -- it is
                validated as identifier-shaped before being interpolated
                into the query, but that is not a substitute for not
                passing untrusted input here.
            default_columns: Column name(s) for the returned DataFrame.

        Returns:
            A DataFrame with one row per column of ``data_source``, indexed
            under ``default_columns``.
        """
        _validate_identifier(data_source)
        query = (
            f"SELECT * FROM {data_source} "
            "LIMIT 0 /* query get_columns_data_source */"
        )

        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(query)

                # noinspection PyTypeChecker
                column_names = (
                    [desc[0] for desc in cursor.description]
                    if cursor.description is not None
                    else []
                )

        return pd.DataFrame(
            column_names,
            columns=list(default_columns),
        )
