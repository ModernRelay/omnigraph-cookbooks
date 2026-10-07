# Runtime for an already-applied cluster. Bootstrap and ownership handoff
# are explicit operator steps; see README.md. No startup storage mutations.
ARG OMNIGRAPH_REF=v0.13.0
ARG OMNIGRAPH_ASSET=omnigraph-linux-x86_64

# The released Linux binaries need glibc >= 2.39. Match image and asset arch.
FROM --platform=linux/amd64 public.ecr.aws/debian/debian:trixie-slim AS runtime

ARG OMNIGRAPH_REF
ARG OMNIGRAPH_ASSET

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl \
    && rm -rf /var/lib/apt/lists/*

# Verify the release archive before installing its CLI and server.
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

EXPOSE 8080
USER omnigraph:omnigraph
WORKDIR /var/lib/omnigraph

# Railway uses healthcheckPath; this also supports a plain docker run.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT:-8080}/readyz" >/dev/null || exit 1

# exec delivers SIGTERM to the server; require a cluster root explicitly.
CMD ["sh", "-c", "exec omnigraph-server --cluster \"${OMNIGRAPH_CLUSTER_URI:?set the applied cluster root}\" --bind \"0.0.0.0:${PORT:-8080}\""]
