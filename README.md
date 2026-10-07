# OmniGraph Cookbooks

Ready-to-run graph examples for **OmniGraph 0.13.0**. Each folder contains a
schema, real or clearly identified fictional seed data, stored queries, policies,
and a cluster declaration. Local examples use filesystem storage.

| Cookbook | Graph ID | Purpose |
|---|---|---|
| [Industry intel](industry-intel/) | `spike` | Industry evidence, patterns and insights |
| [Pharma intel](pharma-intel/) | `pharma` | Competitive intelligence and program decisions |
| [Second brain](second-brain/) | `brain` | Personal projects, relationships and notes |
| [VC operating system](vc-os/) | `vcos` | Deals, portfolio, relationships and investment beliefs |
| [Development graph](dev-graph/) | `dev` | Issues, decisions, specifications and releases |

## Local setup

Install the matching 0.13.0 CLI and server from the
[engine release](https://github.com/ModernRelay/omnigraph/releases/tag/v0.13.0).
Check `omnigraph version`; it should report 0.13.0 and storage format 14.
The examples below use `industry-intel` / `spike`; substitute the folder and
Graph ID from the table for another cookbook.

From a fresh cookbook directory, validate and preview before creating storage:

```bash
cd industry-intel
omnigraph cluster validate --config .
omnigraph cluster plan --config . --json
omnigraph cluster apply --config . --as act-admin --json
```

Fresh apply creates the ledger, graph and stored-query registry. It also prints
an **Admission lock** ID. There is no separate import step.

Before starting the server, the direct apply process must have exited and its
storage I/O must be settled, with no other writer using this root. For this
fresh local example, wait for successful apply completion, then clear that
exact lock ID:

```bash
omnigraph cluster force-unlock '<LOCK_ID_FROM_APPLY>' --config .
export OMNIGRAPH_SERVER_BEARER_TOKENS_JSON='{"act-admin":"local-admin-token","act-writer":"local-writer-token","act-reader":"local-reader-token"}'
omnigraph-server --cluster . --bind 127.0.0.1:8080
```

Leave the server running. These sample tokens are for this loopback demo;
choose your own secrets for a shared deployment. The included roles are:
admin manages configuration and data; writer reads/writes data and branches;
reader reads and invokes stored read queries. Policies are part of the bundle.

In a second terminal, from the same cookbook directory:

```bash
export OMNIGRAPH_BEARER_TOKEN=local-admin-token
export OMNIGRAPH_TOKEN_LOCAL=local-admin-token
# Proceed only when readiness returns HTTP 200.
curl -fsS http://127.0.0.1:8080/readyz
# Append once to the new empty graph. Keep the exact commit receipt.
omnigraph load --server http://127.0.0.1:8080 --graph spike \
  --data seed.jsonl --mode append --json
omnigraph queries list --server http://127.0.0.1:8080 --graph spike
omnigraph query recent_signals --server http://127.0.0.1:8080 --graph spike
```

Use a query from your cookbook if it has a different Graph ID. Seeds are inputs,
not live state: query the server to answer questions. Loading does not generate
embeddings; cookbooks with vector fields explain the optional offline pipeline.
Do not replay a load after a timeout without checking its outcome. `overwrite`
replaces every node/edge type present in the batch; use it only when that
replacement is intended.

For short commands, merge your cookbook's `omnigraph-config.example.yaml`
server/defaults/aliases into your operator config. To switch to reader access,
`unset OMNIGRAPH_TOKEN_LOCAL OMNIGRAPH_BEARER_TOKEN`, then run
`printf '%s' 'local-reader-token' | omnigraph login local`. `OMNIGRAPH_TOKEN_LOCAL` overrides a saved `local` login; use that override for
admin operations below. If an existing differently named server points at the
same URL, select it explicitly and use its matching `OMNIGRAPH_TOKEN_<NAME>`
variable. Aliases invoke read queries. Mutations use `omnigraph mutate` and a writer/admin credential.

## Live updates

Keep the server running. Edit the cookbook's schema, stored queries, policies,
provider settings or graph declarations, then validate, preview and apply:

```bash
export OMNIGRAPH_BEARER_TOKEN=local-admin-token
export OMNIGRAPH_TOKEN_LOCAL=local-admin-token
omnigraph cluster validate --config .
omnigraph cluster plan --config . --server http://127.0.0.1:8080 --json
omnigraph cluster apply --config . --server http://127.0.0.1:8080 --json
```

The server activates the change without restarting. Schema changes require
`main` to be the only live branch; merge and retire review branches first.
Removing a graph from `cluster.yaml` permanently deletes its managed storage
and history. Review the plan before applying.

Apply prints its deployment ID before submission. If waiting times out, continue
observing that ID instead of submitting a new deployment:

```bash
omnigraph cluster status --server http://127.0.0.1:8080 \
  --deployment-id '<DEPLOYMENT_ID>' --wait --timeout 1800 --json
```

Use `/readyz` for readiness. Raw graph/cluster HTTP calls must send and verify
`Omnigraph-Http-Api: 0.13`; the 0.13 CLI and SDK handle this automatically.
Process settings and static tokens still require a server restart. Stopping
**does not release the writer lock**: inspect `cluster status --config .`, stop
all prior writers, establish I/O settlement and clear only the exact retained
lock before starting another owner. See the engine's
[ownership-transfer rules](https://github.com/ModernRelay/omnigraph/blob/v0.13.0/docs/user/deployment.md#writer-topology).

## Upgrading

Upgrade the CLI, server and client integrations together. These examples create
format-14 graphs. A cluster created with 0.11 or earlier needs an export/rebuild
into a **new cluster root** using the matching old and new tools. Keep the old
root intact until the new graph is verified; reloading the seed does not preserve
your added data or history. A 0.12 graph already uses format 14, though an older
ledger may require explicit conversion with writers stopped. Follow the
[0.13 upgrade guide](https://github.com/ModernRelay/omnigraph/blob/v0.13.0/docs/user/operations/upgrade.md).

## SPIKE framework

Industry and pharma intelligence use Signal (observed fact), Pattern (recurring
theme), Insight (interpretation), KnowHow (practice) and Element (concrete
subject). This is a cookbook modeling convention, not an engine requirement.

## Skills and deployment

The [OmniGraph skill](.claude/skills/omnigraph/SKILL.md) is vendored for Claude
Code and linked from `.agents/skills/omnigraph` for Codex. Its immutable source
revision is in `scripts/omnigraph-skill.ref`; `scripts/sync-skill.sh` refreshes it
and records a content hash. This lets documentation corrections follow the
released engine without pretending the binary changed.

The [industry bootstrap skill](industry-intel/skill/) guides domain selection,
research and seed preparation. Install it with:

```bash
npx skills add https://github.com/ModernRelay/omnigraph-cookbooks/tree/main/industry-intel/skill
```

For a Railway deployment, use the [deployment guide](deploy/railway/).
Configuration changes use served apply. Binary rollout and writer ownership
transfer are explicit operator steps.

## Validation and contributions

Schemas and queries are executable examples. Before changing one, read the
root and cookbook `CLAUDE.md` (`AGENTS.md` links to the same file). Run the
local qualification with released binaries on PATH:

```bash
python3 scripts/check-cookbooks.py
```

It checks every bundle and query, then boots isolated local servers to load
seeds, test reader/writer/admin permissions, and apply live schema/query updates
without restarting. Use `OMNIGRAPH_BIN` and `OMNIGRAPH_SERVER_BIN` to choose
explicit binaries. CI runs the same journeys plus the Railway preparation tests. No external
storage or embedding-provider credentials are needed. Failed runs retain their temporary fixture and server logs.

Keep schemas, queries, seeds and cookbook-specific explanations together. Link
to the engine guides for general syntax and operations.
