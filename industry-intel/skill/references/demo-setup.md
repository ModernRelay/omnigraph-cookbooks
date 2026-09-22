# Demo Setup — AI Industry Intel

The quickest path to a populated SPIKE graph. Uses the existing `industry-intel` cookbook as-is.

## Prerequisites

Install the OmniGraph CLI and server v0.11.0. The default filesystem-backed
demo needs no object store, credentials, or Docker. RustFS is optional and is
covered by the S3 alternative in the cookbook README.

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
```

All commands below run from `industry-intel/`. If the clone is somewhere else, substitute the absolute path.

Merge `omnigraph-config.example.yaml`'s `servers`, `defaults`, and `aliases`
into `~/.omnigraph/config.yaml`. Bearer tokens do not belong in that file;
`omnigraph login local` stores one separately later.

### Converge the cluster + load

The cookbook ships a `cluster.yaml` declaring the graph (`spike`), the
schema, and all 73 stored queries. One-time setup:

```bash
omnigraph cluster import --config .                # create the state ledger
omnigraph cluster plan   --config .                # preview (optional but wise)
omnigraph cluster apply  --config . --as <you>     # creates graphs/spike.omni, applies schema, publishes queries
omnigraph load --data seed.jsonl --mode overwrite graphs/spike.omni
```

Apply is idempotent — re-running it on a converged cluster is a no-op. No
RustFS, bucket, or credentials are involved on this path.

Expected output from load:

```
loaded graphs/spike.omni on branch main with overwrite: 263 entities across 9 node types and 17 edge types
```

### Start the server

```bash
export OMNIGRAPH_SERVER_BEARER_TOKENS_JSON='{"act-admin":"local-admin-token","act-writer":"local-writer-token","act-reader":"local-reader-token"}'
omnigraph-server --cluster . --bind 127.0.0.1:8080
```

`--cluster` serves the applied revision (the exclusive boot source). The
cookbook policy requires an authenticated actor, so keep the server running
and log the CLI into its named `local` server from a second terminal:

```bash
printf '%s' 'local-reader-token' | omnigraph login local
```

Every declared query is also a direct HTTP endpoint:
`POST /graphs/spike/queries/<name>`.

### Verify

```bash
omnigraph alias patterns disruption
```

Should return 2 patterns: SaaSpocalypse, Sovereign AI.

Try a traversal:

```bash
omnigraph alias pattern-signals pat-sovereign-ai
```

Should return 3 signals.

## What You Got

| Node | Count |
|------|-------|
| Pattern | 5 (Sovereign AI, SaaSpocalypse, Context Graphs, New Cyber Threats, Accelerated Research) |
| Signal | 15 (each with real dates and source URLs) |
| Element | 24 (products, frameworks, concepts across AI/ML) |
| Company | 16 |
| Expert | 7 |
| SourceEntity | 16 |
| InformationArtifact | 20 |
| Insight | 4 |
| KnowHow | 2 |

That is 109 nodes plus 154 edges, or 263 entities total.

## Next Steps

- **Explore queries** in `queries/*.gq`
- **Try aliases**: merge the cookbook's `omnigraph-config.example.yaml` `aliases:` into `~/.omnigraph/config.yaml`
- **For day-to-day ops** (adding signals, evolving schema, branches, embeddings): switch to the `omnigraph` skill (`npx skills add ModernRelay/omnigraph@omnigraph`)

## Optional: Reset

To wipe and reload the demo data from scratch:

```bash
omnigraph load --data seed.jsonl --mode overwrite graphs/spike.omni
```

`overwrite` truncates the branch before loading — safe for a demo repo, not for production.
