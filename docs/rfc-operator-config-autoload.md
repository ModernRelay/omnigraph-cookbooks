# RFC: Auto-Load Omnigraph Operator Config

Status: Draft
Date: 2026-06-12
Related: Omnigraph operator config, legacy `omnigraph.yaml` deprecation, agent/plugin integration

## Summary

The Omnigraph CLI should automatically load the operator config from the standard operator location for every command that needs operator-layer information.

The operator config is:

```text
$OMNIGRAPH_HOME/config.yaml
~/.omnigraph/config.yaml
```

This is not a replacement for deployment config and must not be passed through `--config`. It is an ambient operator layer: identity, known servers, credentials, output defaults, and personal aliases.

The desired user-facing result:

```bash
omnigraph --server prod --graph knowledge schema show
omnigraph --server staging --graph research query --alias weekly-triage
omnigraph --as act-user cluster apply --config ./team-graph
```

These should work from any current working directory, with the CLI resolving `prod`, `staging`, credentials, and default actor from the operator config and credential chain.

## Problem

Omnigraph now has two clean config surfaces:

| Surface | Owner | File | Purpose |
|---|---|---|---|
| Operator config | One person | `~/.omnigraph/config.yaml` | Who I am and which servers I know |
| Cluster config | Team/project | `cluster.yaml` | What the graph deployment is |

For agent and CLI ergonomics, the operator config needs to behave like `gh` hosts or AWS profiles: once configured, named servers and identity should be available everywhere.

The CLI already has an operator config loader and several call sites use it, but the product contract should be explicit:

- operator config is automatically discovered from the standard location;
- `--config` is not how users point at operator config;
- plugins and agents should store only lightweight pointers like `server#graph`;
- legacy `omnigraph.yaml` should not be part of new workflows.

Without this contract, downstream tooling is tempted to reintroduce config-path pointers, duplicate endpoint/token data, or invent plugin-specific config.

## Goals

- G1: Make operator config ambient and cwd-independent.
- G2: Keep deployment truth explicit and project-owned through `cluster.yaml`.
- G3: Make `server#graph` the stable pointer format for plugins, agents, and docs.
- G4: Keep secrets out of plugin config, repo config, and command examples.
- G5: Preserve a short, understandable precedence model.

## Non-Goals

- NG1: Do not auto-discover `cluster.yaml` from `$HOME`.
- NG2: Do not make `~/.omnigraph/config.yaml` a `--config` file.
- NG3: Do not support legacy `omnigraph.yaml` in new plugin design.
- NG4: Do not introduce a wrapper binary or plugin-side endpoint resolver.
- NG5: Do not store bearer tokens in YAML.

## Proposed Contract

### Operator Config Discovery

For operator-layer data, the CLI resolves:

```text
1. $OMNIGRAPH_HOME/config.yaml
2. ~/.omnigraph/config.yaml
3. empty operator config
```

Absent file is not an error. Malformed file is a loud error.

This layer is loaded automatically by command paths that need:

- `--server <name>` resolution;
- keyed credentials for a matched server URL;
- `operator.actor`;
- output defaults;
- operator aliases;
- future operator-scoped defaults.

### Deployment Config Discovery

Deployment config remains explicit:

```bash
omnigraph cluster plan --config ./team-graph
omnigraph cluster apply --config ./team-graph
omnigraph-server --cluster ./team-graph
```

`cluster` commands may default `--config .`, because `.` is the command's explicit working context. They should not walk up directories or read `~/.omnigraph/config.yaml` for deployment facts.

### Addressing Remote Graphs

The primary remote graph address for humans, agents, and plugins is:

```text
<server>#<graph>
```

It maps to:

```bash
omnigraph --server <server> --graph <graph> ...
```

The server name resolves through operator config:

```yaml
servers:
  prod:
    url: https://graph.example.com
  staging:
    url: https://staging-graph.example.com
```

Credentials resolve through the keyed credential chain:

```text
OMNIGRAPH_TOKEN_<SERVER>
~/.omnigraph/credentials [<server>]
```

The normal setup path is:

```bash
omnigraph login prod
omnigraph login staging
```

## Precedence

For operator identity:

```text
--as > operator.actor > none
```

No legacy `cli.actor` in new workflows.

For server address:

```text
--server <name> > explicit URI
```

`--server` should remain exclusive with explicit URI-style targeting. A command should not silently choose one when both are present.

For graph id:

```text
--graph <id> when --server is multi-graph
```

Single-graph servers may omit `--graph`.

For output:

```text
--json > --format > operator alias format > operator defaults.output > table
```

## Plugin Implications

A plugin can store lightweight pointers:

```json
{
  "graphs": ["prod#knowledge", "staging#research"]
}
```

It can call:

```bash
omnigraph --server prod --graph knowledge schema show
omnigraph --server prod --graph knowledge query --alias recent
```

It should not store:

- endpoint URLs;
- bearer token env var names;
- bearer tokens;
- `omnigraph.yaml` paths;
- `cluster.yaml` paths for global graphs.

For project-local graph work, it should detect `cluster.yaml` in the project and use cluster commands. If it sees `omnigraph.yaml`, it should treat it as unsupported legacy config and suggest:

```bash
omnigraph config migrate
```

## CLI Implementation Guidance

The current CLI already has the right pieces:

- `operator_dir()` resolves `$OMNIGRAPH_HOME` or `~/.omnigraph`.
- `load_operator_config()` returns empty config if absent.
- `resolve_server_flag()` resolves `--server` through operator config.
- `resolve_keyed_token()` resolves server-keyed credentials.
- `resolve_actor()` can fall through to `operator.actor`.

The RFC recommendation is to make this a maintained invariant:

> Any command path that accepts `--server`, resolves actor identity, resolves operator aliases, or sends a bearer token must use the operator resolver, not parse `~/.omnigraph/config.yaml` ad hoc and not route through legacy graph config.

## Validation

Add or keep tests for:

1. `omnigraph --server prod --graph knowledge schema show` works with only `~/.omnigraph/config.yaml` and no `./omnigraph.yaml`.
2. `--server` errors clearly when the server is unknown and lists known servers.
3. `--server` is exclusive with positional URI and `--target`.
4. `OMNIGRAPH_HOME` changes the operator config location.
5. Missing operator config behaves as empty config.
6. Malformed operator config fails loudly.
7. Keyed token is sent only to URLs matching that server's configured URL.
8. `cluster plan --config .` does not read deployment facts from operator config.
9. Plugin-style pointer parsing `server#graph` maps to the exact CLI command shape.

## Open Questions

- O1: Should single-graph `--server prod` omit `--graph`, or should plugins always require an explicit graph id for uniformity?
- O2: Should operator aliases grow mutation support, e.g. `kind: query|mutate`, so capture can be expressed without legacy aliases?
- O3: Should there be a CLI inspection command such as `omnigraph config operator show --json` for plugins to validate `server#graph` pointers without invoking a graph command?

## Decision

Adopt the operator-config autoload contract.

For new agent/plugin work, the stable default is:

```text
server#graph pointer -> omnigraph --server server --graph graph ...
```

Legacy `omnigraph.yaml` is out of scope for new plugin design.
