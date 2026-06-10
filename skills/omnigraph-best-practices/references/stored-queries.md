# Stored-Query Registries (v0.6.1)

A **stored query** is a `.gq` query that the *server* loads, type-checks at startup, and exposes by name — without ever accepting ad-hoc query source from the client. It's how you publish a vetted, typed query surface to remote callers and MCP tools.

This is a server-side feature introduced in **v0.6.1**. It is distinct from CLI `aliases:` (see [`aliases.md`](aliases.md)): an alias is local client ergonomics; a stored query is a server-published, policy-gated endpoint.

## The `queries:` config block

Each entry's **key must equal the `query <name>` symbol inside the `.gq` file**.

### Per-graph (named graphs)

A graph served by name (`server.graph` / `--target`) carries its registry under `graphs.<name>.queries`:

```yaml
graphs:
  local_s3:
    uri: s3://omnigraph-local/repos/spike-intel
    queries:
      get_signal:                  # MUST match `query get_signal(...)` in the .gq
        file: queries/signals.gq   # relative to this config's directory
        mcp:
          expose: true             # default true → listed in GET /queries; false → callable but hidden
          tool_name: signal_lookup # optional MCP tool-name override (defaults to the query name; must be unique)
      recent_signals:
        file: queries/signals.gq

server:
  graph: local_s3
```

### Top-level (anonymous bare-URI graph only)

A top-level `queries:` block applies **only** to an anonymous bare-URI single-graph server — the same rule as top-level `policy:`. Using a top-level `queries:` with a *named* graph makes the server **refuse to boot** (v0.6.1 config-follows-identity). See [`server-policy.md`](server-policy.md).

```yaml
queries:
  get_signal: { file: queries/signals.gq }   # mcp.expose defaults to true
```

## CLI

```bash
omnigraph queries validate     # type-check every stored query against the live schema (offline; opens the graph; exits non-zero on drift)
omnigraph queries list         # print the selected registry: query names, MCP exposure, typed params
```

- `validate` catches schema drift **without restarting the server** — run it after a `schema apply` or before deploying a config change. The server also runs this check at startup and **refuses to boot** on drift or on a duplicate MCP tool name.
- Select the registry with `--target <graph>` or `cli.graph`. With no graph selected, `list` shows only the top-level `queries:` block.
- `queries` is distinct from `lint` — `lint` validates a single `.gq` file you point it at; `queries validate` validates the registry the server will actually serve.

## HTTP surface

| Route | Gate | Purpose |
|-------|------|---------|
| `GET /queries` | `read` | Typed tool catalog of the `mcp.expose` queries. Graph-wide (branch-independent; `read` authorized against `main`). Works in default-deny mode. |
| `POST /queries/{name}` | `invoke_query` (+ `change` for a stored mutation) | Invoke a named query. Body carries params only — **never** `.gq` source. A stored mutation cannot target a `snapshot` (`400`); a param type error is a structured `400` naming the param. |

`?branch=` / `?snapshot=` query params apply to `POST /queries/{name}` reads; branch/snapshot access stays enforced by the inner `read`/`change` gate (`invoke_query` itself is graph-scoped, not branch-scoped).

## Policy gating (`invoke_query`)

- **`invoke_query`** is a per-graph Cedar action gating the whole stored-query invocation surface. Grant it like any other action (see [`server-policy.md`](server-policy.md)).
- **Stored mutations are double-gated:** the caller needs `invoke_query` to reach the query **and** `change` for the write. An actor with `invoke_query` but not `change` gets `403` on a stored mutation.
- **Deny == unknown:** for a caller *lacking* `invoke_query`, a denial and an unknown query name return the **same 404** (identical body) — the catalog can't be probed. A caller who *holds* `invoke_query` may still get a `403` from the inner gate for a query it can't `read`/`change`, so existence is visible to grant-holders by design.
- **Default-deny mode** (bearer tokens, no `policy.file`) permits only `read`, so *every* `/queries/{name}` call returns `404` until an `invoke_query` rule is configured.

## MCP exposure

- `mcp.expose` defaults to **`true`** — declaring a query in `queries:` lists it in `GET /queries`.
- Set `mcp: { expose: false }` for service-only queries that should stay HTTP-callable but hidden from the catalog.
- `tool_name` overrides the catalog/MCP tool name (defaults to the query name); it must be unique across exposed queries, or the server refuses to boot.

## Note on per-query authorization

The catalog is **not** Cedar-filtered per query yet: a caller with `read` but not `invoke_query` can *list* a query it cannot *invoke* (invocation would 404). Per-query authorization is future work; for now the catalog is a discovery surface and `invoke_query` is the invocation gate.

## Stored Queries in Cluster Mode

In a cluster deployment, queries are declared in `cluster.yaml` instead:

```yaml
graphs:
  knowledge:
    queries: queries/    # discover every `query <name>` in queries/*.gq
```

A file list (`[a.gq, b.gq]`) and a fine-grained `name: { file: ... }` map are
also accepted; with discovery the `.gq` files are the declaration and
duplicate names across files fail validation. `cluster apply`
publishes them to a content-addressed catalog; the `--cluster` server
type-checks and serves every applied query (`GET /graphs/<id>/queries`,
`POST /graphs/<id>/queries/<name>`). There is no `mcp:`/expose flag in
cluster mode yet — every applied query is listed (per-query exposure policy
is a planned phase). Cedar's `invoke_query` gating works identically.
