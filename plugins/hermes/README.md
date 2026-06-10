# Hermes ⇄ Omnigraph plugin

A [Hermes](https://hermes-agent.nousresearch.com) plugin that makes an **Omnigraph**
graph a first-class, hard-to-misuse capability for the agent. It wraps the
**`omnigraph` CLI** (CLI-first — **no MCP**) with config discovery, the
`omnigraph-best-practices` skill, guardrailed `query` / `schema` / `mutate` /
`capture` tools, a guard that blocks dangerous raw `omnigraph` calls, and
**capture-by-default** (proposes importing durable info the user shares).

Plugin name: **`omnigraph`** (installs to `~/.hermes/plugins/omnigraph/`).

---

## Why this exists

Out of the box, Hermes has **zero awareness** of Omnigraph. If you've got a graph
that's your system of record (people, tasks, projects, commitments, relationships),
Hermes won't consult it, won't know its schema, and — if it shells out to `omnigraph`
on its own — will trip the well-known footguns: the deprecated `read`/`change` verbs,
`table` output in automation, string-interpolated params, `load --mode overwrite`
against `main`, `schema apply` without a plan, and — worst — **blind retries after a
504 that duplicate append-only nodes** on remote graphs.

Separately, the discipline a power user keeps in their head ("consult the graph first;
fetch the schema before querying; write to a branch, never main; import durable info
into the graph") lives in editor config files the *agent never reads*. This plugin
**ports that discipline into Hermes and enforces it** — turning the high-frequency
mistakes from "remember not to" into "can't."

## What you get

| Surface | What it does |
|---|---|
| **9 tools** | `omnigraph_doctor`, `omnigraph_targets`, `omnigraph_schema`, `omnigraph_query`, `omnigraph_search`, `omnigraph_mutate`, `omnigraph_capture`, `omnigraph_lint`, `omnigraph_schema_plan` |
| **Discovery banner** | injects a per-turn note: the graph is the source of truth — consult it, fetch schema first, write to a branch |
| **Capture-by-default** | when you share durable info, Hermes proposes importing it (resolves identity via `ExternalID` first, writes to a branch) |
| **Guard** | blocks dangerous *raw* `omnigraph` calls even when the model bypasses the tools and uses the `terminal` tool |
| **Verify ritual** | remote mutations are confirmed via the commit head before/after — never blind-retried |
| **Bundled skill** | the full `omnigraph-best-practices` ruleset, loadable as `skill_view("omnigraph:best-practices")` |
| **CLI tree** | `hermes omnigraph doctor \| targets \| schema \| migrate-config \| setup` |
| **Slash** | `/omni doctor \| targets \| schema [t] \| q <alias> [args]` (CLI + gateways) |

## How it works with Hermes

The plugin is a standard Hermes plugin (`plugin.yaml` + `register(ctx)`), CLI-first by
design — every operation shells the `omnigraph` binary through one chokepoint
(`runner.py`) that bakes in the correct defaults (canonical verbs, flags after the
subcommand, `--format jsonl` / `--json`, params via a temp `--params-file`, creds via
the subprocess env, `--config` always passed explicitly). It hooks into Hermes at four
lifecycle points:

- **`on_session_start`** → discovers your `omnigraph.yaml` configs and indexes them into
  a registry (so graphs resolve *by name*, cwd-independently).
- **`pre_llm_call`** → injects the discovery banner + a relevance-gated capture nudge
  (appended to the user message, so prompt caching is preserved).
- **`pre_tool_call`** → the guard: inspects `terminal` calls whose argv is `omnigraph`
  and blocks the dangerous set (allow-by-default, so it never nags).
- **`transform_tool_result`** → redacts any leaked bearer-token value from results.

The model sees the 9 tools and the banner; when you share something worth remembering it
reaches for `omnigraph_capture`; when it needs facts it reaches for `omnigraph_query`
after `omnigraph_schema`. Writes go through `omnigraph_mutate`, which runs the verify
ritual and targets a feature branch — `main` is never written directly.

> **⚠ Runtime requirement — the model must be able to *call tools*.** The plugin's tools
> are only useful under a Hermes runtime that exposes Hermes's tool registry to the model
> (the default **`openai_runtime: auto`** = chat_completions harness). Under
> **`codex_app_server`** the model runs in Codex's own sandboxed shell loop and Hermes's
> registered tools are **not** exposed to it (and tool network is sandboxed off) — so the
> banner still reaches the model but the tools/guard don't apply. If your tools aren't
> showing up, switch with `/codex-runtime auto` (or set `model.openai_runtime: auto`).

## Install & enable

```bash
# From this repo (ships the bundled skill):
hermes plugins install ModernRelay/omnigraph-cookbooks --enable
# …or for local development, symlink + enable (a plugin cannot enable itself):
ln -sfn "$PWD/plugins/hermes" ~/.hermes/plugins/omnigraph
hermes plugins enable omnigraph
```

Prerequisites: the `omnigraph` CLI (`>= 0.6.0`) on PATH, a bearer token in the env var
your `omnigraph.yaml` references (e.g. `OMNIGRAPH_BEARER_TOKEN`), and a tool-calling
runtime (see the runtime note above). The write tools are hidden until a token is set;
reads and `omnigraph_doctor` work without one. After enabling:

```bash
hermes omnigraph setup     # version, discovered configs, tokens, migrate-config suggestions
hermes omnigraph doctor    # binary, configs, tokens, reachability
```

## Config knobs

Graph definitions stay in your `omnigraph.yaml` (the CLI reads them); the plugin owns
only behaviour. In `~/.hermes/config.yaml`:

```yaml
plugins:
  enabled: [omnigraph]
  entries:
    omnigraph:
      default_target: personal          # default graph when a tool omits target
      capture: { mode: suggest }        # suggest | auto-branch | off
      guard: { level: high }
      search_aliases: { personal: semantic-transcripts }
      config_paths: []                  # optional explicit omnigraph.yaml hints
```

## Config discovery

`discovery.resolve()` finds the config to use (first match wins — **no merge**): explicit
`--config` → `OMNIGRAPH_CONFIG` → **registry lookup by target name** → cwd walk-up for
`omnigraph.yaml` → XDG / `~/.omnigraph` / `~/omnigraph.yaml`. The runner then *always*
passes `--config` explicitly, so resolution is deterministic regardless of cwd. The
tool-neutral registry (`$XDG_STATE_HOME/omnigraph/registry.yaml`) indexes target → config
so any graph resolves by name. (This is a removable bridge for a fix that ultimately
belongs in the `omnigraph` binary itself.)

## Safety model

- **Guard** blocks deprecated `read`/`change`, raw `mutate`, `load --mode overwrite`,
  `schema apply` without a plan, and flags-before-subcommand — even via `terminal`.
- **Verify ritual** (`omnigraph_mutate`, remote) compares the branch commit head
  before/after → `landed` / `did_not_land` / `safe_retry`; never blind-retries
  append-only types after a 504.
- **Capture-by-default** resolves identity via `ExternalID` first (no duplicate `Person`)
  and writes to a branch, never `main`.

## Develop / test

```bash
~/.hermes/hermes-agent/venv/bin/python tests/test_plugin.py     # offline unit suite (15 tests)
HERMES_PLUGINS_DEBUG=1 hermes plugins list                      # discovery diagnostics
```

## Notes

- **CLI-first, no MCP** by design.
- The upcoming omnigraph **cluster-config** control plane (`cluster.yaml` + state ledger)
  is out of scope here; `discovery.py` reserves the operator-vs-cluster distinction for
  when `omnigraph cluster *` serves traffic. See the RFC in
  `.context/rfc-hermes-omnigraph-plugin.md`.
