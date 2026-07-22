# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`databricks-web-app` is a Python library of reusable helpers for Solara web
apps that authenticate users and query Databricks via OAuth (on behalf of the
signed-in user) and machine-to-machine (Azure Service Principal) flows. It is
**not published to PyPI** — consumers install it as a git dependency
(`databricks-web-app @ git+https://github.com/feardrop/databricks-web-app.git@<tag>`).

## Commands

Install for development:

```bash
pip install -e .
pip install -r requirements-dev.in   # or pip-compile it first for a pinned lockfile
```

Test:

```bash
pytest                                                    # full suite
pytest -m "not slow"                                      # what CI runs
pytest tests/test_app_config.py -k test_loads_from_environ  # a single test
```

Lint/format/type-check — all run through pre-commit, and CI runs the exact
same command, so a clean local run means CI will pass:

```bash
pre-commit run --all-files                        # ruff, black, isort, mypy, pydoclint, pydocstyle, base hooks
pre-commit run --all-files --hook-stage pre-push  # adds the pytest hook
```

The same tools can be invoked directly: `ruff check .`, `black --check .`,
`isort --check .`, `mypy databricks_web_app`,
`pydoclint --config=pyproject.toml databricks_web_app`,
`pydocstyle databricks_web_app`.

Run the example consumer app (see `examples/dev_app/README.md` for the
no-Docker variant):

```bash
cd examples/dev_app
cp .env.example .env && cp .env-secrets.example .env-secrets  # fill in real values
docker compose -f docker-compose-dev.yml up --build
```

## Architecture

### Package layers (`databricks_web_app/`)

- **`app_config.py`** — `AppConfig`: env-var-driven, validated configuration.
  Each field is a `ConfigAttribute` descriptor with a `transform`
  (parse/validate function), optional `env` var name, `required`, and
  `sensitive` (redacted from `repr()`/`debug_string()`). Values resolve in
  order: constructor kwargs > process env > `SECRETS_FILE` > class defaults.
  `m2m_client_id`/`m2m_client_secret` can additionally resolve through
  `*_PROXY` env vars — an indirection for orgs that inject the secret under a
  different variable name than this package expects.
- **`handlers/`** — `AbstractHandler` subclasses that own `get_connection()`
  and run SQL (`fetchall_df`, `exec_statement`). `AccessTokenUserHandler`
  authenticates as the signed-in user (OAuth access token, via `auth/`);
  `AzureSPM2MOauthHandler` authenticates as the app's own service principal.
- **`connector.py`** — `AbstractConnector`/`DatabricksUserAndM2MConnector`: a
  composition layer owning one user handler and one M2M handler, built via
  injectable factories (defaulting to the two handlers above). Note:
  `AbstractConnector.__init__` declares a `handler_factory` parameter that
  concrete connectors don't actually use — `DatabricksUserAndM2MConnector`
  takes two factories instead. This mismatch is intentional (documented with
  a `# type: ignore[call-arg]` where `app.py` calls a connector generically);
  don't "fix" the abstract signature without reading that comment first.
- **`app.py`** — `DatabricksApp`: a generic holder that lazily constructs
  `connector_class(config)` once and caches it (`databricks_handler`
  property); setting it directly raises on purpose, since `connector_class`
  is meant to be set instead. `get_server_app()` builds the Starlette app
  consumers mount in production: one custom route
  (`/__keepalive_backend`, which re-captures a refreshed OAuth token into
  `auth/token_store.TOKEN_BY_SESSION` keyed by the `solara-session-id`
  cookie) plus `solara.server.starlette.routes` mounted at `/`.
- **`auth/`** — `token_store.TOKEN_BY_SESSION` is a plain in-memory dict
  shared process-wide (session id -> access token — read this before
  assuming any request-scoped isolation exists). `token_providers.UserTokenProvider`
  reads the current user's token (in-memory store first, then request
  headers as fallback) and verifies its JWT signature against Azure AD's
  JWKS endpoint.
- **`error_handlers/`** — each `RichErrorDialogBase` subclass has a
  `matches(exception)` for one specific failure (expired token, expired
  client secret, invalid Databricks token, missing Databricks permissions)
  and a `build_dialog_config(...)` that renders a Solara modal instead of a
  raw traceback. Handler *order* matters: `solara_components.py`'s
  `_ERROR_DIALOG_HANDLER_TYPES` tuple defines priority, with
  `GenericApplicationErrorDialog` last as the catch-all.
- **`solara_components.py`** — `OAuthDatabricksErrorBoundary`: the top-level
  component consumers wrap their dashboard in. It runs the ordered error
  handlers above against Solara's `use_exception()`, and — if given a
  `SolaraUserInfoBinding` — populates app-owned reactive state from
  OAuth/reverse-proxy request headers on first render.

### `examples/dev_app` is a drift detector, not just documentation

`examples/dev_app/src/{dashboard.py,server_app.py}` is a full reference
consumer wired against the real public API. `tests/test_examples_dev_app.py`
imports these two files directly (by file path, via `importlib`) against
whatever version of `databricks_web_app` is installed in the test
environment, so a breaking API change surfaces as a test failure here before
it reaches a real consumer. Keep the example in sync with any public API
change, not just the README prose.

### Branching and release model

Three-tier flow, partly enforced by CI: `develop` (integration) →
`release/vX.Y.Z` (cut from `develop`; carries only the version bump and
changelog cutover) → `main` (released only). `.github/workflows/ci.yml`'s
`branch-policy` job fails any PR into `main` whose source branch isn't
`release/*`. `.github/workflows/release.yml` fires after CI succeeds on
`main`; it's a no-op unless `pyproject.toml`'s version has no matching
`vX.Y.Z` tag yet, in which case it tags, builds the sdist/wheel, extracts
that version's `CHANGELOG.md` section (via
`.github/scripts/extract_changelog_section.py`) as release notes, publishes
a GitHub Release, and merges `main` back into `develop`. Nothing about the
version number or changelog content is generated automatically — see the
README's "Branching"/"Releasing" sections for the manual steps.

### Conventions

- Commit and PR titles follow [Conventional Commits](https://www.conventionalcommits.org/)
  (`conventionalcommit.json` lists the accepted types).
- `CHANGELOG.md` follows [Keep a Changelog](https://keepachangelog.com/); add
  entries under `## [Unreleased]` in the same PR that makes the change.

### Lint scoping quirks (don't "fix" these without reading why first)

- `pydocstyle`'s `D105` is disabled repo-wide (`pyproject.toml`
  `[tool.pydocstyle]`) because it's incompatible with `D418` for the
  `@overload`-decorated `ConfigAttribute.__get__` stubs in `app_config.py`.
- `mypy`, `pydoclint`, and `pydocstyle` are scoped to `databricks_web_app/`
  only (see `.pre-commit-config.yaml`), not `tests/` or `examples/`.
- `pandas`, `pyjwt`, and `requests` are real runtime dependencies (imported
  in `handlers/abstract.py`, `auth/token_providers.py`,
  `error_handlers/authentication.py`) even though nothing in the top-level
  package `__init__.py` hints at them — keep them in `pyproject.toml`'s
  `dependencies` if that list ever gets edited.
