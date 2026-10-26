# Cookbook agent guide

Read this file and the cookbook's own `CLAUDE.md` before editing. `AGENTS.md`
links to the corresponding `CLAUDE.md`; edit the target once.

## Scope and sources

These are seven self-contained OmniGraph **0.14.0** bundles: schemas, seed data,
stored queries and applied policies. The only application code is the beads
cookbook's `ob` client in `beads/client/`, with its own tests, and the local
HTTPS gateway `scripts/local-tls-gateway.py`. The root
[README](README.md) owns setup, live updates and upgrades; individual cookbook
guides own their domain model and worked queries.

| Folder | Graph ID |
|---|---|
| `industry-intel` | `spike` |
| `pharma-intel` | `pharma` |
| `second-brain` | `brain` |
| `vc-os` | `vcos` |
| `dev-graph` | `dev` |
| `beads` | `beads` |
| `company-brain` | `company` |

The graph ID is the key in `cluster.yaml`, not the folder name. Configurations
omit `storage`, so local roots default to their directory. Explicit storage
belongs in the deployment configuration. Never commit graph or ledger state.

The vendored [OmniGraph skill](.claude/skills/omnigraph/SKILL.md) owns command and
language detail. Its immutable source is `scripts/omnigraph-skill.ref`, separate
from the released binary pin in `deploy/railway/Dockerfile`. Refresh with
`scripts/sync-skill.sh`; do not hand-edit vendored references.

## Changes and validation

- Run `python3 scripts/check-cookbooks.py` for all seven local journeys, or
  name cookbooks to run only those. It uses the released CLI/server, isolated
  operator homes, disposable roots and the local HTTPS gateway; it never
  touches a deployed graph. The Railway config preparer has its own tests
  under `deploy/railway/tests/`. For beads the checker also drives the `ob`
  client against the served graph; the client's local tests run with
  `python3 -m unittest discover -s beads/client/tests`.
- For a query edit, start with `omnigraph lint --schema schema.pg --query
  queries/<file>.gq`. This is an offline check. Comments in `.pg`/`.gq` use `//`.
- Keep `seed.md` and `seed.jsonl` consistent. Preserve the domain examples and
  required-field/edge constraints. A keyed node or unique edge must not repeat
  within one seed batch.
- New cookbooks ship schema, queries, seed, role policies, `cluster.yaml`,
  operator alias examples and short domain guidance. Add their local journey
  to the existing checker rather than creating a second harness.
- Update user instructions in the same change as a command or behavior. Prefer
  a link to an existing owner over copying another lifecycle walkthrough.

## Operational rules

Use [local setup](README.md#local-setup) for fresh roots. Fresh
`cluster apply --target . --config .` creates the ledger; no separate import is
needed. Direct apply retains exclusive admission after exit; a server releases
it on a clean shutdown. Only clear an exact lock after its owner and accepted
I/O have stopped. Never automatically force-unlock or edit the ledger; never
direct-apply while serving.

The 0.14 CLI selects destinations with `--target` and source folders with
`--config`; it sends tokens only over HTTPS, which is why local setup puts the
gateway in front of the server. Use `cluster plan/apply --target NAME --config
DIR` for live schema, query, policy and provider changes. Review deletions:
omitting a graph permanently purges its managed root and history. Schema changes
need only `main` live. Adoption, missing-root recreation and out-of-band schema
changes are refused.

All bundles include `act-admin`, `act-writer`, `act-reader` role policies.
company-brain adds `act-agent` (and named agents), which write only on
unprotected branches and cannot merge or delete branches. Static actor-to-token
JSON remains supported. `omnigraph access --target NAME --graph ID --branch B`
reports what a target's role may do. The bearer token selects the trusted actor;
a query's `$actor` is merely application provenance. `config_manage` authorizes
live deployment, and schema changes also need graph `schema_apply`. Do not
expand roles or change a running cluster without task authorization.

Query the live graph to answer questions; seed files are load inputs. Discover
stored names and parameters with `omnigraph queries list --target NAME --graph
ID`. Aliases take parameters by name with `--params` and are read-only.
Mutations use `omnigraph mutate`; ad-hoc source uses `-e` or `--query`, never
the name slot. Parameterize values and supply every required field.

Use `load --mode append` once on an empty graph. `merge` upserts; `overwrite`
replaces the types present in the batch. Review larger writes on a branch, keep
the exact receipt and verify the effect; `branch diff` and `branch merge
--dry-run` show a branch's change and its merge before publishing. A failed
write's `disposition.effects` says whether it changed anything; a timeout or
`unknown` has an unknown outcome, so inspect before replay. Deployment status
is observed by its original ID.

`@embed` does not generate vectors during load. Prepare JSONL with the offline
embedding pipeline; query-time providers must match its model and dimensions.
Full-text calls (`bm25`, `fuzzy`, `match_text`, ...) need the property declared
`@index`.
Never claim empty semantic results prove there are no matching facts without
checking vector coverage.

## Deployment

[Railway](deploy/railway/README.md) prepares a bundle without storage writes.
Bootstrap is explicit and, until the engine supports S3 bootstrap from the 0.14
CLI, uses the 0.13.0 CLI once; later configuration updates go through the
running server. Runtime/token changes require a stop-then-start replacement.
Keep one writer and use `/readyz` for readiness. A local smoke pass does not
qualify Railway/S3 failure or ownership-transfer behavior.
