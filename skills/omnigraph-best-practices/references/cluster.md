# Cluster Mode — Declarative Deployments

The cluster control plane (omnigraph >= 0.7.0; edge channel until 0.7.0 tags)
manages a whole deployment — graphs, schemas, stored queries, Cedar policies —
as **declared files in one directory**, converged Terraform-style. It is
opt-in: everything in the other references (single-graph `omnigraph.yaml`
deployments, data-plane operations) remains fully supported.

## The model

```
company-brain/
├── cluster.yaml        # the deployment: graphs, schemas, queries, policies
├── schema.pg
├── queries/*.gq
├── *.policy.yaml
├── graphs/<id>.omni    # DERIVED — created by apply, never by hand (gitignore)
└── __cluster/          # ledger + catalog + approvals — local state (gitignore)
```

```yaml
# cluster.yaml
version: 1
state: { backend: cluster, lock: true }
graphs:
  knowledge:
    schema: ./schema.pg
    queries:
      find_person: { file: ./queries/people.gq }   # name must match `query find_person` in the file
policies:
  base: { file: ./base.policy.yaml, applies_to: [knowledge] }  # or [cluster] for server-level
```

A `.gq` file may hold many queries; declare each name against the same file.

## The loop (memorize this)

```bash
omnigraph cluster validate --config .              # parse + typecheck everything
omnigraph cluster import   --config .              # one-time: create the state ledger
omnigraph cluster plan     --config .              # preview — REQUIRED reading before apply
omnigraph cluster apply    --config . --as <you>   # converge (idempotent)
omnigraph-server --cluster . --bind 127.0.0.1:8080 --unauthenticated  # serve (local dev)
```

- **`apply` creates graphs** at `./graphs/<id>.omni` — there is no separate
  `omnigraph init` in cluster mode.
- **Schema changes**: edit the `.pg`, `plan` shows the engine's real migration
  steps (`add_property`, `drop_property [soft]`, `unsupported: …`), `apply`
  migrates the live graph. **Soft drops only** — data-loss migrations are not
  reachable from cluster apply (prior versions retain dropped columns).
- **Applied = serving on the next server restart.** No hot reload.
- **`--as <actor>` attributes every run** (sidecars, audit, engine commits).
  Defaults from your per-operator `omnigraph.yaml`'s `cli.actor`; required for
  `approve`.
- **Destructive changes are gated**: removing a graph from `cluster.yaml`
  blocks with `approval_required` until
  `omnigraph cluster approve graph.<id> --config . --as <you>` records a
  digest-bound approval. Any config/state drift after approving invalidates it.
- **Drift**: `cluster refresh` re-observes live graphs and marks out-of-band
  changes `drifted`; the next `apply` converges them back to the declaration.
- **Data is NOT cluster's job**: rows flow through `omnigraph load / ingest /
  mutate` against the derived roots, with branches as usual.

## The two-file contract (do not blur this)

| File | Owns | Read by |
|---|---|---|
| `cluster.yaml` | the deployment: graph set, schemas, stored queries, policy bindings | `cluster` commands; the `--cluster` server |
| `omnigraph.yaml` | per-operator ergonomics: aliases, CLI defaults, `cli.actor`, credentials | data-plane CLI commands |

Cluster commands read `omnigraph.yaml` for **exactly one thing**: the
`cli.actor` default when `--as` is omitted. A `--cluster` server reads it for
**nothing** — boot from cluster state XOR `omnigraph.yaml`, never a merge.
Point `graphs.<name>.uri` at a derived root in your `omnigraph.yaml` so
aliases and `--target` work against cluster-managed graphs — that is
ergonomics, not coupling.

## Serving

`omnigraph-server --cluster <dir>` is exclusive (cannot combine with a URI,
`--target`, or `--config`), always multi-graph (`/graphs/{id}/...`), and
fail-fast: missing/pending/tampered state refuses boot with a remedy. Every
declared query is exposed (`GET /graphs/<id>/queries`, `POST
/graphs/<id>/queries/<name>`); Cedar bundles attach via `applies_to`
(`cluster` → server-level gate incl. `graph_list`; `graph.<id>` → that
graph's gate incl. `invoke_query`). Bearer tokens and bind stay process-level
(env/flags). In containers: `OMNIGRAPH_CLUSTER=<mounted dir>` (the image
ships the CLI for in-container `cluster apply`).

## Recovery cheat-sheet

| Symptom | Fix |
|---|---|
| Apply crashed mid-run | run `cluster apply` again — sidecars + sweep reconcile |
| Held lock | `cluster status` (shows lock id) → `cluster force-unlock <LOCK_ID> --config .` |
| Lost/corrupt `state.json` | `cluster import` rebuilds from config + live graphs, then `apply` |
| Server refuses to boot | the error names its remedy (usually `cluster refresh` + `apply`, restart) |
| `approval_stale` warning | re-run `cluster approve` — the plan changed since you approved |

Full reference: the omnigraph repo's `docs/user/cluster.md` (operator guide)
and `docs/user/cluster-config.md` (every key, flag, and diagnostic).
