---
name: hermes-ops
description: >-
  Decision tree for operating Omnigraph from Hermes via the omnigraph_* tools.
  Use when deciding read vs write, which target/graph, local vs remote, and how
  to capture durable info the user shares. Pairs with the omnigraph:best-practices
  skill (load that for the full ruleset, gotchas, and CLI reference).
license: MIT
metadata:
  author: ModernRelay
  version: "0.1.0"
---

# Operating Omnigraph from Hermes

You have a set of `omnigraph_*` tools that wrap the `omnigraph` CLI with correct
defaults baked in. **Prefer these tools over raw `terminal` calls** — a guard will
block the dangerous raw invocations anyway. For the full ruleset (schema authoring,
search, remote-ops 504 handling, policy), load `skill_view("omnigraph:best-practices")`.

## The graph is the source of truth

Before answering a factual question about people / tasks / projects / commitments /
places / relationships / media, **consult the graph** (`omnigraph_query`). Don't guess
from memory. If a query returns empty, say so — don't invent.

When the user *shares* durable info (a task, a person, a commitment, a place, a note,
a project, something they read/watched), **propose importing it** with
`omnigraph_capture` — the graph is the system of record, not the chat log.

## Decision tree

1. **Which graph?** Pick a `target` (e.g. `personal`, `modernrelay`). If unsure, call
   `omnigraph_targets` to list what exists. Default is the config's `cli.graph`.
2. **Reading?** Prefer a configured **alias** (`omnigraph_query` with `alias=...`).
   Only write an ad-hoc query when no alias fits — and **fetch the schema first**
   (`omnigraph_schema`) so you use real node/edge/enum names. Never guess fields.
3. **Searching by meaning?** Use `omnigraph_search` (scope-then-rank); it always adds
   the required `limit`.
4. **Writing?** Use `omnigraph_mutate` (never raw `terminal`). Writes go to a **branch,
   never `main`**. For remote graphs the tool runs the verification ritual and reports
   `landed` / `did_not_land` — **never blind-retry** after a dropped response.
5. **Capturing shared info?** Use `omnigraph_capture`. It fetches the schema, resolves
   identity via `ExternalID` first (so it never creates a duplicate `Person`), builds a
   parameterized mutation, and — by policy — either proposes it for your confirmation
   (`suggest`, default) or writes it to a branch (`auto-branch`).

## Hard rules (the tools enforce these; don't fight them)

- Canonical verbs are `query` / `mutate` — never the deprecated `read` / `change`.
- Parameterize everything; never string-interpolate values into `.gq` or params.
- Never write directly to `main`; never `load --mode overwrite` a populated graph.
- `schema apply` only after a successful `schema plan`.
- Resolve a `Person` through its `ExternalID` before creating a new one.

## When something breaks

- `omnigraph_doctor` reports binary/version, discovered configs, tokens, reachability.
- A 504 on a write means "status unknown" — verify via the commit head before retrying
  (the tool does this for you). A `409`/`429` is always safe to retry.
