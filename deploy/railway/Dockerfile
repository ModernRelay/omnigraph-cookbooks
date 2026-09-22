# Single-stage Dockerfile for one-click Railway deploys of any cookbook.
#
# Pulls the prebuilt omnigraph CLI + server binaries from the pinned
# GitHub release (no Rust toolchain, no source build) onto a
# debian:trixie-slim runtime, alongside the bundled cookbook cluster
# configs, the template policy bundles, and an idempotent cluster-apply
# init script that runs as Railway's preDeployCommand (OmniGraph 0.11
# is cluster-only — RFC-011).
#
# Base is trixie (Debian 13, glibc 2.41), not bookworm (2.36): the release
# binaries are linked against glibc >= 2.39 and won't run on bookworm.
#
# Build context is the cookbooks repo root. `dockerfilePath` is set in
# railway.toml so Railway picks this file up while keeping the cookbook
# directories visible to COPY at the repo root.

ARG OMNIGRAPH_REF=v0.11.0
# The release publishes linux-x86_64 and (since v0.8.0) linux-arm64.
# Railway runs amd64, so we pin the platform and the x86_64 asset for
# determinism (and so the binary matches the image arch even when built
# on an arm64 host).
ARG OMNIGRAPH_ASSET=omnigraph-linux-x86_64

# Use the ECR Public mirror of the official Debian image to avoid
# anonymous-pull rate limits from shared CI egress (Railway builds share
# outbound IPs with many other tenants).
FROM --platform=linux/amd64 public.ecr.aws/debian/debian:trixie-slim AS runtime

ARG OMNIGRAPH_REF
ARG OMNIGRAPH_ASSET

# ca-certificates + curl are needed both to download the release here and
# for the runtime healthcheck. tar/gzip ship in the base image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Fetch the prebuilt binaries from the public release, verify the checksum,
# and install them. The tarball holds `omnigraph` and `omnigraph-server`
# at its root. Downloaded with original names so the .sha256 (which is in
# `<hash>  <asset>.tar.gz` form) verifies directly. Tarball is removed in
# the same layer so it never lands in the image.
RUN set -eux; \
    cd /tmp; \
    base="https://github.com/ModernRelay/omnigraph/releases/download/${OMNIGRAPH_REF}"; \
    curl -fsSL -O "${base}/${OMNIGRAPH_ASSET}.tar.gz"; \
    curl -fsSL -O "${base}/${OMNIGRAPH_ASSET}.sha256"; \
    sha256sum -c "${OMNIGRAPH_ASSET}.sha256"; \
    tar -xzf "${OMNIGRAPH_ASSET}.tar.gz" -C /usr/local/bin omnigraph omnigraph-server; \
    chmod 0755 /usr/local/bin/omnigraph /usr/local/bin/omnigraph-server; \
    rm -f "${OMNIGRAPH_ASSET}.tar.gz" "${OMNIGRAPH_ASSET}.sha256"; \
    omnigraph --version

RUN groupadd --system omnigraph \
    && useradd --system --gid omnigraph --create-home \
       --home-dir /var/lib/omnigraph --shell /bin/sh omnigraph

# A graph is declared by a cluster config DIRECTORY (cluster.yaml
# + schema + stored queries + policies), not a single schema file, so the
# cookbook configs are bundled — they are a few KiB each. init.sh selects
# one via $OMNIGRAPH_COOKBOOK and points its storage at the Bucket.
COPY industry-intel /opt/cookbooks/industry-intel
COPY pharma-intel   /opt/cookbooks/pharma-intel
COPY second-brain   /opt/cookbooks/second-brain
COPY vc-os          /opt/cookbooks/vc-os
COPY dev-graph      /opt/cookbooks/dev-graph

# Template policy bundles, injected by init.sh for cookbooks that do not
# declare their own `policies:` in cluster.yaml.
COPY deploy/railway/config/policy.railway.yaml        /opt/railway-config/policy.railway.yaml
COPY deploy/railway/config/server.policy.railway.yaml /opt/railway-config/server.policy.railway.yaml

# Idempotent cluster validate/import/apply runs via railway.toml's
# preDeployCommand.
COPY deploy/railway/scripts/init.sh /usr/local/bin/omnigraph-railway-init.sh
RUN chmod 0755 /usr/local/bin/omnigraph-railway-init.sh

ENV OMNIGRAPH_BIND=0.0.0.0:8080

EXPOSE 8080

USER omnigraph:omnigraph
WORKDIR /var/lib/omnigraph

# Railway ignores this instruction (it healthchecks `healthcheckPath` on
# the injected $PORT); it's only consulted by a plain `docker run`. Track
# $PORT so it stays correct under either, falling back to 8080 locally.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8080}/healthz" >/dev/null || exit 1

# Default command — Railway overrides via startCommand in railway.toml,
# but this lets `docker run` work standalone for local smoke tests.
# `exec` so the server (not the shell) is PID 1 and receives SIGTERM.
CMD ["sh", "-c", "exec omnigraph-server --cluster \"$OMNIGRAPH_CLUSTER_URI\" --bind ${OMNIGRAPH_BIND}"]
