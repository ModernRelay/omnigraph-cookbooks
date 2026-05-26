#!/bin/sh
# Idempotent first-deploy bootstrap for the Omnigraph Railway template.
#
# Runs as Railway's preDeployCommand. On a fresh deploy the configured
# Bucket is empty, so `omnigraph snapshot` fails — the script then runs
# `omnigraph init` and (unless OMNIGRAPH_LOAD_SEED=false) loads the
# cookbook's bundled seed. On every subsequent deploy the snapshot
# succeeds and the script exits 0 without touching the graph.
#
# Schema changes after the first deploy are *not* applied here. Run
# `omnigraph schema apply` from a workstation against the running server.

set -e

: "${OMNIGRAPH_TARGET_URI:?OMNIGRAPH_TARGET_URI must be set}"

COOKBOOK="${OMNIGRAPH_COOKBOOK:-industry-intel}"
SCHEMA_PATH="${OMNIGRAPH_SCHEMA_PATH:-/cookbooks/$COOKBOOK/schema.pg}"
SEED_PATH="${OMNIGRAPH_SEED_PATH:-/cookbooks/$COOKBOOK/seed.jsonl}"

if [ ! -f "$SCHEMA_PATH" ]; then
  echo "init: schema not found at $SCHEMA_PATH" >&2
  echo "init: check OMNIGRAPH_COOKBOOK (got '$COOKBOOK') or OMNIGRAPH_SCHEMA_PATH" >&2
  exit 64
fi

if omnigraph snapshot "$OMNIGRAPH_TARGET_URI" --json >/dev/null 2>&1; then
  echo "init: graph at $OMNIGRAPH_TARGET_URI already initialized; skipping"
  exit 0
fi

echo "init: cookbook=$COOKBOOK schema=$SCHEMA_PATH target=$OMNIGRAPH_TARGET_URI"
omnigraph init --schema "$SCHEMA_PATH" "$OMNIGRAPH_TARGET_URI"

if [ "${OMNIGRAPH_LOAD_SEED:-true}" = "true" ]; then
  if [ -f "$SEED_PATH" ]; then
    echo "init: loading seed from $SEED_PATH (mode=merge)"
    omnigraph load --data "$SEED_PATH" --mode merge "$OMNIGRAPH_TARGET_URI"
  else
    echo "init: no seed file at $SEED_PATH; continuing with empty graph"
  fi
else
  echo "init: OMNIGRAPH_LOAD_SEED=false, skipping seed load"
fi

echo "init: complete"
