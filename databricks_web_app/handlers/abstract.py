"""Abstract class to build SQL queries sender."""

import logging
from abc import ABC, abstractmethod
from typing import Iterable

from databricks_web_app.app_config import AppConfig

import pandas as pd
from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from databricks.sql.client import Connection

log = logging.getLogger(__name__)


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
        return self.get_dataframe(
            statement,
            self.get_connection(),
            arrow,
        )

    def exec_statement(self, statement: str) -> None:
        """Execute a statement via user authentication."""
        with self.get_connection().cursor() as cursor:
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
        default_columns: Iterable = ("tag_db_alias",),
    ) -> pd.DataFrame:
        """Return column names for a data source."""
        query = (
            f"SELECT * FROM {data_source} "
            "LIMIT 0 /* query get_columns_data_source */"
        )

        connection = self.get_connection()

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
