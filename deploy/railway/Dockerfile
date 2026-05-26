# Multi-stage Dockerfile for one-click Railway deploys of any cookbook.
#
# Stage 1 builds the omnigraph CLI and server from the public source repo
# pinned to a tagged release. Stage 2 is a debian:bookworm-slim runtime
# with the binaries, every ready cookbook, a default omnigraph.yaml, a
# Cedar-via-YAML policy file, and an idempotent init script that runs as
# Railway's preDeployCommand.
#
# Build context is the cookbooks repo root. `dockerfilePath` is set in
# `deploy/railway/railway.toml` so Railway picks this file up while
# keeping the cookbook directories visible to COPY at the repo root.

ARG OMNIGRAPH_REF=v0.5.0

# ----- Stage 1: build omnigraph from source --------------------------------
FROM rust:1.84-slim-bookworm AS builder

ARG OMNIGRAPH_REF

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential pkg-config libssl-dev git ca-certificates \
       protobuf-compiler libprotobuf-dev \
    && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${OMNIGRAPH_REF}" \
        https://github.com/ModernRelay/omnigraph.git /src

WORKDIR /src

# No --features aws: Railway Bucket exposes plain S3 credentials, no AWS
# Secrets Manager wiring is needed.
RUN cargo build --release --locked -p omnigraph-cli -p omnigraph-server

# ----- Stage 2: runtime image ---------------------------------------------
# Use the ECR Public mirror of the official Debian image to avoid
# anonymous-pull rate limits from shared CI egress (Railway builds share
# outbound IPs with many other tenants).
FROM public.ecr.aws/debian/debian:bookworm-slim AS runtime

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --system omnigraph \
    && useradd --system --gid omnigraph --create-home \
       --home-dir /var/lib/omnigraph --shell /bin/sh omnigraph

COPY --from=builder /src/target/release/omnigraph        /usr/local/bin/omnigraph
COPY --from=builder /src/target/release/omnigraph-server /usr/local/bin/omnigraph-server

# Bake every ready cookbook into the image. The .dockerignore strips out
# docs (README.md / CLAUDE.md / seed.md / .env.omni*) so only the
# schema, seed data, queries, and per-cookbook omnigraph.yaml land here.
COPY industry-intel /cookbooks/industry-intel
COPY pharma-intel   /cookbooks/pharma-intel
COPY second-brain   /cookbooks/second-brain
COPY vc-os          /cookbooks/vc-os

# Server-side config: where the Cedar-via-YAML policy file lives.
COPY deploy/railway/config/omnigraph.yaml /etc/omnigraph/omnigraph.yaml
COPY deploy/railway/config/policy.yaml    /etc/omnigraph/policy.yaml

# Idempotent init runs via railway.toml's preDeployCommand.
COPY deploy/railway/scripts/init.sh /usr/local/bin/omnigraph-railway-init.sh
RUN chmod 0755 /usr/local/bin/omnigraph-railway-init.sh

ENV OMNIGRAPH_BIND=0.0.0.0:8080

EXPOSE 8080

USER omnigraph:omnigraph
WORKDIR /var/lib/omnigraph

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8080/healthz >/dev/null || exit 1

# Default command — Railway overrides via startCommand in railway.toml,
# but this lets `docker run` work standalone for local smoke tests.
CMD ["sh", "-c", "omnigraph-server \"$OMNIGRAPH_TARGET_URI\" --config /etc/omnigraph/omnigraph.yaml --bind ${OMNIGRAPH_BIND}"]
