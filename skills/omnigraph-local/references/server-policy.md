# HTTP Server & Cedar Policy

How to run `omnigraph-server` and gate operations with Cedar policies.

## Starting the Server

Two forms — pass the URI directly, or read from config:

```bash
# Direct URI + bind
omnigraph-server s3://omnigraph-local/repos/spike-intel --bind 127.0.0.1:8080

# Config-driven (uses server.graph and server.bind from omnigraph.yaml)
omnigraph-server --config ./omnigraph.yaml
```

The `--config` form is cleaner — less duplication, and the server graph is the same one the CLI can target via `graphs.<name>`.

### `omnigraph.yaml` server block

```yaml
graphs:
  local_s3:
    uri: s3://omnigraph-local/repos/spike-intel

server:
  graph: local_s3          # which graph to serve
  bind: 127.0.0.1:8080     # where to listen
```

## HTTP Routes

| Route | Purpose |
|-------|---------|
| `GET /healthz` | liveness probe |
| `GET /snapshot` | table state + row counts |
| `GET /export` | JSONL stream of a branch |
| `POST /read` | read query execution |
| `POST /change` | mutation execution |
| `POST /schema/apply` | schema migration |
| `GET /branches` | branch list |
| `GET /runs` | transactional run history |
| `GET /commits` | commit history |

Query params for read routes: `?branch=main` or `?snapshot=<id>`.

## Auth

Set `OMNIGRAPH_SERVER_BEARER_TOKEN` on the server process:

```bash
OMNIGRAPH_SERVER_BEARER_TOKEN=s3cret \
  omnigraph-server --config ./omnigraph.yaml
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
omnigraph read --target remote --alias signal sig-foo
```

Leave auth off entirely for pure local dev.

## When to Use Server vs Direct S3

- **Direct S3** (`s3://...` URI): simpler for local dev, no process to manage, works with any CLI invocation
- **HTTP server**: required for remote clients, policy enforcement, and a stable target URL across tool sessions

## Cedar Policy

Omnigraph can gate sensitive actions with [Cedar](https://www.cedarpolicy.com/) policies.

### Gated actions

| Action | Protects |
|--------|----------|
| `read` | query execution |
| `change` | mutations |
| `export` | data export |
| `schema_apply` | schema migrations |
| `branch_create` | branch creation |
| `branch_merge` | merges (especially into protected branches) |
| `run_publish`, `run_abort` | transactional run control |

For any shared repo, gate at least `schema_apply` and `branch_merge`.

### Policy file reference

```yaml
# omnigraph.yaml
policy:
  file: ./policy.yaml
```

### Policy.yaml shape

```yaml
groups:
  admins: [act-alice, act-bob]
  team: [act-carol, act-dan]

protected_branches:
  - main

rules:
  - name: admins-can-apply-schema
    effect: permit
    actors: admins
    actions: [schema_apply]

  - name: team-can-merge-to-protected
    effect: permit
    actors: team
    actions: [branch_merge]
    target_branch_scope: protected

  - name: deny-unreviewed-schema-apply
    effect: deny
    actions: [schema_apply]
    branch_scope: any
    # unless overridden by explicit permit
```

Rule scopes:
- `branch_scope: any | protected | unprotected`
- `target_branch_scope: protected | unprotected` (for merges)

### Validate, test, explain

```bash
# Compile Cedar + check syntax
omnigraph policy validate --config ./omnigraph.yaml

# Run declarative test cases from policy.tests.yaml
omnigraph policy test --config ./omnigraph.yaml

# Debug a single decision
omnigraph policy explain \
  --actor act-alice \
  --action schema_apply \
  --branch main \
  --config ./omnigraph.yaml
```

### Test cases (`policy.tests.yaml`)

```yaml
cases:
  - name: alice-can-apply-schema
    actor: act-alice
    action: schema_apply
    branch: main
    expect: permit

  - name: random-user-cannot-merge-to-main
    actor: act-random
    action: branch_merge
    target_branch: main
    expect: deny
```

Run `policy test` after every policy edit. Tests are cheap.

## Server + Policy Together

When the server is running with a policy file:
1. All HTTP routes check the authenticated actor (from the bearer token) against Cedar rules
2. Unauthorized requests return `403 Forbidden`
3. The CLI doesn't bypass policy when it connects over HTTP — it's enforced at the server

Direct S3 access bypasses policy (there's no actor to authenticate). Use HTTP when policy matters.
