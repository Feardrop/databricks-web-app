# databricks-web-app

Reusable Python helpers for [Solara](https://solara.dev/) web apps that
authenticate users and query [Databricks](https://www.databricks.com/) through
OAuth (on behalf of the signed-in user) and machine-to-machine (M2M) flows.

The package bundles the pieces a Solara + Databricks dashboard needs so they
don't have to be reimplemented per project:

- **`AppConfig`** — typed, validated configuration loaded from environment
  variables and/or a secrets file, with sensitive values redacted from
  `repr()`/debug output.
- **`DatabricksApp`** / **`get_server_app`** — a small Starlette app that
  mounts the Solara server and captures refreshed OAuth access tokens.
- **`AbstractConnector`** / **`DatabricksUserAndM2MConnector`** and the
  underlying `AccessTokenUserHandler` / `AzureSPM2MOauthHandler` — send SQL
  statements to a Databricks SQL warehouse either as the logged-in user or as
  a service principal.
- **`OAuthDatabricksErrorBoundary`** / **`SolaraUserInfoBinding`** — a Solara
  error boundary that turns common OAuth/Databricks failures (expired
  tokens, expired client secrets, missing permissions) into rich, actionable
  modal dialogs instead of raw tracebacks.

## Installation

This package is not published to PyPI. Install it directly from GitHub in the
consuming project.

With `pip`/`requirements.in` (used with `pip-tools`):

```
databricks-web-app @ git+https://github.com/feardrop/databricks-web-app.git@main
```

With `pyproject.toml`:

```toml
dependencies = [
    "databricks-web-app @ git+https://github.com/feardrop/databricks-web-app.git@main",
]
```

Pin to a commit SHA instead of `@main` for reproducible installs, e.g.
`@6b81d89`. Once a tagged release exists, pin to that tag instead (e.g.
`@v0.0.1`).

## Configuration

`AppConfig` reads its values with the following precedence (highest first):

1. Explicit constructor keyword arguments
2. Process environment variables
3. Variables from the file referenced by `SECRETS_FILE`
4. Class defaults

| Environment variable          | Required                | Description                                                        |
| ------------------------------ | ------------------------ | -------------------------------------------------------------------- |
| `DATABRICKS_HOST`               | yes                      | Workspace URL, e.g. `https://<workspace>.azuredatabricks.net`         |
| `DATABRICKS_WAREHOUSE_ID`       | yes                      | 16-character SQL warehouse ID                                        |
| `PROJECT_NAME`                  | yes                      | Name of the consuming app (used in error-dialog mailto links)        |
| `AZURE_CLIENT_ID`                | yes (or the proxy below) | Client ID of the Azure AD app used for M2M auth                      |
| `AZURE_CLIENT_SECRET`           | yes (or the proxy below) | Client secret of the Azure AD app used for M2M auth                  |
| `AZURE_CLIENT_ID_PROXY`         | no                       | Name of another env var that holds the client ID                     |
| `AZURE_CLIENT_SECRET_PROXY`     | no                       | Name of another env var that holds the client secret                 |
| `AZURE_TENANT_ID`               | no                       | Fallback tenant ID if it can't be derived from the connection        |
| `DATABRICKS_TOKEN`               | development only         | PAT used instead of OAuth while `SOLARA_APP_ENV=development`         |
| `SOLARA_APP_ENV`                | no (default `production`)| `development` or `production`                                        |
| `SECRETS_FILE`                  | no                       | Path to a dotenv-style file with any of the above                    |
| `CONTACT_EMAIL`                  | no                       | Support contact used in error-dialog mailto links                    |
| `DATA_ACCESS_MANAGEMENT_URL`    | no                       | Link shown in the "missing permissions" error dialog                 |
| `DATA_ACCESS_PACKAGES_URL`      | no                       | Link shown in the "missing permissions" error dialog                 |

```python
from databricks_web_app import AppConfig

config = AppConfig()
print(config.debug_string())  # sensitive values are redacted
```

## Usage

### Backend: mount the Solara app behind a Starlette server

```python
# server_app.py
from databricks_web_app import get_server_app

app = get_server_app()
```

### Querying Databricks

```python
from databricks_web_app import AppConfig, DatabricksUserAndM2MConnector

config = AppConfig()
connector = DatabricksUserAndM2MConnector(config)

# As the signed-in user (requires the OAuth access-token header/cookie)
df = connector.user_handler.fetchall_df("SELECT * FROM main.default.my_table")

# As the service principal (machine-to-machine)
df = connector.m2m_handler.fetchall_df("SELECT * FROM main.default.my_table")
```

Build a custom connector by subclassing `AbstractConnector` and wiring your
own handler factories; see the docstring on `AbstractConnector` for a minimal
example.

### Reusing one connector across requests with DatabricksApp

Constructing a connector on every request is wasteful. `DatabricksApp` holds
one lazily-constructed connector per process — build it once at import time
and pull the handler out wherever you need it:

```python
from databricks_web_app import AppConfig, DatabricksApp, DatabricksUserAndM2MConnector

config = AppConfig()


class MyApp(DatabricksApp[DatabricksUserAndM2MConnector]):
    connector_class = DatabricksUserAndM2MConnector


app = MyApp(config)

# Elsewhere, e.g. inside a Solara component's event handler:
df = app.databricks_handler.user_handler.fetchall_df("SELECT 1")
```

`app.databricks_handler` builds the connector on first access and reuses it
afterwards; setting it directly raises `AttributeError` on purpose — set
`connector_class` instead.

### Solara error boundary and user info

```python
import solara
from databricks_web_app import AppConfig, OAuthDatabricksErrorBoundary, SolaraUserInfoBinding

user_id = solara.Reactive("")
user_email = solara.Reactive("")
user_name = solara.Reactive("")
user_short_name = solara.Reactive("")


@solara.component
def DashboardContent():
    ...


@solara.component
def Page():
    OAuthDatabricksErrorBoundary(
        children=DashboardContent,
        fallback=lambda: solara.Text("Something went wrong."),
        on_clearable_error_close=lambda: None,
        app_config=AppConfig(),
        user_info_binding=SolaraUserInfoBinding(
            set_user_id=user_id.set,
            set_user_email=user_email.set,
            set_user_name=user_name.set,
            set_user_short_name=user_short_name.set,
        ),
    )
```

See the docstring on `OAuthDatabricksErrorBoundary` for the full dashboard
wiring pattern (header, footer, layout fallback).

### Full example

[`examples/dev_app`](examples/dev_app) is a small, runnable consuming project
that wires up all of the above (`AppConfig`, `DatabricksApp`,
`DatabricksUserAndM2MConnector`, `OAuthDatabricksErrorBoundary`,
`SolaraUserInfoBinding`, `get_server_app`). Its `src/dashboard.py` and
`src/server_app.py` are also imported directly by this repository's test
suite, so they stay accurate as the package evolves. Start there if you want
something to copy into a new project.

## Deploying a consuming project

A consuming project is a small wrapper around this package: a Solara
`dashboard.py` (development UI) plus a `server_app.py` exposing the ASGI app
from `get_server_app()` (production), both under `src/`, driven by a Dockerfile
whose entrypoint picks between the two based on `SOLARA_APP_ENV`.

```
web-app/
├── Dockerfile               # installs databricks-web-app from requirements.in
├── entrypoint_command.sh    # SOLARA_APP_ENV=development -> solara run; else uvicorn
├── docker-compose-dev.yml   # loads .env, mounts .env-secrets via SECRETS_FILE
├── requirements.in          # databricks-web-app @ git+https://...
└── src/
    ├── dashboard.py         # Solara UI (development)
    └── server_app.py        # app = get_server_app() (production)
```

The two things worth knowing when adapting this:

- **Config vs. secrets.** Non-sensitive `AppConfig` values come from `.env`
  (compose `env_file`); secrets live in a separate file mounted as a Docker
  secret and read through `SECRETS_FILE` — never bake them into the image.
- **One image, two modes.** The entrypoint runs `solara run` in development and
  `uvicorn server_app:app` in production, selected by `SOLARA_APP_ENV`.

[`examples/dev_app`](examples/dev_app) is a complete, runnable version of this
layout. After filling in its `.env`/`.env-secrets`, one command starts it:

```bash
docker compose -f docker-compose-dev.yml up --build
```

## Development

Clone the repository and install it in editable mode along with the
development tools:

```bash
python -m venv venv
source venv/bin/activate
pip install pip-tools
pip-compile requirements.in
pip-compile requirements-dev.in
pip install -r requirements-dev.txt
```

### Pre-commit hooks

Linting, type checking, and the test suite all run through
[pre-commit](https://pre-commit.com/) (installed by the step above). Install
both hook stages once per clone:

```bash
pre-commit install                       # linters + formatters on `git commit`
pre-commit install --hook-type pre-push  # full test suite on `git push`
```

From then on the hooks run automatically. The commit stage runs the fast
checks (ruff, black, isort, pydoclint, pydocstyle, mypy, plus whitespace/JSON/
YAML/TOML checks); the push stage runs `pytest`. To run everything on demand:

```bash
pre-commit run --all-files                     # all commit-stage hooks
pre-commit run --all-files --hook-stage pre-push  # add the pytest hook
```

The same tools can also be invoked directly, e.g. `pytest`, `ruff check .`,
`black --check .`, `isort --check .`, `mypy databricks_web_app`.

Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
(see `conventionalcommit.json` for the accepted types).

### Branching

- `main` — released code only. Every commit on `main` is a tagged release or
  about to become one via the release automation below. Never commit or PR
  directly into it, other than from a `release/vX.Y.Z` branch.
- `develop` — the integration branch. Feature and fix branches are cut from
  `develop` and PR'd back into `develop`.
- `release/vX.Y.Z` — cut from `develop` when preparing a release; carries
  only the version bump and changelog cutover described below. PR'd into
  `main`. `.github/workflows/ci.yml` has a `branch-policy` job that fails any
  PR into `main` whose source branch doesn't match `release/*`.

```
feature/* ──PR──▶ develop ──branch──▶ release/vX.Y.Z ──PR──▶ main ──▶ tag + GitHub Release
                     ▲                                         │
                     └─────────────── auto merge-back ──────────┘
```

If you add required status checks in branch protection, require `lint`,
`test-summary`, and (for `main`) `branch-policy` — **not** `test`. `test` is
a matrix job, so GitHub reports each Python version as its own check
(`test (3.10)`, etc.) and never a check literally named `test`; requiring
that name leaves the PR waiting on a check that will never arrive.
`test-summary` exists specifically to give the matrix one stable required
name.

### Releasing

1. From `develop`, create `release/vX.Y.Z` (decide the version from what's
   under `## [Unreleased]` in [`CHANGELOG.md`](CHANGELOG.md)).
2. On that branch, in `CHANGELOG.md`, rename `## [Unreleased]` to
   `## [X.Y.Z] - <YYYY-MM-DD>` and add a fresh, empty `## [Unreleased]` above
   it.
3. Bump `version` in `pyproject.toml` to match.
4. Commit (e.g. `chore(release): vX.Y.Z`), open a PR from `release/vX.Y.Z`
   into `main`, get it through CI, and merge it.

Once CI passes on `main`, [`.github/workflows/release.yml`](.github/workflows/release.yml)
takes over automatically:

- Reads the version from `pyproject.toml`; if a `vX.Y.Z` tag already exists,
  it stops here — so any other merge to `main` is a no-op.
- Otherwise builds the sdist/wheel, pulls that version's section out of
  `CHANGELOG.md` as release notes, and publishes a GitHub Release with the
  tag and built artifacts attached.
- Merges `main` back into `develop` so the next release branch starts from
  the bumped version and trimmed changelog. If that merge conflicts, the job
  fails and needs a manual `git checkout develop && git merge main`.

No PyPI publishing is involved — see [Installation](#installation) for how
consumers pin to a release tag.

## License

MIT — see [LICENSE](LICENSE).
