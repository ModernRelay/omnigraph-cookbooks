# Local setup

How to serve one cookbook on your machine with its roles, and change it while
it runs. `scripts/check-cookbooks.py` runs this same sequence for every
cookbook on every pull request.

To only try a cookbook's questions, you do not need this. The prompt in each
cookbook's README has an agent load it into a local graph, following
[omnigraph.dev/onboarding.md](https://www.omnigraph.dev/onboarding.md).

This page holds what is specific to this repository: the folders, the role
tokens, the local HTTPS gateway and the CLI targets. What the commands mean
belongs to the engine, in the **omnigraph** skill that ships in the CLI:
`omnigraph skill show references/cluster.md` for `cluster` commands and locks,
`references/server-policy.md` for the server and roles, and
`references/data.md` for loads and writes.

## Before you start

- The 0.16.0 `omnigraph` and `omnigraph-server` on your PATH, from the
  [engine release](https://github.com/ModernRelay/omnigraph/releases/tag/v0.16.0).
  `omnigraph version` reports the release. The
  [install guide](https://www.omnigraph.dev/docs/getting-started/install.md#release-channels)
  shows how to pin a version.
- Python 3 and `openssl`, for the gateway.

The commands use `industry-intel` and its Graph ID, `spike`. For another
cookbook, take the folder and Graph ID from "Run it" in its README.

## 1. Create the cluster and start the server

```bash
export COOKBOOK=$PWD/industry-intel     # the folder holding this cookbook's cluster.yaml
omnigraph cluster validate --config "$COOKBOOK"
omnigraph cluster plan --target "$COOKBOOK" --config "$COOKBOOK" --json
omnigraph cluster apply --target "$COOKBOOK" --config "$COOKBOOK" --as act-admin --json
```


`--config` names the folder holding `cluster.yaml`, and `--target` names the
storage root, here the same folder. A fresh apply creates the graph and its
stored queries. It takes the folder's admission lock and, once the apply has
converged, releases it, so the server can start next. If
`omnigraph cluster status --target "$COOKBOOK" --json` still reports a
`lock_id`, the apply did not finish cleanly: read the engine's cluster
reference before clearing it. Then start the server:

```bash
export OMNIGRAPH_SERVER_BEARER_TOKENS_JSON='{"act-admin":"local-admin-token","act-writer":"local-writer-token","act-reader":"local-reader-token","act-agent":"local-agent-token"}'
omnigraph-server --cluster "$COOKBOOK" --bind 127.0.0.1:8080
```


Leave the server running. The tokens are for this loopback demo. Each one is
an actor in the cookbook's `policies/graph.policy.yaml`, which decides what it
may do; `act-agent` exists only in the cookbooks that define an agent role.

Ctrl-C releases the server's lock, so the next start needs no unlock. A server
that was killed, or that failed to open its graph, keeps it: follow the engine's
[ownership-transfer rules](https://github.com/ModernRelay/omnigraph/blob/v0.16.0/docs/user/deployment.md#writer-topology)
before clearing it.

## 2. Reach the server over HTTPS

The CLI sends tokens only over HTTPS, and `omnigraph-server` speaks plain
HTTP. In a second terminal, run the gateway from the repository root. It makes
a private CA and a `localhost` certificate on first use and relays
`https://localhost:8443` to the server:

```bash
export OMNIGRAPH_HOME=~/.omnigraph-cookbooks   # keeps this demo apart from your own CLI setup
python3 scripts/local-tls-gateway.py
```


The certificate takes a moment on the first run. In a script, wait for the
gateway before the next step:

```bash
until curl -fsS --cacert "$OMNIGRAPH_HOME/local-tls/ca.pem" \
  https://localhost:8443/readyz >/dev/null 2>&1; do sleep 0.2; done
```


The gateway is for local use only. A deployment terminates TLS at its proxy or
platform.

## 3. Configure the CLI

In a third terminal, give the CLI one target per role. The CA path is relative
to the configuration file:

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


Each target reads its token from one environment variable. Every command names
its target, or uses `local`, the default.

## 4. Load and query

With `COOKBOOK` set as in step 1:

```bash
curl -fsS --cacert "$OMNIGRAPH_HOME/local-tls/ca.pem" https://localhost:8443/readyz
# Append once to the new empty graph. Keep the exact commit receipt.
omnigraph load --target local --graph spike --data "$COOKBOOK/seed.jsonl" --mode append --json
omnigraph queries list --target local --graph spike
omnigraph query recent_signals --target local-reader --graph spike
omnigraph access --target local-reader --graph spike --branch main
```


The seed is a load input: once it is loaded, the served graph is what answers
questions. Append it once, to the empty graph, and do not replay a load after a
timeout without checking what it did. `omnigraph access` lists what a target's
role may do.

Each cookbook's `omnigraph-config.example.yaml` has read aliases for its
graph. Merge its `aliases:` block into `$OMNIGRAPH_HOME/config.yaml`, then run
one by name: `omnigraph alias <name> --params '{"slug":"..."}'`. The
cookbook's `AGENTS.md` has the command for each question and workflow.

## Live updates

Keep the server running. Edit the cookbook's schema, stored queries, policies
or provider settings, then validate, preview and apply through the server:

```bash
omnigraph cluster validate --config .
omnigraph cluster plan --target local --config . --json
omnigraph cluster apply --target local --config . --json
```


The server takes the change without restarting. A schema change needs `main`
to be the only live branch, so merge and retire review branches first.
Removing a graph from `cluster.yaml` deletes its storage and history for good,
so read the plan before applying.

Apply prints its deployment ID before it submits. If the wait times out, keep
watching that ID; do not submit again:

```bash
omnigraph cluster status --target local \
  --deployment-id '<DEPLOYMENT_ID>' --wait --timeout 1800 --json
```


Server process settings and static tokens still need a restart.

## Upgrading

Upgrade the CLI, the server and client integrations together. What a release
changes, and what it can refuse in a bundle the release before accepted, is in
the engine's
[release notes](https://github.com/ModernRelay/omnigraph/releases) and
[upgrade guide](https://github.com/ModernRelay/omnigraph/blob/main/docs/user/operations/upgrade.md).
The release these cookbooks are checked against is the one pinned in
[`.github/workflows/qualify.yml`](../.github/workflows/qualify.yml).
