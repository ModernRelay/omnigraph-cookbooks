#!/bin/sh
# First-deploy bootstrap for the Omnigraph Railway template.
#
# Runs as Railway's preDeployCommand. Pulls the schema from the URL
# provided via OMNIGRAPH_SCHEMA_URL, then runs `omnigraph init`. On
# subsequent deploys the snapshot succeeds and the script exits without
# touching the graph. No seed data is loaded — the deploy is schema-only;
# operators fill the graph from their own sources.

set -e

: "${OMNIGRAPH_TARGET_URI:?OMNIGRAPH_TARGET_URI must be set}"
: "${OMNIGRAPH_SCHEMA_URL:?OMNIGRAPH_SCHEMA_URL must be set (e.g. https://raw.githubusercontent.com/ModernRelay/omnigraph-cookbooks/main/industry-intel/schema.pg)}"

# Idempotency guard. A non-zero `snapshot` means either "not initialized
# yet" (first deploy) or a transient failure (e.g. S3/credential error). We
# capture the output instead of discarding it (no `>/dev/null 2>&1`) and log
# it before falling through, so a transient failure shows its real cause
# rather than resurfacing later as a confusing `init` error. `omnigraph init`
# is the data-safety backstop: without `--force` it refuses a URI that
# already holds schema artifacts, so a misfired guard fails the deploy
# loudly rather than overwriting an existing graph.
if snapshot_out=$(omnigraph snapshot "$OMNIGRAPH_TARGET_URI" --json 2>&1); then
  echo "init: graph at $OMNIGRAPH_TARGET_URI already initialized; skipping"
  exit 0
fi
echo "init: snapshot did not report an initialized graph — proceeding to init"
echo "init: snapshot output: $(printf '%s' "$snapshot_out" | tr '\n' ' ' | cut -c1-300)"

SCHEMA_PATH=/tmp/omnigraph-schema.pg
echo "init: downloading schema from $OMNIGRAPH_SCHEMA_URL"
curl -fsSL "$OMNIGRAPH_SCHEMA_URL" -o "$SCHEMA_PATH"

echo "init: applying schema to $OMNIGRAPH_TARGET_URI"
omnigraph init --schema "$SCHEMA_PATH" "$OMNIGRAPH_TARGET_URI"

echo "init: complete"
