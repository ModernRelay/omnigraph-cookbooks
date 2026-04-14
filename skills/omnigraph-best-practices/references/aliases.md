# Aliases & Agent Automation

How to wire Omnigraph operations for agents and scripts.

## Every Agent Operation Should Be an Alias

Agents calling raw `omnigraph read --query ... --name ... --params ...` drift as queries evolve. Aliases decouple the **operation name** from the **query implementation**:

```yaml
# omnigraph.yaml
aliases:
  signal:
    command: read
    query: signals.gq
    name: get_signal
    args: [slug]
    format: kv
```

The agent calls:

```bash
omnigraph read --alias signal sig-kimi-k25
```

When the query changes, the alias stays stable. The agent keeps working.

## Alias Schema

```yaml
aliases:
  <alias-name>:
    command: read | change    # which subcommand to dispatch
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
omnigraph read --alias foo sig-bar "Some Name" 29
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
    command: read
    query: signals.gq
    name: get_signal
    args: [slug]
    format: kv

  pattern:
    command: read
    query: patterns.gq
    name: get_pattern
    args: [slug]
    format: kv

  # Lists (default format inherits from cli.output_format)
  signals:
    command: read
    query: signals.gq
    name: recent_signals

  # Traversals
  pattern-signals:
    command: read
    query: patterns.gq
    name: pattern_signals
    args: [slug]

  # Mutations (change command)
  add-signal:
    command: change
    query: mutations.gq
    name: add_signal
    args: [slug, name, brief, stagingTimestamp, createdAt, updatedAt]

  link-forms-pattern:
    command: change
    query: mutations.gq
    name: link_signal_forms_pattern
    args: [signal, pattern]
```

## Invocation Patterns

```bash
# Read by alias
omnigraph read --alias signal sig-kimi-k25

# Change by alias
omnigraph change --alias add-signal sig-new "Name" "Brief" \
  2026-04-14T00:00:00Z 2026-04-14T00:00:00Z 2026-04-14T00:00:00Z

# Override output format
omnigraph read --alias signals --format jsonl

# Override target graph
omnigraph read --alias signal --target local_server sig-kimi-k25

# Override branch
omnigraph read --alias signals --branch staging-2026-04-14

# With explicit --params (wins over positional args on key conflict)
omnigraph read --alias signal --params '{"slug":"sig-override"}'
```
