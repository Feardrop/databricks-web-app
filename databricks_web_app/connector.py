"""Implementation to send SQL queries to databricks."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import cast

from databricks_web_app.handlers import (
    AccessTokenUserHandler,
    AzureSPM2MOauthHandler,
)

from typing_extensions import TYPE_CHECKING

if TYPE_CHECKING:
    from databricks_web_app.app_config import AppConfig
    from databricks_web_app.handlers.abstract import AbstractHandler


class AbstractConnector(ABC):
    """Use astract connector to send SQL queries to databricks.

    Example:
        .. code::python
            import pandas

            class AzureHandler(AbstractHandler):
                # implement handler methods
                pass

            class AzureConnector(AbstractConnector):

                azure_handler_class = AzureHandler

                def __init__(self) -> None:
                    # noinspection PyAbstractClass
                    self.azure_handler = self.azure_handler_class()

                def query_data(self, *args, **kwargs) -> pandas.DataFrame:
                    return self.azure_handler.fetchall_df(*args, **kwargs)
    """

    # define handler classes

    @abstractmethod
    def __init__(
        self,
        config: "AppConfig",
        handler_factory: Callable[
            ["AppConfig"],
            "AbstractHandler",
        ],
    ):
        """Initialize the AbstractConnector and the used handler(s) with the app_config."""
        self.config = config
        self.handler = handler_factory(config)
        raise NotImplementedError


class DatabricksUserAndM2MConnector(AbstractConnector):
    """Manages the connection with Databricks OAuth.

    This class provides mechanisms to handle both user and machine-to-machine
    authentication for connecting to Databricks, leveraging factory functions to
    instantiate the respective authentication handlers.

    Attributes:
        config (OAuthDatabricksConfig): Configuration object containing settings for
            OAuth integration with Databricks.
        user_handler (AbstractHandler): Instance of a handler responsible for user
            authentication, created using the specified factory function.
        m2m_handler (AbstractHandler): Instance of a handler responsible for
            machine-to-machine authentication, created using the specified factory
            function.
    """

    def __init__(
        self,
        config: "AppConfig",
        user_handler_factory: Callable[
            ["AppConfig"], "AbstractHandler"
        ] = AccessTokenUserHandler,
        m2m_handler_factory: Callable[
            ["AppConfig"], "AbstractHandler"
        ] = AzureSPM2MOauthHandler,
    ) -> None:
        """Initializes an instance of the class.

        Args:
            config (OAuthDatabricksConfig): Configuration object containing settings
                for OAuth integration with Databricks.
            user_handler_factory (Callable[[OAuthDatabricksConfig], AbstractHandler]):
                Factory function to create a user authentication handler. Defaults to
                AccessTokenUserHandler.
            m2m_handler_factory (Callable[[OAuthDatabricksConfig], AbstractHandler]):
                Factory function to create a machine-to-machine authentication handler.
                Defaults to AzureSPM2MOauthHandler.
        """
        self.config = config
        self.user_handler = cast(AccessTokenUserHandler, user_handler_factory(config))
        self.m2m_handler = cast(AzureSPM2MOauthHandler, m2m_handler_factory(config))
