# Hermes ⇄ Omnigraph plugin (slim)

A deliberately tiny [Hermes](https://hermes-agent.nousresearch.com) plugin that makes an
**Omnigraph** graph a first-class part of the agent — by doing **three things and nothing else**:

1. **Awareness** — discovers your `omnigraph.yaml` and its graphs.
2. **Skill** — installs the `omnigraph-best-practices` skill from the repo's GitHub **tap**.
3. **Reminders** — injects a per-turn note telling the model to *consult the graph* and
   (optionally) *save durable info to it*.

Everything operational — querying, writing, schema, branches — is the **`omnigraph` CLI**, run by
the model through the built-in `terminal` tool, guided by the skill. **No tools, no guard, no
re-encoded flags or schema** — so the plugin doesn't drift as omnigraph evolves.

## Why so small

A previous version wrapped the CLI in 9 typed tools + a guard + a write-verification ritual +
capture scaffolding (~1,600 LOC). That re-encoded omnigraph's flag surface and even graph-specific
node-type names — a maintenance burden that grows every time the CLI changes. This version is ~250
LOC and couples to almost nothing: it reads one config file and injects text.

## How it works with Hermes

`register(ctx)` wires **two hooks** and **one CLI command** — zero model-facing tools:
- `on_session_start` → resolve + cache the omnigraph config.
- `pre_llm_call` → inject the reminder (appended to the user message, so prompt caching is preserved):
  the graphs available, the config path (so the model passes `--config`), "consult before answering /
  fetch schema first / load `skill_view("omnigraph-best-practices")`", and — per `autocapture` — a
  "save durable info to a branch / to main" instruction. The **model** judges relevance and composes
  any write itself from the live schema; the plugin holds **zero** node/edge/enum names.
- `hermes omnigraph doctor` / `setup` → diagnostics + skill-tap install (human-facing).

## Install

```bash
# enable the plugin (a plugin can't enable itself)
ln -sfn "$PWD/plugins/hermes" ~/.hermes/plugins/omnigraph   # or: hermes plugins install ModernRelay/omnigraph-cookbooks
hermes plugins enable omnigraph

# install the skill from the repo's tap + see config tips
hermes omnigraph setup
```

> **Runtime:** the reminders reach the model under any runtime, but for the model to actually *run*
> `omnigraph` (or any tool) it needs Hermes's chat_completions harness — set
> `model.openai_runtime: auto` (not `codex_app_server`).

## Config

```yaml
plugins:
  enabled: [omnigraph]
  entries:
    omnigraph:
      config_path: ~/omnigraph.yaml   # where your omnigraph.yaml is (no folder hunting)
      autocapture: branch             # off | branch | main
      default_target: personal
      remind_every_turn: false        # reminder injects on session start; true = every turn
```

- **`config_path`** — explicit path to your `omnigraph.yaml`. Resolution if unset:
  `$OMNIGRAPH_CONFIG` → `~/omnigraph.yaml` → `./omnigraph.yaml`.
- **`autocapture`** — the single capture knob: `off` (no save nudge), `branch` (save durable info to a
  feature branch + suggest a merge — default), `main` (save directly to main).

## The skill (via tap, not bundled)

The plugin ships **no skill copy**. The repo is already a valid Hermes tap (`skills/<name>/SKILL.md`),
so `hermes omnigraph setup` runs `hermes skills tap add ModernRelay/omnigraph-cookbooks` +
`hermes skills install …/omnigraph-best-practices`. Single source of truth, auto-updates, and (unlike
bundled plugin skills) auto-indexed in `<available_skills>`.

## Test

```bash
~/.hermes/hermes-agent/venv/bin/python plugins/hermes/tests/test_plugin.py   # offline unit suite
HERMES_PLUGINS_DEBUG=1 hermes plugins list                                   # 0 tools / 2 hooks / 1 CLI
hermes omnigraph doctor
```
