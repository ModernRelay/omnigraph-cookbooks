# OmniGraph Cookbooks

Ready-to-run graph examples for **OmniGraph 0.15.0**. Each folder contains a
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

Install the matching 0.15.0 CLI and server from the
[engine release](https://github.com/ModernRelay/omnigraph/releases/tag/v0.15.0).
Check `omnigraph version`; it should report 0.15.0 and HTTP contract 0.14.
You also need Python 3 and `openssl` for the local HTTPS gateway below.
The examples use `industry-intel` / `spike`; substitute the folder and Graph ID
from the table for another cookbook.

### 1. Create the cluster

Validate and preview before creating storage. Every command below names the
cookbook folder, so it runs the same from the repository root or from anywhere
else; set `COOKBOOK` once:

```bash
export COOKBOOK=$PWD/industry-intel     # the folder holding this cookbook's cluster.yaml
omnigraph cluster validate --config "$COOKBOOK"
omnigraph cluster plan --target "$COOKBOOK" --config "$COOKBOOK" --json
omnigraph cluster apply --target "$COOKBOOK" --config "$COOKBOOK" --as act-admin --json
```

`--config` names the folder holding `cluster.yaml`; `--target` names the
storage root, here the same folder. Fresh apply creates the ledger, graph and
stored-query registry, and prints an **Admission lock** ID. There is no
separate import step.

The apply process keeps that lock after it exits. Wait for it to complete,
make sure nothing else writes to this folder, then clear that exact lock ID
once and start the server:

```bash
omnigraph cluster force-unlock '<LOCK_ID_FROM_APPLY>' --target "$COOKBOOK"
export OMNIGRAPH_SERVER_BEARER_TOKENS_JSON='{"act-admin":"local-admin-token","act-writer":"local-writer-token","act-reader":"local-reader-token","act-agent":"local-agent-token"}'
omnigraph-server --cluster "$COOKBOOK" --bind 127.0.0.1:8080
```

Leave the server running. The sample tokens are for this loopback demo; choose
your own secrets for a shared deployment. The roles are: admin manages
configuration and data; writer reads and writes data and branches; reader reads
and invokes stored read queries. Cookbooks with agents, such as company-brain
and hardware-program, also define `act-agent`, which writes only on review
branches. Policies are part of each bundle, and they are the only gate: an
agent reaching the graph over MCP (`omnigraph mcp --target <t> --graph <id>`,
plus `--write` for the write tools) gets exactly the operations its role
allows, with no server-side MCP switch to set.

Stopping the server with Ctrl-C releases its writer lock, so the next start
needs no unlock. A server that was killed keeps the lock; follow the engine's
[ownership-transfer rules](https://github.com/ModernRelay/omnigraph/blob/v0.15.0/docs/user/deployment.md#writer-topology)
before clearing it.

### 2. Reach the server over HTTPS

The CLI sends tokens only over HTTPS, and `omnigraph-server` speaks plain
HTTP. In a second terminal, run the local gateway from the repository root. It
creates a private CA and a `localhost` certificate on first use and relays
`https://localhost:8443` to the server:

```bash
export OMNIGRAPH_HOME=~/.omnigraph-cookbooks   # keeps this demo apart from your own CLI setup
python3 scripts/local-tls-gateway.py
```

Making the certificate takes a moment on the first run, so the gateway starts
listening a little after the command does. If you are scripting this rather
than watching a terminal, wait for it before the next step — a request that
arrives early is refused at the socket, and the CLI reports that as a failure
to establish the HTTP contract:

```bash
until curl -fsS --cacert "$OMNIGRAPH_HOME/local-tls/ca.pem" \
  https://localhost:8443/readyz >/dev/null 2>&1; do sleep 0.2; done
```

It is for local demos only. A deployment terminates TLS at its proxy or
platform.

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

Still with `COOKBOOK` from step 1, so this works from any directory:

```bash
curl -fsS --cacert "$OMNIGRAPH_HOME/local-tls/ca.pem" https://localhost:8443/readyz
# Append once to the new empty graph. Keep the exact commit receipt.
omnigraph load --target local --graph spike --data "$COOKBOOK/seed.jsonl" --mode append --json
omnigraph queries list --target local --graph spike
omnigraph query recent_signals --target local-reader --graph spike
omnigraph access --target local-reader --graph spike --branch main
```

Use a query from your cookbook if it has a different Graph ID. Reads take
`--format table|json|jsonl|csv|kv|toon`; `toon` carries the same document as
`json` but names each field once across uniform rows, so it is the cheaper
shape to put in an agent's prompt. Seeds are inputs, not live state: query the
server to answer questions. Loading does not generate
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
verify `Omnigraph-Http-Api: 0.14`, which 0.15 keeps unchanged; the CLI and SDK
handle this automatically. Failed calls answer a `code` and a `disposition`
whose `effects` (`none`, `partial` or `unknown`) say whether anything changed.
Process settings and static tokens still require a server restart.

## Upgrading

Upgrade the CLI, server and client integrations together. 0.15 keeps the 0.14
HTTP contract and the 0.14 storage formats, so these bundles move across
unchanged: a graph these examples created opens in 0.15 with no rebuild and no
offline `upgrade`, and a graph written by 0.13 is still served as it is and
stamped format 16 by its next publication.

Two 0.15 changes can refuse a bundle that 0.14 accepted:

- **An edge `@card` minimum is now checked on every write.** `@card(1..1)` and
  `@card(1..)` edges, which several cookbooks here declare, mean a node must
  arrive with those edges in one mutation query or one JSONL load; 0.14 only
  checked some write paths, so a graph could hold nodes that broke its own
  schema. Find them with a `not { $n someEdge $_ }` query before upgrading, and
  note that `schema apply` refuses a new edge type that puts a minimum on an
  existing node type (`OG-MF-107`).
- **`@unique` on a list or vector property is refused.** 0.14 parsed it but
  every write that set the property failed. Drop those properties in one apply
  and add them back without the constraint in the next.

If you serve MCP, read the release's upgrade actions first: `/mcp` now lists
every tool the caller's policy allows, writes included, and the
`--mcp-allow-writes` / `--mcp-allow-adhoc` flags are gone. Policy is the only
place that decides what an agent may run.

The operator configuration is unchanged from 0.14 (`version: 1`). Coming from
0.13 or earlier, follow the engine's
[0.15 release notes](https://github.com/ModernRelay/omnigraph/releases/tag/v0.15.0),
[0.13 to 0.14 checklist](https://github.com/ModernRelay/omnigraph/blob/v0.15.0/docs/user/operations/upgrade-0.14.md)
and [upgrade guide](https://github.com/ModernRelay/omnigraph/blob/v0.15.0/docs/user/operations/upgrade.md).

## SPIKE framework

Industry and pharma intelligence use Signal (observed fact), Pattern (recurring
theme), Insight (interpretation), KnowHow (practice) and Element (concrete
subject). This is a cookbook modeling convention, not an engine requirement.

## Skills and deployment

The OmniGraph skill is not kept here. Every `omnigraph` binary carries the copy
written for its own commands and HTTP contract, so an agent gets the matching
one from the CLI it runs:

```bash
omnigraph skill export ~/.claude/skills/omnigraph --force   # or ~/.codex/skills
omnigraph skill show references/queries.md                  # read one file
```

A copy committed beside the cookbooks would be a second source that drifts from
the pinned release; `skills/omnigraph` in
[ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph) is the one
that does not.

The [industry bootstrap skill](industry-intel/skill/) guides domain selection,
research and seed preparation. Install it with:

```bash
npx skills add https://github.com/ModernRelay/omnigraph-cookbooks/tree/main/industry-intel/skill
```

## Validation and contributions

Schemas and queries are executable examples. Before changing one, read the
root and cookbook `CLAUDE.md` (`AGENTS.md` links to the same file). Run the
local qualification with released binaries on PATH:

```bash
python3 scripts/check-cookbooks.py
```

It checks every bundle and query, then boots isolated local servers behind the
local HTTPS gateway to load seeds, test reader/writer/admin permissions, and
apply live schema/query updates without restarting. Use `OMNIGRAPH_BIN` and
`OMNIGRAPH_SERVER_BIN` to choose explicit binaries. CI runs the same journeys
with the release pinned in `.github/workflows/qualify.yml`. No external storage
or embedding-provider credentials are needed. Failed runs retain their
temporary fixture and server logs.

Keep schemas, queries, seeds and cookbook-specific explanations together. Link
to the engine guides for general syntax and operations.

## Cookbook READMEs

A cookbook README reads as the landing page of OmniGraph for one use case: a
living source of truth for the people and agents doing that work, and the
agent workflows that run around it. It follows one template, and omnigraph.dev
will draw its use-case page from the same sections. Commands, roles and
step-by-step workflows belong in the cookbook's `AGENTS.md`.

The template, the rules for each section and how to write one are in
[AGENTS.md](AGENTS.md#writing-a-cookbook-readme).
[hardware-program](hardware-program/README.md) and
[company-brain](company-brain/README.md) are the worked examples. The
check holds every cookbook to the template.

## The website

[omnigraph.dev/use-cases](https://www.omnigraph.dev/use-cases) is built from
this repository: each cookbook's schema, stored queries, sample counts and
README are imported on every site build. What the site says about a cookbook
lives in its `site.json`:

| Field | Shown as |
|---|---|
| `order` | its place in the directory |
| `name`, `category`, `blurb` | the card and the page header; `category` is one of Company, Engineering, Hardware, Research, Investing, Personal |
| `about` | optional, 600 characters at most: the "What it is" paragraph under the header. Two to four sentences on what the graph is, who it is for and what it takes the place of |
| `sample` | what the seed data depicts, beside its counts |
| `questions` | "Questions it answers": each `q` names a stored **read** query in `queries/*.gq`, with the `params` to run it with where it takes any |
| `search` | the page's `<title>` (60 characters at most, leading with the phrase people search), an optional `heading` (70 at most: the second line of the page's H1, in the searcher's words) and the keywords its structured data carries |
| `use_case`, `needs`, `capabilities` | not shown yet. The use case the cookbook serves, the needs it meets and the capabilities it uses, by their slugs in ModernRelay's mr-ops graph. Each need and capability names, in `shown_in`, the heading of the README that shows it. Leave all three out where mr-ops has no use case for the cookbook |

`python3 scripts/check-cookbooks.py --site` checks every `site.json`, and the
README sections where they apply, offline in under a second; the full run
checks them first and, for those cookbooks, runs each question against the
seed. Rename or remove a query in
the same change as the question that names it. A push to `main` that touches a
cookbook rebuilds the site (`.github/workflows/refresh-site.yml`); a cookbook
without a `site.json` still appears there, under "More", with its README's
title and first paragraph.
