# Template Dockerfile for a project consuming databricks-web-app.
# Adapted from a real consumer's Dockerfile; adjust paths/ports as needed.
# Builds with a single `docker compose up --build`; no pre-compile step.

FROM python:3.10-bullseye

# Core Python build deps
RUN apt-get update && apt-get install -y \
    git \
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
COPY requirements.in .

# Install Python deps via uv. requirements.in pulls databricks-web-app straight
# from git, so no pip-compile lockfile step is needed to build this example.
RUN uv pip install --system --compile \
    -r requirements.in

# Copy full source
COPY . .

# Entrypoint permissions
RUN chmod +x /web-app/entrypoint_command.sh

WORKDIR /web-app/src

ENV SOLARA_APP=dashboard.py

ENTRYPOINT ["/web-app/entrypoint_command.sh"]
