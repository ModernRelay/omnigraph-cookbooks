# Aliases & Agent Automation

How to wire Omnigraph operations for agents and scripts.

## Every Agent Operation Should Be an Alias

Agents calling raw `omnigraph query --query ... --name ... --params ...` drift as queries evolve. Aliases decouple the **operation name** from the **query implementation**:

```yaml
# omnigraph.yaml
aliases:
  signal:
    command: query
    query: signals.gq
    name: get_signal
    args: [slug]
    format: kv
```

The agent calls:

```bash
omnigraph query --alias signal sig-kimi-k25
```

When the query changes, the alias stays stable. The agent keeps working.

> **Aliases ≠ stored queries.** A CLI `aliases:` entry is **client-side** — it tells the local `omnigraph` CLI which `.gq` file + query name + params to send; the server never sees it. The v0.6.1 **`queries:`** registry is **server-side** — curated queries the server loads, type-checks at startup, and exposes over `GET /queries` / `POST /queries/{name}` (gated by `invoke_query`). Use aliases for your own CLI/agent ergonomics; use the `queries:` registry to expose a vetted query surface to remote callers or MCP. See [`stored-queries.md`](stored-queries.md).

## Alias Schema

```yaml
aliases:
  <alias-name>:
    command: query | mutate   # which subcommand to dispatch (`read`/`change` still accepted, deprecated)
    query: <filename.gq>      # resolved via query.roots
    name: <query_name>        # the query inside the file
    args: [<name1>, <name2>]  # positional CLI args → named params
    graph: <graph-name>       # optional: override the default graph
    branch: main              # optional: override the default branch
    format: table|kv|csv|jsonl|json   # optional: output format
```

### `args` bind to query parameters

If `args: [slug, name, age]`, then:

```bash
omnigraph query --alias foo sig-bar "Some Name" 29
```

...maps to `{"slug":"sig-bar","name":"Some Name","age":29}`.

### Args are JSON-first

Each arg is parsed as JSON first, then falls back to string:
- `29` → integer
- `"29"` → string
- `true` → boolean
- `Alice` → string (JSON parse fails, falls back)
- `{"x":1}` → object

Explicit `--params '{...}'` wins on key conflict.

## Default to Structured Output

For scripts and agents, set `jsonl` or `json`. `table` is for humans.

```yaml
cli:
  output_format: jsonl
```

Or per-alias:

```yaml
aliases:
  signal:
    ...
    format: jsonl
```

Or per-call: `--format jsonl`.

### When to use which

- **`jsonl`** — one JSON object per line, first line is metadata; streams; ideal for agents
- **`json`** — pretty-printed JSON array; smaller results; human-readable
- **`kv`** — `key: value` per line; good for single-row lookups (`get_signal slug=foo`)
- **`csv`** — for spreadsheets or line-count-heavy analysis
- **`table`** — default human view; don't use in automation

## Alias Naming Convention

Short, hyphenated, matches the conceptual operation:

- `signal`, `pattern`, `element` — single lookup (typical pair with `format: kv`)
- `signals`, `patterns`, `elements` — list
- `signal-patterns`, `pattern-signals` — traversals
- `add-signal`, `link-forms-pattern` — mutations

## Secrets Don't Belong in Aliases

Credentials go in `.env.omni` referenced via `auth.env_file: .env.omni`. Aliases should only contain query names and parameter bindings — never tokens, passwords, or API keys.

## Example Alias Set

```yaml
aliases:
  # Lookups (kv format for single-row readability)
  signal:
    command: query
    query: signals.gq
    name: get_signal
    args: [slug]
    format: kv

  pattern:
    command: query
    query: patterns.gq
    name: get_pattern
    args: [slug]
    format: kv

  # Lists (default format inherits from cli.output_format)
  signals:
    command: query
    query: signals.gq
    name: recent_signals

  # Traversals
  pattern-signals:
    command: query
    query: patterns.gq
    name: pattern_signals
    args: [slug]

  # Mutations (mutate command)
  add-signal:
    command: mutate
    query: mutations.gq
    name: add_signal
    args: [slug, name, brief, stagingTimestamp, createdAt, updatedAt]

  link-forms-pattern:
    command: mutate
    query: mutations.gq
    name: link_signal_forms_pattern
    args: [signal, pattern]
```

## Invocation Patterns

```bash
# Read by alias
omnigraph query --alias signal sig-kimi-k25

# Change by alias
omnigraph mutate --alias add-signal sig-new "Name" "Brief" \
  2026-04-14T00:00:00Z 2026-04-14T00:00:00Z 2026-04-14T00:00:00Z

# Override output format
omnigraph query --alias signals --format jsonl

# Override target graph
omnigraph query --alias signal --target local_server sig-kimi-k25

# Override branch
omnigraph query --alias signals --branch staging-2026-04-14

# With explicit --params (wins over positional args on key conflict)
omnigraph query --alias signal --params '{"slug":"sig-override"}'
```

> **Cluster note:** aliases are an `omnigraph.yaml` (per-operator) feature
> and keep working in cluster deployments — point `graphs.<name>.uri` at the
> derived root (`<dir>/graphs/<id>.omni`). The deployment's stored queries
> are declared in `cluster.yaml`; aliases remain your CLI sugar over the same
> `.gq` files.
