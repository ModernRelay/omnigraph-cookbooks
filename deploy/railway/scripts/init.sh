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

# Three states to handle on every deploy:
#   1. No manifest        -> run `omnigraph init` then `load`
#   2. Manifest, has rows -> skip everything (no work needed)
#   3. Manifest, 0 rows   -> previous deploy init'd but the seed load
#                            didn't complete; skip `init` (which would
#                            error "already exists") and retry `load`
#
# State 3 is the recovery path. Without it, a transient load failure on
# the first deploy permanently strands the graph empty because snapshot
# still succeeds on subsequent deploys.

SNAPSHOT_JSON=""
if SNAPSHOT_JSON=$(omnigraph snapshot "$OMNIGRAPH_TARGET_URI" --json 2>/dev/null); then
  if printf '%s' "$SNAPSHOT_JSON" | grep -q '"row_count":[[:space:]]*[1-9]'; then
    echo "init: graph at $OMNIGRAPH_TARGET_URI already seeded; skipping"
    exit 0
  fi
  echo "init: manifest exists but graph has no rows; retrying seed load"
else
  echo "init: cookbook=$COOKBOOK schema=$SCHEMA_PATH target=$OMNIGRAPH_TARGET_URI"
  omnigraph init --schema "$SCHEMA_PATH" "$OMNIGRAPH_TARGET_URI"
fi

if [ "${OMNIGRAPH_LOAD_SEED:-false}" = "true" ]; then
  if [ -f "$SEED_PATH" ]; then
    echo "init: loading bundled demo seed from $SEED_PATH (mode=merge)"
    omnigraph load --data "$SEED_PATH" --mode merge "$OMNIGRAPH_TARGET_URI"
  else
    echo "init: no seed file at $SEED_PATH; continuing with empty graph"
  fi
else
  echo "init: OMNIGRAPH_LOAD_SEED not set; graph stays empty (only the cookbook schema is applied)"
fi

echo "init: complete"
