"""Configuration for the OAuth Databricks connector."""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Generic, Mapping, TypeVar, cast, overload

from dotenv import dotenv_values, find_dotenv

SOLARA_APP_ENV = "SOLARA_APP_ENV"
SECRETS_FILE = "SECRETS_FILE"

DATABRICKS_HOST = "DATABRICKS_HOST"
DATABRICKS_TOKEN = "DATABRICKS_TOKEN"
DATABRICKS_WAREHOUSE_ID = "DATABRICKS_WAREHOUSE_ID"

AZURE_CLIENT_ID = "AZURE_CLIENT_ID"
AZURE_CLIENT_ID_PROXY = "AZURE_CLIENT_ID_PROXY"
AZURE_CLIENT_SECRET = "AZURE_CLIENT_SECRET"
AZURE_CLIENT_SECRET_PROXY = "AZURE_CLIENT_SECRET_PROXY"

DATA_ACCESS_PACKAGES_URL = "DATA_ACCESS_PACKAGES_URL"
DATA_ACCESS_MANAGEMENT_PAGE_URL = "DATA_ACCESS_MANAGEMENT_URL"
AZURE_TENANT_ID = "AZURE_TENANT_ID"

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ConfigurationError(ValueError):
    """Raised when the connector configuration is missing or invalid."""


class ConfigAttribute(Generic[T]):
    """Typed descriptor for an application configuration attribute."""

    def __init__(
        self,
        *,
        env: str | None = None,
        sensitive: bool = False,
        required: bool = False,
        transform: Callable[[Any], T] | None = None,
    ) -> None:
        """Initialize the configuration attribute.

        Args:
            env:
                Environment variable associated with the attribute.
            sensitive:
                Whether the value must be redacted from diagnostic output.
            required:
                Whether configuration validation requires a value.
            transform:
                Function converting an input value to the declared type.
                Defaults to ``str``.
        """
        self.name = ""
        self.env = env
        self.sensitive = sensitive
        self.required = required
        self.transform: Callable[[Any], T] = transform or cast(
            Callable[[Any], T],
            str,
        )

    def __set_name__(
        self,
        owner: type[AppConfig],
        name: str,
    ) -> None:
        """Record the attribute name assigned by the owning class."""
        self.name = name

    @overload
    def __get__(
        self,
        config: None,
        owner: type[AppConfig],
    ) -> ConfigAttribute[T]: ...

    @overload
    def __get__(
        self,
        config: AppConfig,
        owner: type[AppConfig],
    ) -> T | None: ...

    def __get__(
        self,
        config: AppConfig | None,
        owner: type[AppConfig],
    ) -> ConfigAttribute[T] | T | None:
        """Return the descriptor or its value for a configuration instance."""
        if config is None:
            return self

        return config._values.get(self.name)

    def __set__(
        self,
        config: AppConfig,
        value: Any,
    ) -> None:
        """Transform and store a configuration value."""
        if value is None:
            config._values.pop(self.name, None)
            return

        try:
            transformed = self.transform(value)
        except (TypeError, ValueError) as error:
            raise ConfigurationError(
                f"Invalid value for configuration field {self.name!r}."
            ) from error

        config._values[self.name] = transformed


def _parse_nonempty_string(value: Any) -> str:
    """Return a stripped, nonempty string."""
    result = str(value).strip()

    if not result:
        raise ConfigurationError("Value must not be empty.")

    return result


def _parse_uuid(value: Any) -> str:
    """Parse a UUID."""
    result = _parse_nonempty_string(value)

    if not re.match(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", result
    ):
        raise ConfigurationError("Invalid UUID.")

    return result


def _parse_email(value: Any) -> str:
    """Parse an email address."""
    result = _parse_nonempty_string(value)

    if not re.match(r"[^@]+@[^@]+\.[^@]+", result):
        raise ConfigurationError("Invalid email address.")

    return result


def _parse_databricks_token(value: Any) -> str:
    """Parse a Databricks token."""
    result = _parse_nonempty_string(value)

    if not re.match(r"^dapi[a-z0-9]{32}-2$", result):
        raise ConfigurationError(
            "Invalid Databricks token. "
            "Must start with 'dapi' and end with '-2' and be 44 characters long."
        )

    return result


def _parse_warehouse_id(value: Any) -> str:
    """Parse a Databricks SQL warehouse ID."""
    result = _parse_nonempty_string(value)

    if not re.match(r"^[a-z0-9]{16}$", result):
        raise ConfigurationError(
            "Invalid Databricks SQL warehouse ID. "
            "Must be 16 characters long and contain only lowercase letters and numbers."
        )

    return result


def _parse_environment(value: Any) -> str:
    """Normalize and validate the application environment."""
    result = _parse_nonempty_string(value).lower()
    supported = {"development", "production"}

    if result not in supported:
        allowed = ", ".join([f"'{v}'" for v in sorted(supported)])
        raise ConfigurationError(
            f"{SOLARA_APP_ENV} must be one of {allowed}; received {value!r}."
        )

    return result


def _parse_valid_file_path(value: Any) -> Path:
    """Parse a file path."""
    result = _parse_nonempty_string(value)

    return Path(result).expanduser()


def _parse_url(value: Any) -> str:
    """Parse a valid URL."""
    result = _parse_nonempty_string(value)

    if not re.match(r"^https?://[^\s/$.?#].[^\s]*$", result):
        raise ConfigurationError("Invalid URL.")
    return result


def _parse_host(value: Any) -> str:
    """Normalize a Databricks workspace URL."""
    result = _parse_url(value).rstrip("/")

    if not result.endswith(".azuredatabricks.net"):
        raise ConfigurationError(
            f"{DATABRICKS_HOST} must match 'https://<workspace>.azuredatabricks.net'."
        )

    return result


class AppConfig:
    """Configuration required by the OAuth Databricks connector.

    Value precedence, from highest to lowest:

    1. Explicit constructor arguments
    2. Process environment variables
    3. Variables from SECRETS_FILE
    4. Class defaults

    Sensitive values are redacted from repr(), debug_string(), and as_dict()
    unless include_sensitive=True is explicitly passed to as_dict().
    """

    solara_app_env = ConfigAttribute(
        env=SOLARA_APP_ENV,
        transform=_parse_environment,
    )
    """Environment used by the Solara application. Only set in development."""

    secrets_file = ConfigAttribute(
        env=SECRETS_FILE,
        transform=_parse_valid_file_path,
    )
    """Path to the secrets file used in production."""

    azure_tenant_id = ConfigAttribute(
        env=AZURE_TENANT_ID,
        transform=_parse_nonempty_string,
    )
    """Microsoft Entra ID tenant identifier. Can be omitted."""

    m2m_client_id_proxy = ConfigAttribute(
        env=AZURE_CLIENT_ID_PROXY,
        transform=_parse_nonempty_string,
    )
    """
    Proxy name of the environment variable containing the Client ID of the
    application for M2M authentication. Set either this or AZURE_CLIENT_ID.
    """

    m2m_client_secret_proxy = ConfigAttribute(
        env=AZURE_CLIENT_SECRET_PROXY,
        transform=_parse_nonempty_string,
    )
    """
    Proxy name of the environment variable containing the Client secret of the
    application for M2M authentication. Set either this or AZURE_CLIENT_SECRET.
    """

    m2m_client_id = ConfigAttribute(
        env=AZURE_CLIENT_ID,
        transform=_parse_uuid,
    )
    """
    Client ID of the primary Azure application for M2M authentication.
    Set either this or AZURE_CLIENT_ID_PROXY.
    """

    m2m_client_secret = ConfigAttribute(
        env=AZURE_CLIENT_SECRET,
        sensitive=True,
        transform=_parse_nonempty_string,
    )
    """
    Client secret of the primary Azure application for M2M authentication.
    Set either this or AZURE_CLIENT_SECRET_PROXY.
    """

    data_access_management_url = ConfigAttribute(
        env=DATA_ACCESS_MANAGEMENT_PAGE_URL,
        transform=_parse_url,
    )
    """URL of the data access management info page."""

    databricks_access_packages_url = ConfigAttribute(
        env=DATA_ACCESS_PACKAGES_URL,
        transform=_parse_url,
    )
    """URL of the Databricks access packages page."""

    databricks_host = ConfigAttribute(
        env=DATABRICKS_HOST,
        required=True,
        transform=_parse_host,
    )
    """Databricks workspace host URL."""

    databricks_warehouse_id = ConfigAttribute(
        env=DATABRICKS_WAREHOUSE_ID,
        required=True,
        transform=_parse_warehouse_id,
    )
    """Databricks SQL Warehouse identifier."""

    databricks_token = ConfigAttribute(
        env=("%s" % DATABRICKS_TOKEN),
        sensitive=True,
        transform=_parse_databricks_token,
    )
    """Databricks authentication token. Only used in development to skip user OAuth."""

    project_name = ConfigAttribute(
        env="PROJECT_NAME",
        required=True,
        transform=_parse_nonempty_string,
    )
    """Name of the consuming web-app. Usually pyproject.toml > project > name."""

    contact_email = ConfigAttribute(
        env="CONTACT_EMAIL",
        transform=_parse_email,
    )
    """
    Contact email address for support and ownership inquiries.
    Usually pyproject.toml > project > author > email.
    """

    _attributes: tuple[ConfigAttribute[Any], ...] | None = None

    def __init__(
        self,
        *,
        environ: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> None:
        """Load and validate connector configuration."""
        self._values: dict[str, Any] = {}
        self._sources: dict[str, str] = {}
        _environ = environ or os.environ
        if _environ is None:
            raise ConfigurationError("No environment variables available.")
        self._environ = _environ
        self._secrets: dict[str, str] = {}

        self._set_defaults()
        self._load_secrets(kwargs)
        self._load_declared_values(self._secrets, "secrets file")
        self._load_declared_values(self._environ, "environment")
        self._load_keyword_arguments(kwargs)
        self._set_logger()
        self._validate()
        self._resolve_indirect_credentials()

    @property
    def databricks_http_path(self) -> str:
        """Return the configured SQL warehouse HTTP path."""
        return f"/sql/1.0/warehouses/{self.databricks_warehouse_id}"

    @property
    def is_development(self) -> bool:
        """Return whether development behavior is active."""
        return self.solara_app_env == "development"

    def as_dict(
        self,
        *,
        include_sensitive: bool = False,
    ) -> dict[str, Any]:
        """Return configured values with secrets redacted by default."""
        result: dict[str, Any] = {}

        for attribute in self.attributes():
            value = getattr(self, attribute.name)

            if value is None:
                continue

            if attribute.sensitive and not include_sensitive:
                result[attribute.name] = "***"
            else:
                result[attribute.name] = value

        return result

    def debug_string(self) -> str:
        """Generates a detailed debug string representation of the current object state.

        The method constructs and returns a multi-line string that includes the names,
        values, and sources of all attributes of the object, excluding any attributes
        with a `None` value. For sensitive attributes, the value is masked with "***".
        The source of each attribute's value is also presented, defaulting to "derived"
        if no explicit source is found.

        Returns:
            str: A multi-line string containing the debug information.
        """
        lines = ["AppConfig("]

        for attribute in self.attributes():
            value = getattr(self, attribute.name)

            if value is None:
                continue

            displayed = "***" if attribute.sensitive else repr(value)
            source = self._sources.get(attribute.name, "derived")

            lines.append(
                f"  {attribute.name}:"
                f"\n    value: {displayed}"
                f"\n    source: {source}"
            )

        lines.append(")")
        return "\n".join(lines)

    @classmethod
    def attributes(cls) -> tuple[ConfigAttribute[Any], ...]:
        """Retrieve and cache configuration attributes defined on the class."""
        cached = cls.__dict__.get("_attributes")

        if isinstance(cached, tuple):
            return cached

        attributes = tuple(
            value
            for value in cls.__dict__.values()
            if isinstance(value, ConfigAttribute)
        )

        cls._attributes = attributes
        return attributes

    def _set_defaults(self) -> None:
        """Set defaults that are not organization-specific."""
        defaults = {
            "solara_app_env": "production",
        }

        for name, value in defaults.items():
            setattr(self, name, value)
            self._sources[name] = "default"

    def _load_secrets(
        self,
        kwargs: Mapping[str, Any],
    ) -> None:
        """Resolve SECRETS_FILE and load its nonempty values."""
        explicit_path = kwargs.get("secrets_file")

        if explicit_path is not None:
            if not isinstance(explicit_path, str):
                raise TypeError(
                    "Configuration argument 'secrets_file' must be a string."
                )

            configured_path = explicit_path.strip()
            source = "constructor"
        else:
            configured_path = self._environ.get(SECRETS_FILE, "").strip()
            source = "environment"

        if not configured_path:
            return

        path = Path(configured_path).expanduser()

        if not path.is_file():
            msg = f"{SECRETS_FILE} does not exist or is not a file: {path!s}"
            logging.error(msg) if not self.is_development else logging.debug(msg)
            try:
                find_dotenv(path.parts[-1], raise_error_if_not_found=True)
            except IOError as error:
                logging.error(f"Could not find {path.parts[-1]} file: {error}")

        loaded_values = dotenv_values(path)

        self.secrets_file = str(path)
        self._sources["secrets_file"] = source
        # noinspection PyTypeChecker
        self._secrets = {
            name: value
            for name, value in loaded_values.items()
            if isinstance(value, str) and value
        }

    def _load_declared_values(
        self,
        source: Mapping[str, str],
        source_name: str,
    ) -> None:
        """Load values mapped directly to declared variables."""
        for attribute in self.attributes():
            if not attribute.env:
                continue

            value = source.get(attribute.env)

            if value is None or value == "":
                continue

            setattr(self, attribute.name, value)
            self._sources[attribute.name] = f"{source_name}: {attribute.env}"

    def _load_keyword_arguments(
        self,
        kwargs: Mapping[str, Any],
    ) -> None:
        """Apply explicit constructor arguments."""
        known_names = {attribute.name for attribute in self.attributes()}
        unknown_names = set(kwargs) - known_names

        if unknown_names:
            names = ", ".join(sorted(unknown_names))
            raise TypeError(f"Unknown configuration argument(s): {names}")

        for name, value in kwargs.items():
            if value is None or name == "secrets_file":
                continue

            setattr(self, name, value)
            self._sources[name] = "constructor"

    def _resolve_proxy_value(
        self,
        *,
        field_name: str,
        proxy_name: str | None,
    ) -> str | None:
        """Resolve a credential through an optional environment proxy."""
        if not proxy_name:
            return None

        if value := self._environ.get(proxy_name):
            self._sources[field_name] = f"environment proxy: {proxy_name}"
            return _parse_nonempty_string(value)

        if value := self._secrets.get(proxy_name):
            self._sources[field_name] = f"secrets-file proxy: {proxy_name}"
            return _parse_nonempty_string(value)

        return None

    def _resolve_direct_or_proxy_value(
        self,
        *,
        field_name: str,
        direct_value: str | None,
        proxy_name: str | None,
    ) -> str | None:
        """Return a direct credential or resolve it through an optional proxy."""
        if direct_value:
            if proxy_name:
                logger.warning(
                    "Both the direct value for %s and proxy variable %s are "
                    "configured. Only the direct value is used; the proxy is "
                    "ignored.",
                    field_name,
                    proxy_name,
                )

            return direct_value

        return self._resolve_proxy_value(
            field_name=field_name,
            proxy_name=proxy_name,
        )

    def _resolve_indirect_credentials(self) -> None:
        """Resolve missing credentials through optional environment proxies."""
        self.m2m_client_id = self._resolve_direct_or_proxy_value(
            field_name="m2m_client_id",
            direct_value=self.m2m_client_id,
            proxy_name=self.m2m_client_id_proxy,
        )

        if not self.m2m_client_id:
            raise ConfigurationError(
                f"Missing M2M client ID. Configure {AZURE_CLIENT_ID} "
                f"directly or configure {AZURE_CLIENT_ID_PROXY} to "
                "reference another variable."
            )

        self.m2m_client_secret = self._resolve_direct_or_proxy_value(
            field_name="m2m_client_secret",
            direct_value=self.m2m_client_secret,
            proxy_name=self.m2m_client_secret_proxy,
        )

        if not self.m2m_client_secret:
            raise ConfigurationError(
                "Missing M2M client secret. Configure "
                f"{AZURE_CLIENT_SECRET} directly or configure "
                f"{AZURE_CLIENT_SECRET_PROXY} to reference another "
                "variable."
            )

    def _validate(self) -> None:
        """Validate required and environment-specific values."""
        missing = [
            attribute.name
            for attribute in self.attributes()
            if attribute.required and not getattr(self, attribute.name)
        ]

        if missing:
            names = ", ".join(sorted(missing))
            raise ConfigurationError(
                f"Missing required configuration field(s): {names}"
            )

        if self.is_development and not self.databricks_token:
            raise ConfigurationError("DATABRICKS_TOKEN is required in development.")

    def _set_logger(self):
        if self.is_development:
            logging.basicConfig(
                level=os.environ.get("LOG_LEVEL", logging.INFO),
                format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                force=True,  # Python >= 3.8
            )

    def __repr__(self) -> str:
        """Represents the string representation of an object for debugging purposes.

        The `__repr__` method is used to return a developer-friendly and unambiguous
        string representation of the object. It calls the `debug_string` method of
        the object to compose this representation.

        Returns:
            str: A string that provides a debug representation of the object.

        """
        return self.debug_string()
