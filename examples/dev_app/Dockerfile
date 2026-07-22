# Template Dockerfile for a project consuming databricks-web-app.
# Adapted from a real consumer's Dockerfile; adjust paths/ports as needed.
#
# Before building, compile requirements.txt from requirements.in:
#   pip install pip-tools
#   pip-compile requirements.in

FROM python:3.10-bullseye

# Core Python build deps
RUN apt-get update && apt-get install -y \
    python3-pip \
    python3-dev \
    python3-setuptools \
    --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*

# Locales (adjust to your deployment locale)
RUN apt-get update && apt-get install -y \
    locales \
 && echo "en_US.UTF-8 UTF-8" > /etc/locale.gen \
 && locale-gen

# Upgrade pip + install uv
RUN pip3 install --compile --upgrade pip uv

# Runtime utilities
RUN apt-get update && apt-get install -y \
    ca-certificates \
    gettext \
 && rm -rf /var/lib/apt/lists/*

# App root
WORKDIR /web-app

# Copy deps first (cache layer)
COPY requirements.txt .

# Install Python deps via uv
RUN uv pip install --system --compile \
    -r requirements.txt

# Copy full source
COPY . .

# Entrypoint permissions
RUN chmod +x /web-app/entrypoint_command.sh

WORKDIR /web-app/src

ENV SOLARA_APP=dashboard.py

ENTRYPOINT ["/web-app/entrypoint_command.sh"]
