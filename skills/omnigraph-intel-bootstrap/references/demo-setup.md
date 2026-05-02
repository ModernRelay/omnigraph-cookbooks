# Demo Setup — AI Industry Intel

The quickest path to a populated SPIKE graph. Uses the existing `industry-intel` cookbook as-is.

## Prerequisites

### RustFS + binaries

RustFS must be running locally on `127.0.0.1:9000`. Verify with:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:9000/
```

If you get `000` (no connection), bootstrap RustFS. **Requires Docker** ([install](https://docs.docker.com/get-docker/)):

```bash
docker version >/dev/null 2>&1 || { echo "Install Docker first: https://docs.docker.com/get-docker/"; exit 1; }
curl -fsSL https://raw.githubusercontent.com/ModernRelay/omnigraph/main/scripts/local-rustfs-bootstrap.sh | bash
```

Bootstrap installs `omnigraph` and `omnigraph-server` under `<workdir>/.omnigraph-rustfs-demo/bin/` — **not on PATH by default**. Add it or invoke by absolute path.

### Existing server on :8080

Bootstrap auto-starts an `omnigraph-server` on `:8080` against its own demo repo. If you'll be running your own server (later in this flow), check first:

```bash
curl -s -o /dev/null -w "server:%{http_code}\n" http://127.0.0.1:8080/healthz
```

If `200`, either stop the bootstrap server or rebind yours via `omnigraph-server --bind 127.0.0.1:8090`.

## Get the cookbook content

The `industry-intel` cookbook (schema, queries, seed) lives in the [omnigraph-cookbooks](https://github.com/ModernRelay/omnigraph-cookbooks) repo. Ask the user where to clone it (default: current directory):

```bash
git clone https://github.com/ModernRelay/omnigraph-cookbooks.git
```

Then move into the cookbook folder:

```bash
cd omnigraph-cookbooks/industry-intel
[ -f .env.omni ] || cp .env.omni.example .env.omni
set -a && source ./.env.omni && set +a
```

`.env.omni` is gitignored (it's just credentials). The repo ships `.env.omni.example` with the 7 required AWS vars — copy it on first run.

All commands below run from `industry-intel/`. If the clone is somewhere else, substitute the absolute path.

### First-time bucket creation

If this is a fresh RustFS instance (no `omnigraph-local` bucket yet):

```bash
aws --endpoint-url http://127.0.0.1:9000 s3 mb s3://omnigraph-local
```

### Init + load

These are one-time setup ops that write directly to storage:

```bash
omnigraph init --schema ./schema.pg s3://omnigraph-local/repos/spike-intel
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/spike-intel
```

Expected output from load:

```
loaded s3://omnigraph-local/repos/spike-intel on branch main with overwrite: 111 nodes across 9 node types, 148 edges across 16 edge types
```

### Start the server

```bash
omnigraph-server --config ./omnigraph.yaml
```

Keep it running (separate terminal or background). All queries from here on go through it.

### Verify

```bash
omnigraph read --config ./omnigraph.yaml --alias patterns disruption
```

Should return 2 patterns: SaaSpocalypse, Sovereign AI.

Try a traversal:

```bash
omnigraph read --config ./omnigraph.yaml --alias pattern-signals pat-sovereign-ai
```

Should return 3 signals.

## What You Got

| Node | Count |
|------|-------|
| Pattern | 5 (Sovereign AI, SaaSpocalypse, Context Graphs, New Cyber Threats, Accelerated Research) |
| Signal | 15 (each with real dates and source URLs) |
| Element | 26 (products, frameworks, concepts across AI/ML) |
| Company | 17 |
| Expert | 7 |
| SourceEntity | 16 |
| InformationArtifact | 20 |
| Insight | 3 |
| KnowHow | 2 |

Plus 148 edges wiring the graph together.

## Next Steps

- **Explore queries** in `queries/*.gq`
- **Try aliases**: see `omnigraph.yaml` under `aliases:`
- **For day-to-day ops** (adding signals, evolving schema, branches, embeddings): switch to the `omnigraph-best-practices` skill

## Optional: Reset

To wipe and reload the demo from scratch:

```bash
omnigraph load --data ./seed.jsonl --mode overwrite s3://omnigraph-local/repos/spike-intel
```

`overwrite` truncates the branch before loading — safe for a demo repo, not for production.
