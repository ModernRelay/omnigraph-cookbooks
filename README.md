# OmniGraph Cookbooks

Ready-to-run graph examples for **OmniGraph 0.14.0**. Each folder contains a
schema, real or clearly identified fictional seed data, stored queries, policies,
and a cluster declaration. Local examples use filesystem storage.

| Cookbook | Graph ID | Purpose |
|---|---|---|
| [Industry intel](industry-intel/) | `spike` | Industry evidence, patterns and insights |
| [Pharma intel](pharma-intel/) | `pharma` | Competitive intelligence and program decisions |
| [Second brain](second-brain/) | `brain` | Personal projects, relationships and notes |
| [VC operating system](vc-os/) | `vcos` | Deals, portfolio, relationships and investment beliefs |
| [Development graph](dev-graph/) | `dev` | Issues, decisions, specifications and releases |
| [Beads](beads/) | `beads` | A beads-style work queue for coding agents, with the `ob` client |
| [Company brain](company-brain/) | `company` | Claims, decisions and action items with the exact source text they rest on, shared by a company's people and agents |
| [Hardware program](hardware-program/) | `program` | Requirements, budgets, interfaces and verification for a hardware program |

## Local setup

Install the matching 0.14.0 CLI and server from the
[engine release](https://github.com/ModernRelay/omnigraph/releases/tag/v0.14.0).
Check `omnigraph version`; it should report 0.14.0 and HTTP contract 0.14.
You also need Python 3 and `openssl` for the local HTTPS gateway below.
The examples use `industry-intel` / `spike`; substitute the folder and Graph ID
from the table for another cookbook.

### 1. Create the cluster

From a fresh cookbook directory, validate and preview before creating storage:

```bash
cd industry-intel
omnigraph cluster validate --config .
omnigraph cluster plan --target . --config . --json
omnigraph cluster apply --target . --config . --as act-admin --json
```

`--config` names the folder holding `cluster.yaml`; `--target .` names the
storage root, here the same folder. Fresh apply creates the ledger, graph and
stored-query registry, and prints an **Admission lock** ID. There is no
separate import step.

The apply process keeps that lock after it exits. Wait for it to complete,
make sure nothing else writes to this folder, then clear that exact lock ID
once and start the server:

```bash
omnigraph cluster force-unlock '<LOCK_ID_FROM_APPLY>' --target .
export OMNIGRAPH_SERVER_BEARER_TOKENS_JSON='{"act-admin":"local-admin-token","act-writer":"local-writer-token","act-reader":"local-reader-token","act-agent":"local-agent-token"}'
omnigraph-server --cluster . --bind 127.0.0.1:8080
```

Leave the server running. The sample tokens are for this loopback demo; choose
your own secrets for a shared deployment. The roles are: admin manages
configuration and data; writer reads and writes data and branches; reader reads
and invokes stored read queries. Cookbooks with agents, such as company-brain
and hardware-program, also define `act-agent`, which writes only on review
branches. Policies are part of each bundle.

Stopping the server with Ctrl-C releases its writer lock, so the next start
needs no unlock. A server that was killed keeps the lock; follow the engine's
[ownership-transfer rules](https://github.com/ModernRelay/omnigraph/blob/v0.14.0/docs/user/deployment.md#writer-topology)
before clearing it.

### 2. Reach the server over HTTPS

The 0.14 CLI sends tokens only over HTTPS, and `omnigraph-server` speaks plain
HTTP. In a second terminal, run the local gateway from the repository root. It
creates a private CA and a `localhost` certificate on first use and relays
`https://localhost:8443` to the server:

```bash
export OMNIGRAPH_HOME=~/.omnigraph-cookbooks   # keeps this demo apart from your own CLI setup
python3 scripts/local-tls-gateway.py
```

It is for local demos only. A deployment terminates TLS at its proxy or
platform, as Railway does.

### 3. Configure the CLI

In a third terminal, point the CLI at the gateway with one target per role. The
CA path is relative to the configuration file:

```bash
export OMNIGRAPH_HOME=~/.omnigraph-cookbooks
cat > "$OMNIGRAPH_HOME/config.yaml" <<'EOF'
version: 1
targets:
  local:
    kind: server
    endpoint: https://localhost:8443
    auth: {provider: token, source: {env: OG_LOCAL_ADMIN_TOKEN}}
    transport: {tls: {ca: {mode: append, file: local-tls/ca.pem}}}
  local-writer:
    kind: server
    endpoint: https://localhost:8443
    auth: {provider: token, source: {env: OG_LOCAL_WRITER_TOKEN}}
    transport: {tls: {ca: {mode: append, file: local-tls/ca.pem}}}
  local-reader:
    kind: server
    endpoint: https://localhost:8443
    auth: {provider: token, source: {env: OG_LOCAL_READER_TOKEN}}
    transport: {tls: {ca: {mode: append, file: local-tls/ca.pem}}}
  local-agent:
    kind: server
    endpoint: https://localhost:8443
    auth: {provider: token, source: {env: OG_LOCAL_AGENT_TOKEN}}
    transport: {tls: {ca: {mode: append, file: local-tls/ca.pem}}}
defaults:
  target: local
  output: table
EOF
export OG_LOCAL_ADMIN_TOKEN=local-admin-token OG_LOCAL_WRITER_TOKEN=local-writer-token
export OG_LOCAL_READER_TOKEN=local-reader-token OG_LOCAL_AGENT_TOKEN=local-agent-token
omnigraph config validate
```

Each target reads its token from one named environment variable; the CLI reads
no other token variable. Every command names its target, or uses `local`, the
default.

### 4. Load and query

From the cookbook directory:

```bash
curl -fsS --cacert "$OMNIGRAPH_HOME/local-tls/ca.pem" https://localhost:8443/readyz
# Append once to the new empty graph. Keep the exact commit receipt.
omnigraph load --target local --graph spike --data seed.jsonl --mode append --json
omnigraph queries list --target local --graph spike
omnigraph query recent_signals --target local-reader --graph spike
omnigraph access --target local-reader --graph spike --branch main
```

Use a query from your cookbook if it has a different Graph ID. Seeds are inputs,
not live state: query the server to answer questions. Loading does not generate
embeddings; cookbooks with vector fields explain the optional offline pipeline.
Do not replay a load after a timeout without checking its outcome. `overwrite`
replaces every node/edge type present in the batch; use it only when that
replacement is intended. `access` lists what a target's role may do.

Each cookbook's `omnigraph-config.example.yaml` holds read aliases for its
graph. Merge its `aliases:` block into `$OMNIGRAPH_HOME/config.yaml`, then run
them by name, passing parameters by name: `omnigraph alias <name> --params
'{"slug":"..."}'`. Aliases only read. Mutations use `omnigraph mutate` with a
writer or admin target.

## Live updates

Keep the server running. Edit the cookbook's schema, stored queries, policies,
provider settings or graph declarations, then validate, preview and apply
through the server:

```bash
omnigraph cluster validate --config .
omnigraph cluster plan --target local --config . --json
omnigraph cluster apply --target local --config . --json
```

The server activates the change without restarting. Schema changes require
`main` to be the only live branch; merge and retire review branches first.
Removing a graph from `cluster.yaml` permanently deletes its managed storage
and history. Review the plan before applying.

Apply prints its deployment ID before submission. If waiting times out, continue
observing that ID instead of submitting a new deployment:

```bash
omnigraph cluster status --target local \
  --deployment-id '<DEPLOYMENT_ID>' --wait --timeout 1800 --json
```

Use `/readyz` for readiness. Raw graph and cluster HTTP calls must send and
verify `Omnigraph-Http-Api: 0.14`; the 0.14 CLI and SDK handle this
automatically. Failed calls answer a `code` and a `disposition` whose `effects`
(`none`, `partial` or `unknown`) say whether anything changed. Process settings
and static tokens still require a server restart.

## Upgrading

Upgrade the CLI, server and client integrations together. These examples create
format-16 graphs. A graph written by 0.13 opens in 0.14 without a rebuild; its
next write moves it to format 16. The operator configuration has a new format
with no importer: recreate your targets as above, and replace old commands
(`--server`, `--store`, `--cluster`, `login`, token environment variables,
positional alias arguments) with `--target`, `--config` and `--params`. A
cluster created with 0.11 or earlier needs an export and rebuild into a **new
cluster root** with the matching old and new tools. Follow the engine's
[0.13 to 0.14 checklist](https://github.com/ModernRelay/omnigraph/blob/3602c30896f6696c17cfdef28135d1749cd593ca/docs/user/operations/upgrade-0.14.md)
and [upgrade guide](https://github.com/ModernRelay/omnigraph/blob/v0.14.0/docs/user/operations/upgrade.md).

## SPIKE framework

Industry and pharma intelligence use Signal (observed fact), Pattern (recurring
theme), Insight (interpretation), KnowHow (practice) and Element (concrete
subject). This is a cookbook modeling convention, not an engine requirement.

## Skills and deployment

The [OmniGraph skill](.claude/skills/omnigraph/SKILL.md) is vendored for Claude
Code and linked from `.agents/skills/omnigraph` for Codex. Its immutable source
revision is in `scripts/omnigraph-skill.ref`; `scripts/sync-skill.sh` refreshes it
and records a content hash. This lets documentation corrections follow the
released engine without pretending the binary changed. To give an agent the
skill that matches the CLI it runs, export it from the binary instead:
`omnigraph skill export ~/.claude/skills/omnigraph`.

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

It checks every bundle and query, then boots isolated local servers behind the
local HTTPS gateway to load seeds, test reader/writer/admin permissions, and
apply live schema/query updates without restarting. Use `OMNIGRAPH_BIN` and `OMNIGRAPH_SERVER_BIN` to choose
explicit binaries. CI runs the same journeys plus the Railway preparation tests. No external
storage or embedding-provider credentials are needed. Failed runs retain their temporary fixture and server logs.

Keep schemas, queries, seeds and cookbook-specific explanations together. Link
to the engine guides for general syntax and operations.
