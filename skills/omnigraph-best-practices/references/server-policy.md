# HTTP Server & Cedar Policy

How to run `omnigraph-server` and gate operations with Cedar policies.

## Starting the Server

The server is the canonical runtime entry point. Start it once per repo and keep it running — all CLI queries, mutations, and admin ops go through it.

```bash
omnigraph-server --config omnigraph.yaml
```

Reads `server.graph` and `server.bind` from the config. Run in a separate terminal or background process.

### `omnigraph.yaml` server block

```yaml
graphs:
  local_s3:
    uri: s3://omnigraph-local/repos/spike-intel

server:
  graph: local_s3          # which graph to serve (single-graph mode)
  bind: 127.0.0.1:8080     # where to listen
```

## HTTP Routes

| Route | Purpose |
|-------|---------|
| `GET /healthz` | liveness probe |
| `GET /snapshot` | table state + row counts |
| `GET /export` | JSONL stream of a branch |
| `POST /query` | read query execution |
| `POST /mutate` | mutation execution |
| `POST /read` / `POST /change` | **deprecated** aliases for `/query` / `/mutate` — still served, but carry `Deprecation: true` and `Link: </query>; rel="successor-version"` response headers. Prefer the canonical names. |
| `GET /queries` | stored-query catalog (v0.6.1) — lists `mcp.expose` queries as a typed tool catalog; **read**-gated |
| `POST /queries/{name}` | invoke a named stored query (v0.6.1); **`invoke_query`**-gated (+ `change` for a stored mutation); never accepts ad-hoc `.gq` from the client; deny == 404 |
| `POST /schema/apply` | schema migration |
| `GET /branches` | branch list |
| `GET /commits` | commit history |

Query params for read routes: `?branch=main` or `?snapshot=<id>`.

> **No `/runs` endpoint.** The transactional Run state machine and its `/runs` routes were removed in v0.4.0. Writes now publish directly and commit atomically via the `__manifest` table; use `GET /commits` for write/audit history. A request to `/runs` returns 404.

## Auth

Set `OMNIGRAPH_SERVER_BEARER_TOKEN` on the server process:

```bash
OMNIGRAPH_SERVER_BEARER_TOKEN=s3cret \
  omnigraph-server --config omnigraph.yaml
```

On the client side, declare the env var that holds the matching token in `graphs.<name>`:

```yaml
graphs:
  remote:
    uri: http://server.example.com:8080
    bearer_token_env: OMNIGRAPH_BEARER_TOKEN
```

Then export the token before running the CLI:

```bash
export OMNIGRAPH_BEARER_TOKEN=s3cret
omnigraph query --target remote --alias signal sig-foo
```

### Running without auth requires an explicit opt-in

You can no longer just "leave auth off." Since v0.6.0 the server **refuses to start** when it has neither bearer tokens nor a policy file, unless you explicitly opt in:

```bash
omnigraph-server --config omnigraph.yaml --unauthenticated
# or: OMNIGRAPH_UNAUTHENTICATED=1 omnigraph-server --config omnigraph.yaml
```

This is a guardrail against accidentally shipping an open server. For pure local dev, pass `--unauthenticated` deliberately.

## Setup Operations Bypass the Server

`init` and `load` write the repo on storage directly — they don't go through the server. Pass the repo URI:

```bash
omnigraph init --schema schema.pg s3://omnigraph-local/repos/<name>
omnigraph load --data seed.jsonl --mode overwrite s3://omnigraph-local/repos/<name>
```

Everything else — `query`, `mutate`, `snapshot`, `schema plan/apply`, `branch`, `commit` — goes through the running server.

## Cedar Policy

Omnigraph can gate sensitive actions with [Cedar](https://www.cedarpolicy.com/) policies.

### Default-deny posture

Policy is enforced engine-wide (every authoring path calls the same gate), and the default is **closed**, not open:

| Server state | Bearer tokens | Policy file | Behavior |
|---|---|---|---|
| **Open** | no | no | Every request permitted — but the server refuses to start without `--unauthenticated` / `OMNIGRAPH_UNAUTHENTICATED=1`. |
| **DefaultDeny** | yes | no | Every authenticated request for an action other than `read` is rejected (HTTP 403). "Tokens but forgot the policy file" no longer ships the illusion of protection. |
| **PolicyEnabled** | yes | yes | Requests are evaluated against your Cedar rules. |

So configuring a policy file is what *enables* writes — there is no "permit everything by default" mode once tokens are set.

### Gated actions

Per-graph actions (evaluated against the graph being addressed):

| Action | Protects |
|--------|----------|
| `read` | query execution |
| `export` | data export |
| `change` | mutations |
| `invoke_query` | stored-query invocation via `POST /queries/{name}` (v0.6.1; graph-scoped, not branch-scoped). A stored **mutation** is double-gated — it also passes `change`. For a caller without the grant, a denial and an unknown query name both return the same **404** so the catalog can't be probed. |
| `schema_apply` | schema migrations |
| `branch_create` | branch creation |
| `branch_delete` | branch deletion |
| `branch_merge` | merges (especially into protected branches) |

`admin` exists but is reserved (no call site yet — don't write rules for it). In multi-graph deployments there is also a server-scoped `graph_list` action gating `GET /graphs`; it lives in a separate `server.policy.file`.

> The old `run_publish` / `run_abort` actions were **removed in v0.4.0**. A `policy.yaml` that still references them fails validation — delete those rules; the `change` action covers the equivalent gating.

For any shared repo, gate at least `schema_apply` and `branch_merge`.

### Policy file reference

```yaml
# omnigraph.yaml
policy:
  file: policy.yaml
```

> **Config-follows-identity (v0.6.1, breaking).** A top-level `policy:` (and `queries:`) block applies **only** to an anonymous bare-URI single-graph server. A graph served **by name** — `server.graph: <name>` or `--target <name>` — must nest its policy under that graph:
>
> ```yaml
> graphs:
>   local_s3:
>     uri: s3://omnigraph-local/repos/spike-intel
>     policy:
>       file: policy.yaml          # per-graph; required when the graph is named
> server:
>   graph: local_s3
> ```
>
> Leaving `policy:` (or `queries:`) at the top level while selecting a named graph now makes the server **refuse to boot** with migration guidance (it used to be silently accepted in v0.6.0). The multi-graph layout below already nests correctly.

### `policy.yaml` shape

The policy model is **allow-only**: every rule is a `permit`. You grant capabilities to groups; anything ungranted is denied by default. There is **no `deny` / `effect` key** — to forbid something, simply don't grant it.

```yaml
version: 1                          # required; must be 1

groups:
  admins: [act-alice, act-bob]
  team:   [act-carol, act-dan]

protected_branches:
  - main

rules:
  - id: admins-can-apply-schema     # rules use `id`, not `name`
    allow:                          # required `allow:` block
      actors: { group: admins }     # references a group by name
      actions: [schema_apply]
      target_branch_scope: protected

  - id: team-can-merge-to-protected
    allow:
      actors: { group: team }
      actions: [branch_merge]
      target_branch_scope: protected

  - id: team-can-read-write-unprotected
    allow:
      actors: { group: team }
      actions: [read, change]
      branch_scope: unprotected
```

To "block unreviewed schema applies," you don't write a deny rule — you just don't grant `schema_apply` to that group. Default-deny does the rest.

Scope rules (a rule's `allow` block may use **at most one**):

- `branch_scope: any | protected | unprotected` — for `read`, `export`, `change` (matches the source branch).
- `target_branch_scope: any | protected | unprotected` — for `schema_apply`, `branch_create`, `branch_delete`, `branch_merge` (matches the destination branch).

### Validate, test, explain

```bash
# Compile Cedar + check syntax
omnigraph policy validate --config omnigraph.yaml

# Run declarative test cases from policy.tests.yaml
omnigraph policy test --config omnigraph.yaml

# Debug a single decision
omnigraph policy explain \
  --actor act-alice \
  --action schema_apply \
  --target-branch main \
  --config omnigraph.yaml
```

### Test cases (`policy.tests.yaml`)

```yaml
version: 1                          # required; must be 1
cases:
  - id: alice-can-apply-schema      # cases use `id`, not `name`
    actor: act-alice
    action: schema_apply
    target_branch: main             # schema_apply is target-branch scoped
    expect: allow                   # `allow` / `deny` (not `permit`)

  - id: random-user-cannot-merge-to-main
    actor: act-random
    action: branch_merge
    target_branch: main
    expect: deny
```

Run `policy test` after every policy edit. Tests are cheap.

## Multi-graph mode (v0.6.0+)

One `omnigraph-server` process can serve up to 10 graphs at once. Mode is inferred from config: a non-empty `graphs:` map **with no single-mode selector** (`server.graph`, a positional `<URI>`, or `--target`) starts the server in multi mode.

```yaml
server:
  bind: 0.0.0.0:8080
  policy:
    file: server-policy.yaml          # server-level Cedar (graph_list)

graphs:
  alpha:
    uri: s3://tenant-bucket/alpha
    policy:
      file: policies/alpha.yaml       # per-graph Cedar
  beta:
    uri: s3://tenant-bucket/beta
    # no per-graph policy → engine-layer enforcement is a no-op for beta
```

**Routes are namespaced per graph.** Every per-graph route moves under `/graphs/{graph_id}/...` (`/graphs/alpha/query`, `/graphs/alpha/branches`, …). The bare flat routes (`/query`, `/snapshot`, …) return **404** in multi mode; conversely the cluster routes return **405** in single mode. SDK clients generated against a single-mode spec must regenerate.

**`GET /graphs`** lists the registered graphs (sorted by `graph_id`). It's gated by the server-scoped `graph_list` action and requires `server.policy.file` to be exposed — even under `--unauthenticated`, server topology stays closed until you explicitly authorize it. `omnigraph graphs list` mirrors it (remote servers only; rejects local URIs).

**Policy attaches at two levels:**
- `graphs.<id>.policy.file` — per-graph rules (`read`, `change`, `branch_*`, `schema_apply`). Each graph flows through its own policy.
- `server.policy.file` — server-level rules (`graph_list`).
- Top-level `policy.file` is **rejected** in multi mode (ambiguous across graphs); it stays valid for single-graph / CLI-local use. The loaders reject a `graph_list` rule in a per-graph file (or a `read` rule in the server file) at startup.

Runtime add/remove of graphs is **not** in v0.6.0 — operators edit `omnigraph.yaml` and restart.

## Server + Policy Together

When the server is running with a policy file:
1. Every request resolves the actor from the bearer token (the client cannot set actor identity) and checks it against Cedar rules.
2. Unauthorized requests return `403 Forbidden`.
3. The CLI doesn't bypass policy when it connects over HTTP — it's enforced at the server. Enforcement is also engine-wide, so CLI direct-engine writes and embedded SDK consumers hit the same gate.

Setup ops (`init`, `load`) write storage directly. With a policy configured they still flow through the engine-layer enforce gate for the actor you pass via `--as` (or `cli.actor` in `omnigraph.yaml`); gate the raw storage layer too (S3 bucket ACLs, object locks) if the bucket is shared.

## Cluster-Booted Servers

`omnigraph-server --cluster <dir>` serves a cluster directory's **applied
revision** — an exclusive boot source (cannot combine with a URI, `--target`,
or `--config`; `omnigraph.yaml` is never read). Always multi-graph routing
(`/graphs/{id}/...`). Policies are declared in `cluster.yaml` with the same
Cedar YAML format and attach via `applies_to`: `[cluster]` becomes the
server-level engine (gates `graph_list` / `GET /graphs`), `[<graph-id>]`
becomes that graph's engine (gates `invoke_query`, `read`, `change`, …).
Bearer tokens stay process-level (same env vars as below). Applied changes
serve on the next restart; boot is fail-fast with named remedies. See
`references/cluster.md`.
