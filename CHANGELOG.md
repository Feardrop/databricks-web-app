# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A scheduled `drift-check.yml` workflow that fails if `main` ever ends up
  ahead of `develop` (e.g. an unmerged sync-develop PR), so that no longer
  goes unnoticed. Part of #3.

### Changed

- Four `ConfigAttribute` "docstrings" in `AppConfig`
  (`m2m_client_id`/`m2m_client_secret`, `*_proxy`) were f-strings used as
  bare expression statements — not string literals, so no tooling ever
  captured them as attribute docstrings. Converted to plain string
  literals. Part of #7.
- `AccessTokenUserHandler` and `AzureSPM2MOauthHandler` had identical,
  uninformative docstrings; differentiated (user-token vs.
  service-principal M2M). Part of #7.

### Removed

- `AppConfig._resolve_named_value` and `_parse_port`: both were unused dead
  code (`_parse_port` wasn't wired to any config field). `connector.py`'s
  unused `TypeVar` `T` was removed too. Part of #7.

### Fixed

- `AbstractHandler.fetchall_df`, `exec_statement`, and `get_columns` now
  close the Databricks SQL connection they open (via the connection's
  context-manager protocol), even when the query raises. Previously every
  call opened a connection that was never closed, leaking warehouse
  sessions/sockets over a dashboard's lifetime. Fixes #5.
- `_parse_databricks_token`'s error message said tokens must be 44
  characters long; the actual (unchanged) pattern requires 38.
- `connector.py` docstrings referenced a nonexistent `OAuthDatabricksConfig`
  type instead of `AppConfig`, and had an "astract connector" typo.
- `release.yml`'s `sync-develop` job now opens a PR to merge `main` back
  into `develop` instead of pushing directly, which `develop`'s
  pull-request-only ruleset was silently rejecting. Fixes #3.

## [0.0.1] - 2026-07-22

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
- GitHub Actions CI workflow: a `lint` job that runs `pre-commit run
  --all-files` (single source of truth with local hooks) and a `test` job that
  runs `pytest` across Python 3.10–3.12.
- `pre-commit` hooks for `mypy` and the `pytest` suite (the latter on the
  `pre-push` stage), plus README instructions for installing both hook stages.
- `.github/pull_request_template.md`, with a checklist of Keep a Changelog
  categories (Added/Changed/Fixed/etc.) that a PR can check off multiple of.
- A `develop` integration branch and a three-tier branching model: feature
  branches target `develop`; releases are cut as `release/vX.Y.Z` branches
  from `develop` and PR'd into `main`. `.github/workflows/ci.yml` gained a
  `branch-policy` job that fails any PR into `main` whose source branch
  isn't `release/*`, and now also runs on pushes to `develop`/`release/**`.
  Also added a `test-summary` job giving the `test` matrix a single stable
  check name for branch protection to require (a literal `test` check never
  gets reported for a matrix job).
- `.github/workflows/release.yml`: after CI passes on `main`, publishes a
  GitHub Release (tag, changelog excerpt, built sdist/wheel) whenever
  `pyproject.toml`'s version doesn't have a matching tag yet, then merges
  `main` back into `develop`; a no-op otherwise. See the README's
  "Branching"/"Releasing" sections for the manual steps.
- `.github/scripts/extract_changelog_section.py`, used by the release
  workflow to pull one version's notes out of `CHANGELOG.md`.
- `CLAUDE.md` with the package architecture, branching/release model, and
  lint-scoping quirks, for future AI-assisted work in this repo.

### Changed

- CI now drives linting through `pre-commit` instead of invoking `ruff`,
  `black`, and `isort` directly, so it can no longer drift from the versions
  pinned in `.pre-commit-config.yaml` and now also runs the base hooks
  (whitespace, YAML/JSON/TOML checks).

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

[Unreleased]: https://github.com/feardrop/databricks-web-app/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/feardrop/databricks-web-app/releases/tag/v0.0.1
