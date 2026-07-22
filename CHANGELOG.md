# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Nothing has been released yet; everything below is still unreleased, pending
the initial `0.0.1` release.

## [Unreleased]

### Added

- `databricks_web_app` package: `AppConfig`, `DatabricksApp`/`get_server_app`,
  `AbstractConnector`/`DatabricksUserAndM2MConnector`, Databricks SQL
  handlers, OAuth token providers, and Solara error-boundary components.
- Project tooling: `pyproject.toml`, `pylintrc`, `.pre-commit-config.yaml`,
  `conventionalcommit.json`, `requirements.in`/`requirements-dev.in`.
- `README.md` with installation, configuration, and usage documentation.
- `LICENSE` (MIT).
- `py.typed` marker so consumers' type checkers pick up inline type hints.
- Unit tests for `AppConfig` parsing/validation, error-handler matching,
  `solara_components` helper functions, `DatabricksApp`/`get_server_app`, and
  the connector classes.
- `examples/dev_app`: a runnable reference consumer (`src/dashboard.py`,
  `src/server_app.py`, `Dockerfile`, `entrypoint_command.sh`,
  `docker-compose-dev.yml`, `.env`/`.env-secrets` templates) plus integration
  tests that import it directly to catch drift between the docs and the
  package API.
- README sections on reusing a connector via `DatabricksApp` and on deploying
  a consuming project (Docker/entrypoint/compose pattern).
- GitHub Actions CI workflow running lint and tests.
- `pre-commit` hooks for `mypy` and the `pytest` suite (the latter on the
  `pre-push` stage), plus README instructions for installing both hook stages.

### Fixed

- Added `pandas`, `pyjwt`, and `requests` to `project.dependencies` in
  `pyproject.toml` — these are imported by the package but were missing,
  which would break installs in consuming projects.
- Resolved the two `mypy` errors surfaced once CI was added (an `Optional[str]`
  narrowing gap in `auth/token_providers.py` and a documented type-ignore for
  the `AbstractConnector`/concrete-connector `__init__` signature mismatch in
  `app.py`) so the new CI workflow passes.
- Resolved a `pydocstyle` D105/D418 conflict on the `@overload`-decorated
  `ConfigAttribute.__get__` stubs that would have failed the new CI workflow.
- Scoped the `pydoclint`/`pydocstyle` pre-commit hooks to `databricks_web_app/`
  (matching CI); they previously also targeted `tests/`, where undocumented
  test methods and `tests/__init__.py` made the hooks fail.

[Unreleased]: https://github.com/feardrop/databricks-web-app/commits/main
