#!/bin/sh
set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR"

cd ./src

if [ "${SOLARA_APP_ENV:-}" = "development" ]; then
  # solara run serves the frontend UI and backend from a single process,
  # which is enough for local development.
  exec solara run ./dashboard.py --host=0.0.0.0 --production
else
  # In production, server_app:app (server_app.py) is the ASGI object that
  # mounts the Solara server. Adjust the SSL paths, port, and --root-path
  # for your deployment.
  exec uvicorn --workers 1 --host 0.0.0.0 --port 8765 server_app:app \
     --ssl-keyfile=../ssl/priv-key.pem --ssl-certfile=../ssl/fullchain.pem \
     --proxy-headers --root-path /tools/<project-name>
fi
