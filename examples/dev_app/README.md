# Example: a databricks-web-app consumer

A minimal, runnable stand-in for a real project that depends on
`databricks-web-app`. It shows the two files every consumer needs
(`src/dashboard.py`, `src/server_app.py`) and the Docker-based deployment
files (`Dockerfile`, `entrypoint_command.sh`, `docker-compose-dev.yml`) that
wrap them, adapted from a real consuming project's setup.

The test suite (`tests/test_examples_dev_app.py`) imports the two `src/`
modules directly against the package installed from this repository, so this
example is also a regression check: if it stops importing cleanly, the README
and the package have drifted apart.

## Run without Docker (fastest way to try it)

From the repository root:

```bash
pip install -e .
cp examples/dev_app/.env.example examples/dev_app/.env
cp examples/dev_app/.env-secrets.example examples/dev_app/.env-secrets
# edit both files with real values for your workspace
set -a && source examples/dev_app/.env && set +a
SECRETS_FILE=examples/dev_app/.env-secrets SOLARA_APP_ENV=development \
    solara run examples/dev_app/src/dashboard.py
```

## Run with Docker (mirrors a production-like deployment)

```bash
cd examples/dev_app
cp .env.example .env
cp .env-secrets.example .env-secrets
# edit both files, then compile the lockfile Docker expects:
pip install pip-tools
pip-compile requirements.in
docker compose -f docker-compose-dev.yml up --build
```

The app is served at `http://localhost:8765`.

## What each file demonstrates

| File | Package feature |
| --- | --- |
| `src/dashboard.py` | `AppConfig`, `DatabricksApp`, `DatabricksUserAndM2MConnector`, `OAuthDatabricksErrorBoundary`, `SolaraUserInfoBinding` |
| `src/server_app.py` | `get_server_app` — the ASGI app mounted behind uvicorn in production |
| `.env.example` / `.env-secrets.example` | The full set of `AppConfig` environment variables, split into non-sensitive config and secrets (`SECRETS_FILE`) |
| `Dockerfile` / `entrypoint_command.sh` | The `solara run` (development) vs. `uvicorn server_app:app` (production) split described on `get_server_app`'s docstring |
| `docker-compose-dev.yml` | Loading `.env` for config and mounting `.env-secrets` as a Docker secret consumed via `SECRETS_FILE` |

Treat this directory as a template: copy it into a new repository, replace the
package's own dependency with a released tag, and fill in your workspace's
values.
