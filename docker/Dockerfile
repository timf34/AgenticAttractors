# Sandbox image for agentic-attractor runs. Keep contents FIXED across an
# entire experiment: what's installed is itself an affordance.
# Build: docker build -t attractors-sandbox:v2 docker/
# See CHANGELOG.md for environment version history (v2 adds libfaketime so
# the container clock can follow the simulated clock).
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git curl jq sqlite3 nano less procps coreutils libfaketime \
    && rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/bash agent \
    && mkdir -p /workspace && chown agent:agent /workspace

USER agent
WORKDIR /workspace
