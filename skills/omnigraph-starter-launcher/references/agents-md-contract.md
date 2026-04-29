# `AGENTS.md` contract

Each shipped starter's `AGENTS.md` is the operational manual a launcher (or a fresh agent) reads to take a user from *"I want to try this"* to a working graph + first read.

This file specifies the H2 sections the launcher expects, the order, and what each is for. Authoring a new `AGENTS.md` means writing these sections with content that follows the conventions below.

The canonical reference implementation is `gtm-for-infra/AGENTS.md` in this repo.

## Required H2 sections

In this order:

### `## About`

One paragraph explaining what the starter is and who it is for. Should be parseable without prior context (don't open with *"An Omnigraph schema and seed for…"* — that requires the reader to already know what Omnigraph is). Optionally followed by a node diagram.

### `## First-contact onboarding`

The branches a fresh user typically wants. Standard set:

1. **Demo** — run Prerequisites → Bootstrap → Headline; offer Follow-ups.
2. **Setup for own data** — run Prerequisites → Bootstrap with the shipped seed first; walk through swap-data follow-up.
3. **Just exploring** — explain, don't bootstrap.
4. *(Optional)* **Editorial** — for users who want to edit the schema; route to `## When editing` instead of bootstrap.

Each branch is numbered, titled in the user's voice (*"Demo me the graph"*), and maps to specific subsequent sections. Include an explicit fallback: *"if intent is unclear, default to branch (1)"* — so an executing agent never deadlocks.

### `## Prerequisites`

Verifiable shell commands that confirm the user's environment is ready. Each independently runnable. Don't combine with bootstrap — keep them separate so the launcher can fail fast.

```bash
omnigraph --version              # need >= 0.2.2
command -v omnigraph-server      # verify on PATH
```

If a prerequisite fails, the file should specify the remediation in prose right under the block. Don't use `--version` as a probe for binaries that don't support it (we caught this in `gtm-for-infra/AGENTS.md` — `omnigraph-server --version` errors).

### `## Bootstrap`

The bash blocks that take an empty environment to a running graph. Should:

- **Parameterize** `$REPO`, `$PORT`, `$PIDFILE`, `$LOGFILE` so a launcher can substitute on collision. The four variables move together — if the launcher picks a non-default port, all four must be renamed to match.
- **Document defaults explicitly** (e.g. `REPO=/tmp/<starter>/repo`, `PORT=8090`).
- **Document collision behavior**: state that `init`/`load` are storage-only and only `omnigraph-server` cares about `$PORT`, so a port collision doesn't require a fresh `$REPO`.
- **Track the background server PID** in `$PIDFILE` so `## Teardown` works.
- **Note the `--uri` requirement** if the bound port differs from `omnigraph.yaml`'s default `local_server.uri`. Either include `--uri http://127.0.0.1:$PORT` in every subsequent read/change command, or instruct the launcher to do so.

### `## Headline`

The single read that demonstrates the starter's value. One command, expected output captured verbatim from a real run, brief narration of why it matters.

Don't include more than one headline — pick the strongest. Additional reads belong in `## Follow-ups`.

The headline output should be a literal terminal block, not a styled markdown table. The launcher will compare actual output to expected; verbatim makes the comparison reliable.

### `## Follow-ups`

Optional next steps after Headline. Each is an `### subsection` with:

- A title in the user's voice (*"See prompt-version provenance"*, *"Live enrichment via X"*).
- A bash block with starter-specific external commands or read aliases.
- A short paragraph explaining what just happened.
- For external enrichment follow-ups, provide only starter-specific context: source rows, fields to request, semantic mapping into the graph, and verification alias. The launcher supplies the reusable Omnigraph schema-discovery, transient-transform, merge, and scratch-directory mechanics.

Use portable temporary directories in examples (`WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/<starter>.XXXXXX")"`), not repo-specific hidden folders such as `.context/`.

**Follow-ups that cost money or mutate persistent data must be flagged with `**Ask before running.**`** so the launcher knows to gate them. Example from `gtm-for-infra/AGENTS.md`:

> **Ask before running.** This costs real money on the user's Parallel account and takes ~1–2 min per account. Confirm scope (which accounts, how many) before kicking off.

### `## Ask-the-user moments`

A checklist of decision points where an executing agent must stop and ask. Examples:

- Before any follow-up that costs API credits.
- Before `--mode overwrite` against any path that isn't `/tmp/...`.
- Before editing `seed.jsonl` when the user has said *"set this up for my own data"*.
- Before `omnigraph schema apply` without a successful prior `schema plan`.

The launcher consults this list at every relevant step. The list is the single source of truth for "where to interrupt."

### `## Teardown`

How to clean up at session end:

```bash
kill "$(cat "$PIDFILE")" 2>/dev/null
rm -rf "$REPO" "$PIDFILE" "$LOGFILE"
```

## Optional H2 sections

Useful for editorial intent (branch 4 of First-contact) and for agents working on schema/queries. The launcher does not execute these — they are read-only context.

- `## Domain model` — entity list, canonical traversals, lineage rules.
- `## Design choices to preserve` — load-bearing decisions that shouldn't be churned without reason.
- `## When editing` — checklist for schema or query edits (lint after every edit, prefer narrower types, use `@rename_from` for renames, etc.).
- `## Files` — quick reference to the starter's layout.
- `## Repo-wide conventions` — pointer to `../CLAUDE.md` for storage URI, server lifecycle, canonical workflow.

## Cold-testing your `AGENTS.md`

The contract is only useful if a fresh agent can execute it without prior context. To verify:

1. Spawn a subagent with no prior conversation context.
2. Tell it: *"follow `AGENTS.md` literally; do not read `README.md` or other files; report what worked and what was unclear."*
3. Test both **clear intent** (*"demo me"*) and **ambiguous intent** (*"help me with this folder"*).
4. Apply the friction the cold test surfaces. Common findings:
   - Port-handling instructions that silently fall back to a default.
   - Prerequisite checks that don't actually verify (e.g. `--version` on a binary that errors).
   - Branch routing that's unambiguous on paper but misses a category (we added `editorial` to `gtm-for-infra` after this kind of test).
   - Teardown paths that don't move with custom `$REPO` / `$PORT` substitution.

Two cold tests on `gtm-for-infra/AGENTS.md` produced four concrete fixes before it shipped. Worth the spend.

## Worked example

`gtm-for-infra/AGENTS.md` is the canonical worked example. Read it as the reference implementation when authoring a new starter's `AGENTS.md`.
