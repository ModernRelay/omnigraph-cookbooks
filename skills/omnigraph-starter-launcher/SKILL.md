---
name: omnigraph-starter-launcher
description: 'Launch a shipped Omnigraph starter from the omnigraph-starters repo (gtm-for-infra, industry-intel, etc.) — read its AGENTS.md, route the user through first-contact branches (demo / setup-for-own-data / explore / editorial), execute prerequisites + bootstrap + headline, then offer follow-ups. Use this when a user wants to demo a starter, get one running locally, see what a starter does, run the headline query, or run a follow-up against an already-bootstrapped starter. Triggers: "launch the gtm-for-infra starter", "demo me gtm-for-infra", "set up industry-intel for me", "show me what this starter does", "run the lookalikes query", "what does the headline read return", "I want to try this template", "spin this up", "get me to the aha". This skill is for *running* a shipped starter — for *creating* a new domain from scratch use omnigraph-intel-bootstrap; for *day-to-day operations* on a running graph use omnigraph-best-practices.'
license: MIT (see LICENSE at repo root)
compatibility: Requires omnigraph CLI >= 0.2.2 and a starter with AGENTS.md present.
metadata:
  author: ModernRelay
  version: "0.1.0"
  repository: https://github.com/ModernRelay/omnigraph-starters
---

# Omnigraph Starter Launcher

This skill takes a user from *"I want to see what `<starter>` does"* to a working graph plus a meaningful read in under a minute. It does this by treating each starter's `AGENTS.md` as the operational contract: the skill itself is small, and the per-starter detail lives in `AGENTS.md` as the source of truth.

## Scope vs. sibling skills

- **`omnigraph-starter-launcher`** *(this skill)* — launch a *shipped* starter from this repo. The starter exists; you want to run it.
- **`omnigraph-intel-bootstrap`** — author a *new* domain from scratch (elicitation + research + init/load). Use when the user wants a brand-new graph for an industry that isn't shipped.
- **`omnigraph-best-practices`** — day-to-day operations on a running graph (schema changes, query lint, mutations, server lifecycle).

If the user wants to *create* a new graph, hand off to `omnigraph-intel-bootstrap`. If they want to *operate* an already-running one, hand off to `omnigraph-best-practices`.

## The contract: AGENTS.md

Every shipped starter has an `AGENTS.md` at its root. This skill reads it and follows it literally. The contract has these H2 sections:

| Section | What this skill does with it |
|---|---|
| `## About` | Show to the user when explaining what the starter is. |
| `## First-contact onboarding` | Read the branches; route the user to one. |
| `## Prerequisites` | Run the listed checks; bail if any fail. |
| `## Bootstrap` | Execute the fenced bash blocks in order, with port/path overrides on collision. |
| `## Headline` | Run the headline read and show its output verbatim. |
| `## Follow-ups` | List as numbered options after Headline; execute the user's pick. Combine starter-specific follow-up context with this skill's reusable Omnigraph execution patterns. |
| `## Ask-the-user moments` | Use this checklist to gate destructive or expensive operations. |
| `## Teardown` | Offer at session end. |

The skill consumes this contract faithfully — it does not invent steps the starter's `AGENTS.md` doesn't list.

If a section is missing, see [Failure modes](#failure-modes) below.

## The flow

### Step 1: Locate the starter

In order of preference:

1. **CWD has `AGENTS.md`** — use it.
2. **CWD has subfolders containing `AGENTS.md`** — list them with their `## About` first paragraph and ask which.
3. **User mentioned a starter by name** (e.g. *"the gtm-for-infra starter"*) — find that folder, then verify `AGENTS.md` exists in it before continuing:

   ```bash
   STARTER=<folder>
   test -f "$STARTER/AGENTS.md" || echo "MISSING"
   ```

   If the file is missing, jump to [Failure modes](#failure-modes) — do **not** continue the flow.

4. **None of the above** — ask: *"which starter? Available: [list of starters with AGENTS.md found in repo]"*.

To find starters globally: `find . -maxdepth 3 -name AGENTS.md -not -path '*/.git/*' -not -path '*/skills/*'`.

### Step 2: Read AGENTS.md in full

Read the entire file before doing anything. The H2 sections form the contract you will execute. If the file references `../CLAUDE.md` for repo-wide conventions, read that too.

### Step 3: Route via First-contact onboarding

The `## First-contact onboarding` section enumerates branches (typically: demo / setup-for-own-data / just-exploring / editorial). Route by:

- **Explicit user intent** — if the user said *"demo me"*, *"set me up"*, *"just show me"*, *"I want to edit the schema"*, pick the matching branch and proceed without asking.
- **Ambiguous intent** — ask the user once, listing the branches verbatim from the file. If their answer is still vague, follow the documented default (typically branch 1).

Don't deviate from `AGENTS.md`'s branches. If the file lists three options, present three; don't add a fourth from your own knowledge.

### Step 4: Execute Prerequisites

Run every check in the `## Prerequisites` section. If any fails:

- Surface the failure with the exit code or stderr.
- Quote the remediation hint from the file (e.g. `brew install …`).
- Do **not** proceed to Bootstrap with failed prerequisites.

### Step 5: Execute Bootstrap (demo / setup branches only)

Run the fenced bash blocks in `## Bootstrap` in order, with these adjustments:

- **Path collision.** If the default `$REPO` path already exists with a different schema, ask the user before overwriting. Otherwise pick a fresh suffix (`-2`, `-3`, …) and update `$REPO` in every subsequent block.
- **Port collision.** Test with `lsof -nP -iTCP:$PORT -sTCP:LISTEN`. If bound, pick the next free port (default + 1, then + 2 …) and update `$PORT`, `$PIDFILE`, `$LOGFILE` consistently. The four variables move together.
- **`--uri` propagation.** If you picked a non-default port, ensure every subsequent `omnigraph read|change` includes `--uri http://127.0.0.1:$PORT`. The starter's AGENTS.md should already do this — verify, don't assume.
- **Background server.** Track the PID in `$PIDFILE` so `## Teardown` works at session end.

Confirm the server is reachable before running the Headline:

```bash
sleep 1
curl -s http://127.0.0.1:$PORT/healthz | head -c 200 || echo "server not responding on $PORT"
```

### Step 6: Execute Headline

Run the command(s) in `## Headline`. Show the actual terminal output to the user. Then narrate using the file's expected-output narration verbatim — don't add editorial flourishes the file didn't write.

If the actual output diverges from the expected output (e.g. row count differs, a row is missing), say so explicitly and stop. Do not blindly continue.

### Step 7: Present Follow-ups

List the `## Follow-ups` subsections as numbered options. Do not auto-execute any. Each follow-up runs only when the user picks it.

If you are running non-interactively (e.g. invoked from another agent or a script), list the follow-ups and stop. Do not pick a default — the launcher's job ends at the headline; follow-ups always require human (or upstream-caller) selection.

For each follow-up flagged with **"Ask before running"** (typically those that cost API credits or mutate persistent data), confirm scope before kicking off — even if the user already picked it. The cost of a second confirmation is one message; the cost of skipping it is a surprise bill.

#### Reusable pattern: external enrichment → graph patch

Some starters have follow-ups that call an external enrichment tool (Parallel CLI, a CSV enrichment job, a CRM export, etc.) and then merge the result into Omnigraph. In those cases, `AGENTS.md` should provide the domain-specific context: source rows, fields to enrich, target account identifiers, and the semantic intent for how the result should appear in the graph. This launcher owns the reusable Omnigraph mechanics.

Use a portable scratch directory, not a repo-specific hidden folder:

```bash
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/omnigraph-starter.XXXXXX")"
echo "$WORKDIR"
```

After the external tool has produced structured output, discover the graph contract from the running repo before writing any transform. Prefer the persisted schema over the checked-in schema because it is what the repo actually accepted:

```bash
omnigraph schema show "$REPO" > "$WORKDIR/accepted-schema.pg"
omnigraph snapshot --json "$REPO" > "$WORKDIR/snapshot.json"
omnigraph export "$REPO" > "$WORKDIR/sample.jsonl"
```

If the starter names specific relevant types, you may narrow the export to those types for readability:

```bash
omnigraph export --type Account --type ResearchRun --type Claim "$REPO" \
  > "$WORKDIR/provenance-sample.jsonl"
```

Write any one-off transformer into `$WORKDIR`, using whatever runtime is already available (`jq`, `node`, `ruby`, `python3`, `awk`, etc.). Do **not** add generated glue to tracked starter files unless the user explicitly asks to productize it.

The transformer must be derived from the accepted schema and sample export:

- Identify required node fields, edge names, and enum values from `accepted-schema.pg`.
- Use sample exported rows to match JSONL load shape: `{"type":"NodeType","data":{...}}` for nodes and `{"edge":"EdgeType","from":"...","to":"...","data":{...}}` for edges.
- Preserve the starter's semantic intent, but adapt to renamed node/edge types or required fields if the schema changed.
- Prefer stable IDs/slugs for repeatability with `load --mode merge`.
- Keep source input, transformed patch, schema snapshot, and scratch scripts in `$WORKDIR`.

Before merging, sanity-check the patch shape with cheap shell tools:

```bash
test -s "$PATCH"
sed -n '1,8p' "$PATCH"
```

Merge with `load --mode merge`, not overwrite:

```bash
omnigraph load --data "$PATCH" --mode merge "$REPO"
```

Then run the starter's documented verification read. If the follow-up does not name one, use the closest existing alias that proves the loaded data is reachable from the graph's primary entity. Show the actual output.

### Step 8: Apply Ask-the-user moments throughout

The `## Ask-the-user moments` section is a checklist. Apply it at every step:

- Before any follow-up flagged with "Ask before running."
- Before `--mode overwrite` against any path that isn't `/tmp/...`.
- Before editing `seed.jsonl` if the user said *"set this up for my own data"* — ask replace vs append.
- Before `omnigraph schema apply` without a successful prior `schema plan`.

If the file lists a moment you're about to trigger, **stop and ask**.

### Step 9: Teardown (offer at session end)

When the user is done, offer to run `## Teardown`. Don't run it unprompted — they may want the running server for further follow-ups.

## Failure modes

- **Starter has no `AGENTS.md`.** **Stop. Do not run Prerequisites, Bootstrap, or any `omnigraph` write command.** Tell the user the file is missing, and offer three options:
  - **(a)** Read-only walkthrough of the starter from its `README.md` — no server start, no data load.
  - **(b)** Author a new `AGENTS.md` for this starter based on its `README.md` and `omnigraph.yaml` aliases, using [`references/agents-md-contract.md`](./references/agents-md-contract.md) as the contract template. Produce a draft, ask the user to review, then re-enter Step 2 with the new file.
  - **(c)** Hand off to the `omnigraph-intel-bootstrap` skill if the user actually wants a *new* graph rather than to launch the shipped one.
- **Headline command fails.** Capture stderr. Check whether the server is reachable (`curl :PORT/healthz`). Check the `omnigraph load` output from Bootstrap for warnings. Don't blindly retry.
- **Prerequisite missing** (e.g. `omnigraph` binary not found). Show the install hint from the file. Do not try alternative installation methods the file didn't list.
- **First-contact branches don't fit the user's stated intent.** Ask the user to clarify. Don't invent a fifth branch.

## Authoring `AGENTS.md` for a new starter

If a starter you're launching doesn't have one — or if the user wants to add one to an existing starter — see [`references/agents-md-contract.md`](./references/agents-md-contract.md) for the full H2 contract and a worked example.

## Cold-testing a starter's `AGENTS.md`

The contract is only useful if a fresh agent can execute it without prior context. To verify a starter's `AGENTS.md`:

1. Spawn a subagent with no prior conversation context.
2. Tell it: *"follow `AGENTS.md` literally; do not read `README.md` or other files; report what worked and what was unclear."*
3. Test both clear intent (*"demo me"*) and ambiguous intent (*"help me with this folder"*).
4. Apply the friction the cold test surfaces.

This is the validation pattern used to harden `gtm-for-infra/AGENTS.md` — it caught silently-failing port instructions, broken prerequisite checks, and unclear branch routing before any user hit them.
