# Reference Commands

Commands you'll reach for but don't need best-practice rules around. Quick syntax reference.

## Inspect State

### `snapshot` — tables + row counts

```bash
omnigraph snapshot $REPO --branch main --json
```

Returns the manifest: all node/edge tables with row counts and versions. Use this to verify a load succeeded or to see what types exist.

### `export` — full JSONL dump

```bash
omnigraph export $REPO --branch main > graph.jsonl
```

Streams all nodes and edges as JSONL. The right tool for large-snapshot inspection. Don't try to page through the whole graph with read queries.

Filter by type:

```bash
omnigraph export $REPO --branch main --type Signal > signals.jsonl
```

## Branches

```bash
omnigraph branch create --uri $REPO --from main <branch-name>
omnigraph branch list --uri $REPO
omnigraph branch merge --uri $REPO <branch-name> --into main
omnigraph branch delete --uri $REPO <branch-name>
```

All support `--json`.

## Commits (History)

```bash
omnigraph commit list $REPO --branch main
omnigraph commit show $REPO <commit-id>
```

Inspect graph history. Useful for "what changed between these two points" investigation.

## Schema

```bash
omnigraph schema plan --schema ./next.pg $REPO --json
omnigraph schema apply --schema ./next.pg $REPO
```

See `references/schema.md` for the full workflow.

## Query Lint

```bash
omnigraph query lint --schema ./schema.pg --query ./queries/foo.gq --json
# or against a live repo:
omnigraph query lint --query ./queries/foo.gq $REPO --json
```

See `references/queries.md`.

## Embed

```bash
omnigraph embed --seed ./embed-config.yaml                  # fill missing
omnigraph embed --seed ./embed-config.yaml --reembed_all    # regenerate all
omnigraph embed --seed ./embed-config.yaml --clean          # delete
omnigraph embed --seed ./embed-config.yaml --select "Type:field=value"
```

See `references/search.md`.

## Init

```bash
omnigraph init --schema ./schema.pg $REPO
```

Creates a new repo at `$REPO` with the given schema. Also scaffolds `omnigraph.yaml` in the current directory if one doesn't exist — review and edit the template before committing (default graph names are placeholders).

**Note:** `init` does not accept `--json`. Drop the flag if you see `unexpected argument --json`.

## Load vs Ingest

```bash
# load: operates on an existing branch (default main)
omnigraph load --data ./seed.jsonl --mode merge $REPO

# ingest: creates a branch from --from and loads onto it
omnigraph ingest --data ./delta.jsonl --branch feature-x --from main --mode merge $REPO
```

`--mode` values for both: `overwrite`, `merge`, `append`. See `references/data.md`.

## Read / Change

```bash
omnigraph read  --query queries/signals.gq --name get_signal --params '{"slug":"sig-foo"}'
omnigraph change --query queries/mutations.gq --name add_signal --params '{"slug":"sig-foo",...}'
```

With aliases:

```bash
omnigraph read  --alias signal sig-foo
omnigraph change --alias add-signal sig-foo "Name" "Brief" 2026-04-14T00:00:00Z 2026-04-14T00:00:00Z 2026-04-14T00:00:00Z
```

## Config Resolution Order

When the CLI decides which graph to target:

1. **Explicit `--uri` or positional URI** wins
2. **`--target <name>`** selects a named graph from `omnigraph.yaml`
3. **Config default (`cli.graph`)** wins last

For queries:

1. **Explicit `--query <file>`** wins
2. Otherwise the **alias's `query`** is used (if `--alias` set)
3. Relative query paths resolve through **`query.roots`** in config

For params:

1. **Explicit `--params '{...}'`** wins on key conflict
2. **Positional alias args** map to alias `args` list

## Output Formats

`--format <fmt>` on read/change:

- `table` (default) — human-readable
- `kv` — `key: value` per line; good for single rows
- `csv` — comma-separated
- `jsonl` — NDJSON, one per line, with metadata line first
- `json` — pretty JSON array

For admin commands (branch, commit, schema, policy): use `--json` for structured output, otherwise human text.

## Health Check

```bash
curl http://127.0.0.1:8080/healthz
```

Returns `200 OK` if the server is up.
