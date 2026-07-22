"""ASGI entrypoint for the example app, mirroring a real consumer's server_app.py.

Run with (from ``examples/dev_app``):

    uvicorn --host 0.0.0.0 --port 8765 src.server_app:app
"""

from databricks_web_app import get_server_app

app = get_server_app()
