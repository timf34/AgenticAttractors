# Sandbox image for agentic-attractor runs. Keep contents FIXED across an
# entire experiment: what's installed is itself an affordance.
# Build: docker build -t attractors-sandbox:v1 docker/
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl jq sqlite3 nano less procps coreutils \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash agent \
    && mkdir -p /workspace && chown agent:agent /workspace

USER agent
WORKDIR /workspace
