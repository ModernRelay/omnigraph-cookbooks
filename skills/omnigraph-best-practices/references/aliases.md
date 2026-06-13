# Aliases & Agent Automation

## Contents
- Two kinds of alias (operator vs legacy `omnigraph.yaml`)
- Alias schema
- Default to structured output
- Alias naming convention
- Secrets don't belong in aliases
- Example alias set
- Invocation patterns

How to wire Omnigraph operations for agents and scripts.

## Two kinds of alias

An alias decouples a stable **operation name** from its implementation, so an agent calling `omnigraph query --alias signal …` keeps working as the query evolves. There are two forms in 0.7.0:

- **Operator aliases** (modern, `~/.omnigraph/config.yaml`) — personal *bindings* to a **stored query on a named server**. They carry no query content; the stored query in the cluster catalog is the team's contract.

  ```yaml
  # ~/.omnigraph/config.yaml
  aliases:
    triage:
      server: intel-dev      # an entry under servers:
      graph: spike           # optional (multi-graph servers)
      query: weekly_triage   # the STORED query's name — never a file
      args: [since]          # positional args → params, in order
      params: { limit: 20 }  # fixed defaults; positionals/--params win
      format: table
  ```

  ```bash
  omnigraph query --alias triage 2026-06-01
  # → POST <intel-dev>/graphs/spike/queries/weekly_triage with the keyed credential
  ```

- **Legacy `omnigraph.yaml` aliases** (deprecated config surface, RFC-008) — client-side bindings to a local `.gq` **file + query name**. Still how the cookbooks in this repo wire local/single-graph ops; they keep working through the deprecation window.

  ```yaml
  # omnigraph.yaml (legacy)
  aliases:
    signal:
      command: query
      query: signals.gq
      name: get_signal
      args: [slug]
      format: kv
  ```

  ```bash
  omnigraph query --alias signal sig-kimi-k25
  ```

When the query changes, the alias stays stable. The agent keeps working.

> **Aliases ≠ stored queries.** A CLI `aliases:` entry is **client-side** — it tells the local `omnigraph` CLI which `.gq` file + query name + params to send; the server never sees it. The v0.6.1 **`queries:`** registry is **server-side** — curated queries the server loads, type-checks at startup, and exposes over `GET /queries` / `POST /queries/{name}` (gated by `invoke_query`). Use aliases for your own CLI/agent ergonomics; use the `queries:` registry to expose a vetted query surface to remote callers or MCP. See [`stored-queries.md`](stored-queries.md).

## Alias Schema

```yaml
aliases:
  <alias-name>:
    command: query | mutate   # which subcommand to dispatch
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

Credentials never live in an alias or any config file. For remote servers, `omnigraph login <server>` stores the bearer token in `~/.omnigraph/credentials` (`0600`); for S3-backed storage, AWS creds go in `.env.omni`. Aliases should only contain query names and parameter bindings — never tokens, passwords, or API keys.

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

> **Cluster note:** operator aliases (in `~/.omnigraph/config.yaml`) bind to a
> cluster's stored queries by name — declare the query in `cluster.yaml`,
> `cluster apply`, then alias it with `{ server, graph, query }`. Legacy
> `omnigraph.yaml` aliases still work too: point `graphs.<name>.uri` at the
> derived root (`<dir>/graphs/<id>.omni`) and they stay CLI sugar over the
> same `.gq` files.
