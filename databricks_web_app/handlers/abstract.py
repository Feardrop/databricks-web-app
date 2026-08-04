"""Abstract class to build SQL queries sender."""

import logging
import re
from abc import ABC, abstractmethod
from typing import Callable, Iterable, Optional, Union

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

QueryIdentifier = Union[str, Callable[[str], str]]


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


def _tag_statement(statement: str, identifier: Optional[QueryIdentifier]) -> str:
    """Prepend ``identifier`` to ``statement`` as a leading SQL comment.

    ``identifier`` may be a plain string or a callable that receives
    ``statement`` and returns the string to use. Returns ``statement``
    unchanged if ``identifier`` is ``None`` or resolves to an empty string.
    """
    if identifier is None:
        return statement

    resolved = identifier(statement) if callable(identifier) else identifier

    if not resolved:
        return statement

    if "*/" in resolved:
        raise ValueError(
            f"Query identifier must not contain '*/': {resolved!r} would "
            "terminate the SQL comment early."
        )

    return f"/* {resolved} */\n{statement}"


class AbstractHandler(ABC):
    """Abstract class to build SQL queries sender."""

    def __init__(
        self,
        config: AppConfig,
        query_identifier: Optional[QueryIdentifier] = None,
    ) -> None:
        """Initializes the class with the provided configuration.

        Args:
            config (AppConfig): Configuration object containing necessary settings.
            query_identifier (Optional[QueryIdentifier]): Default identifier
                prepended as a SQL comment to every statement this handler
                sends, unless overridden per call (see ``fetchall_df``'s and
                ``exec_statement``'s ``query_identifier`` parameter). Either a
                plain string or a callable receiving the outgoing statement
                and returning the string to use.
        """
        self.config = config
        self.query_identifier = query_identifier

    @abstractmethod
    def get_connection(self) -> "Connection":
        """Return a connection object for user authentication."""
        raise NotImplementedError

    def fetchall_df(
        self,
        statement: str,
        arrow: bool = True,
        query_identifier: Optional[QueryIdentifier] = None,
    ) -> pd.DataFrame:
        """Fetch query result via user authentication."""
        tagged = _tag_statement(
            statement,
            query_identifier if query_identifier is not None else self.query_identifier,
        )

        with self.get_connection() as connection:
            return self.get_dataframe(tagged, connection, arrow)

    def exec_statement(
        self,
        statement: str,
        query_identifier: Optional[QueryIdentifier] = None,
    ) -> None:
        """Execute a statement via user authentication."""
        tagged = _tag_statement(
            statement,
            query_identifier if query_identifier is not None else self.query_identifier,
        )

        with self.get_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(tagged)

    @staticmethod
    def get_dataframe(
        statement: str,
        connection: "Connection",
        arrow: bool = True,
        query_identifier: Optional[QueryIdentifier] = None,
    ) -> pd.DataFrame:
        """Fetch query result as pandas DataFrame.

        If ``arrow`` is True, return as an arrow table. ``query_identifier``
        (a string, or a callable receiving the statement and returning the
        string to use) is prepended to the statement as a SQL comment.
        """
        statement = _tag_statement(statement, query_identifier)

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
