# Demo Setup — AI Industry Intel

The quickest path to a populated SPIKE graph. Uses the existing `industry-intel` starter as-is.

## Prerequisites

1. RustFS is running locally. If not, see the `omnigraph-best-practices` skill for the bootstrap command.
2. You're inside the `omnigraph-starters` repo.

## Steps

```bash
cd industry-intel
set -a && source ./.env.omni && set +a
```

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
