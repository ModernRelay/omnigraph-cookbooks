# CLAUDE.md

Repo-wide guidance for Claude Code. Each starter also has its own `CLAUDE.md` — read both when working inside a starter folder.

## What This Repo Is

A collection of Omnigraph starters — each one a self-contained schema + seed + queries for a SPIKE-style intelligence graph. See `README.md` for the framework and starter list.

## Repo Structure

- Root: per-starter folders + top-level README/CLAUDE
- Each starter folder (e.g. `industry-intel/`) is fully self-contained
- Omnigraph CLI and schema design reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph)

## Conventions Across Starters

- **SPIKE primitives are the default vocabulary.** Signal, Pattern, Insight, KnowHow, Element. Don't rename them without a strong reason.
- **Flat node types with `kind` enums** over subtypes or interfaces.
- **`slug` is external identity everywhere.** `@key` on slug; prefixes like `sig-`, `pat-`, `el-` make grep trivial.
- **Verb+target edge naming.** `FormsPattern`, `DevelopedByCompany` — direction is readable from the name.
- **Domain is a property, not a node.** Kept as an inline enum on whatever node needs classification.
- **Comments in `.pg` files use `//` not `#`.**

## Working in a Starter

Always `cd` into the starter folder first:

```bash
cd industry-intel
set -a && source ./.env.omni && set +a
ogdev query lint --schema ./schema.pg --query ./queries/signals.gq
```

The `query lint` command validates queries against the schema — run it after any schema or query edit.

## When Adding a New Starter

- Copy `industry-intel/` as a template — its structure is the reference shape
- Reuse SPIKE primitives where the domain fits; adapt enums to the domain
- Ship real seed data, not placeholders — the value of a starter is that it's opinionated
- Keep per-starter `README.md` and `CLAUDE.md` in sync with `schema.pg`
