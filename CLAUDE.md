# Cookbook agent guide

Read this file and the cookbook's own `CLAUDE.md` before editing. `AGENTS.md`
links to the corresponding `CLAUDE.md`; edit the target once.

## Scope and sources

These are eight self-contained OmniGraph **0.15.0** bundles: schemas, seed data,
stored queries and applied policies. The only application code is the beads
cookbook's `ob` client in `beads/client/`, with its own tests, and the local
HTTPS gateway `scripts/local-tls-gateway.py`. The root
[README](README.md) owns setup, live updates and upgrades; individual cookbook
guides own their domain model and worked queries.

| Folder | Graph ID |
|---|---|
| `industry-intel` | `spike` |
| `pharma-intel` | `pharma` |
| `second-brain` | `brain` |
| `vc-os` | `vcos` |
| `dev-graph` | `dev` |
| `beads` | `beads` |
| `company-brain` | `company` |
| `hardware-program` | `program` |

The graph ID is the key in `cluster.yaml`, not the folder name. Configurations
omit `storage`, so local roots default to their directory. Explicit storage
belongs in the deployment configuration. Never commit graph or ledger state.

The **omnigraph** skill owns command and language detail, and this repository
does not carry a copy of it. It ships inside the CLI, so the copy that matches
the binary you are running comes from that binary: `omnigraph skill export
~/.claude/skills/omnigraph --force` installs it, and `omnigraph skill show
references/<file>.md` prints one file without installing anything. Its source
of truth is `skills/omnigraph` in
[ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph). Read it
before a schema change, a bulk load or a retry after an uncertain write.

## Changes and validation

- Run `python3 scripts/check-cookbooks.py` for all eight local journeys, or
  name cookbooks to run only those. It uses the released CLI/server, isolated
  operator homes, disposable roots and the local HTTPS gateway; it never
  touches a deployed graph. For beads the checker also drives the `ob`
  client against the served graph; the client's local tests run with
  `python3 -m unittest discover -s beads/client/tests`.
- For a query edit, start with `omnigraph lint --schema schema.pg --query
  queries/<file>.gq`. This is an offline check. Comments in `.pg`/`.gq` use `//`.
- Keep `seed.md` and `seed.jsonl` consistent. Preserve the domain examples and
  required-field/edge constraints. A keyed node or unique edge must not repeat
  within one seed batch.
- New cookbooks ship schema, queries, seed, role policies, `cluster.yaml`,
  operator alias examples, short domain guidance and a `site.json` (see
  [The website](README.md#the-website)). Add their local journey to the
  existing checker rather than creating a second harness.
- `site.json` is the copy omnigraph.dev shows; its questions name stored read
  queries. Renaming or removing a query means updating the question in the
  same change; `check-cookbooks.py --site` catches a miss offline. Its search
  keywords come from the market vocabulary in ModernRelay's mr-ops graph:
  change them there first.
- Write a cookbook README from the template in
  [Writing a cookbook README](#writing-a-cookbook-readme). The same check
  covers it offline once its `site.json` names a `use_case`.
- Update user instructions in the same change as a command or behavior. Prefer
  a link to an existing owner over copying another lifecycle walkthrough.

## Writing a cookbook README

A cookbook README is the landing page of OmniGraph for one use case. It tells
an engineer in that field what they get: a living source of truth for the
people and agents doing the work, and the agent workflows that run around it.
It is not a manual. Commands, roles and step-by-step workflows go in the
cookbook's own `AGENTS.md`.

[hardware-program/README.md](hardware-program/README.md) and
[company-brain/README.md](company-brain/README.md) are the worked examples. A cookbook whose `site.json` names a `use_case` is held to this
structure by `check-cookbooks.py --site`; the others move over one at a time.

### Before you write

- Read the cookbook's `schema.pg`, `queries/*.gq` and `seed.md`. Every claim in
  the README has to be something these files do.
- Read the use case in ModernRelay's mr-ops graph: its `UseCase`, the `Need`s
  it meets, the `Capability`s it uses and the `Keyword`s that name it. The
  slugs go in `site.json`; the wording informs the intro.
- Read how the best product in that field describes itself, for its
  vocabulary and for the tools it integrates with. For hardware-program that
  was Flow Engineering's product pages. Take the field's words, not the
  product's claims.

### Working out the workflows

Do not start from the stored queries and ask what could be done with them.
Start from the work. A workflow around a living record is a loop with five
parts: what starts it, what the agent reads, what it does, where a person
decides, and how the record shows it happened. Ask these questions about the
use case, and each answer is a workflow:

| Kind | Ask | Example |
|---|---|---|
| Capture: the world changes, the record learns | What happens outside that the record has to know about, and in which tool does it happen? | A meeting ends; a mass changes in CAD; a test run finishes |
| Check: the record changes, something in it may no longer hold | What can go wrong, go stale or contradict when something changes? | A pass predates its requirement; a decision rests on a disputed claim |
| Act: the record is in a state, someone outside has to know or do something | Who has to know or act when this state appears, and where do they work? | An action item is overdue, so its owner is reminded; a review is blocked, so the board gets the list |

Look for all three kinds. A cookbook that only has checks is a linter, and one
that only captures is a log. The acting workflows are what make the record
part of the work: they take an action outside the record, such as a message, a
ticket or a report, from what the record says.

For each workflow, say what starts it and name the stored queries it reads or
writes. Then be exact about review:

- What an agent writes to the record waits on a branch for a person.
- What an agent does outside the record is not held back by the record. The
  policy cannot stop a message being sent. Say so, keep these workflows to
  notifying and drafting unless a person approves the action, and say that the
  agent uses its own tools for it where the cookbook has no integration.
- Say how a repeat is avoided: what in the record shows the action was taken.
  If the schema has no place for that, say it or add one.

### The template

````markdown
# <Use case>: <what it covers>

Build a living <what the use case keeps>, and the agent workflows around it.
<What it keeps linked, in the field's words.> <Why it stays current.> <What
agents do, and that a person reviews it.>

<The problem in two sentences: where the data lives today and what goes wrong.>
This cookbook sets OmniGraph up as <the one place it is held>.

- **<Benefit>.** <One sentence.>
- **<Benefit>.** <One sentence.>
- **<Benefit>.** <One sentence.>

> If you are an agent: the commands, roles and workflows are in
> [AGENTS.md](AGENTS.md). Read that file before running anything.

## The data model

<One sentence naming what the ontology covers.>

```mermaid
graph LR
  <Type> -- <link in plain words> --> <Type>
```

| Area | Types | Holds |
|---|---|---|
| <Area> | `<Type>`, `<Type>` | <What they hold> |

- **<Modelling choice>.** <What it is and why it matters, in one or two sentences.>

## Branching and merging

<One or two sentences: a change is made on a branch and the baseline moves on merge.>

- **<What a branch is used for here, by people or by agents>.** <One or two sentences.>

## Agents and workflows

<One sentence: what agents do and what stays with people.>

| Kind | Workflow | What it does | Stored queries |
|---|---|---|---|
| Capture | <Name> | <What it records, and from where> | `<stored_query>` |
| Check | <Name> | <What it looks for when the record changes> | `<stored_query>`, `<stored_query>` |
| Act | <Name> | <Who it tells or what it does outside, from which state> | `<stored_query>` |

<The parts every workflow has, numbered: what starts it, what the agent reads,
what it does, where a person decides.>

- **<What an agent may not do in the record>.** <One sentence.>
- **<What the record does not hold back>.** <Outside actions, and how to limit them.>
- **Bring your own agent.** <How it connects, and the skill if the cookbook has one.>

## Data sources

<One sentence: the record connects the tools; each tool stays the authority for its data.>

| Source | Examples | Feeds |
|---|---|---|
| <Kind of tool> | <Named products> | `<Type>`, `<Type>` |

<Say plainly whether the cookbook includes connectors, and how a sync writes to the record.>

## Questions you can ask

<One sentence: each is answered from the current data by a stored query.>

| Question | Stored query |
|---|---|
| <The question, word for word as in site.json> | `<stored_query>` |

## Sample data

<What the seed depicts, with its size.> On a fresh load, the questions above return:

- <One result per question, with its numbers.>

[seed.md](seed.md) describes it and lists what every stored read returns.

## Run it

Paste this prompt into a coding agent such as Claude Code or Codex:

```text
Read https://www.omnigraph.dev/onboarding.md and set up Omnigraph for me with the <name> cookbook: https://github.com/ModernRelay/omnigraph-cookbooks/tree/main/<folder>
```

To do it by hand, follow the shared [local setup](../README.md#local-setup)
using folder `<folder>` and Graph ID `<graph>`. [AGENTS.md](AGENTS.md) has the
exact command for each question and workflow on this page.
````

### Section by section

| Section | Write | The check holds you to |
|---|---|---|
| Title and intro | The opening sentence as in the template, where X is what the use case keeps: a system of record for a hardware program, a company brain. Then the problem and three benefits | That opening; the first paragraph equal to `about` in `site.json`; a link to `AGENTS.md` |
| The data model | The ontology of this use case, drawn, then the type table and the few modelling choices that matter. Say what OmniGraph provides, such as object storage, only where this use case has its own reason for it | Every backticked type exists in `schema.pg` |
| Branching and merging | What a branch is used for in this use case, by people or by agents. In some, engineers branch for change requests; in others only agents do | Not empty |
| Agents and workflows | The workflows by name and kind (capture, check, act), worked out as in "Working out the workflows", each with the stored queries behind it, reads and writes alike. Then what an agent may not do, and what the record does not hold back | Names stored queries, and only ones the cookbook has |
| Data sources | The tools a team brings data in from, by product name, and the types each feeds | Every backticked type exists in `schema.pg` |
| Questions you can ask | The questions `site.json` features, three to five. Feature only questions the sample data answers. One that is rightly empty on a fresh load, such as a check that finds nothing wrong, belongs in the workflow table | Each listed word for word on a line with its query; each returns rows on the seed |
| Sample data | What the seed depicts and what the questions return on it | A link to `seed.md` |
| Run it | The prompt, and where the commands are | Links to local setup and `AGENTS.md`; the Graph ID |

No other `##` is allowed. `README_SECTIONS` in `scripts/check-cookbooks.py` is
the list the check uses; change the two together.

### How to write it

- Use the field's vocabulary first and OmniGraph's second. Say "design
  review", "baseline" and "impact analysis" before "schema", "stored query" or
  "MCP".
- Write short sentences that say who does what and when. Prefer "an engineer
  reviews the branch and merges it" to a noun phrase.
- Use short labelled points, where the label names a feature. Do not write
  slogans or taglines.
- Keep the sample data in its own section. Every other section has to make
  sense to a reader who has not looked at the seed, so numbers from the seed
  go only there.
- Claim only what the cookbook does. If it has no connectors, no automatic
  sync or no enforced approval, do not imply them; say what is there.
- Name data sources by product, as tools a team brings data in from. This is
  what people search for.
- Keep it to about 200 lines.

### What goes with it

- `site.json`: `about` is the README's first paragraph. `use_case`, `needs`
  and `capabilities` carry the mr-ops slugs, and each need and capability
  names in `shown_in` the README heading that shows it. List a need only if
  mr-ops links it to the use case and the cookbook shows it. List a capability
  if mr-ops links it to the use case or to one of those needs. Where the
  cookbook shows something mr-ops does not link, add the link in mr-ops first.
  A question whose query takes parameters gives them in `params`.
- The cookbook's `AGENTS.md`: how to run it, the command for each question,
  each workflow step by step, the detailed modelling rules, and what the
  cookbook does not do.
- Run `python3 scripts/check-cookbooks.py --site` until it passes. The full
  run also runs each question against the seed.

## Operational rules

Use [local setup](README.md#local-setup) for fresh roots. Fresh
`cluster apply --target . --config .` creates the ledger; no separate import is
needed. Direct apply retains exclusive admission after exit; a server releases
it on a clean shutdown. Only clear an exact lock after its owner and accepted
I/O have stopped. Never automatically force-unlock or edit the ledger; never
direct-apply while serving.

The 0.15 CLI selects destinations with `--target` and source folders with
`--config`; it sends tokens only over HTTPS, which is why local setup puts the
gateway in front of the server. Use `cluster plan/apply --target NAME --config
DIR` for live schema, query, policy and provider changes. Review deletions:
omitting a graph permanently purges its managed root and history. Schema changes
need only `main` live. Adoption, missing-root recreation and out-of-band schema
changes are refused.

All bundles include `act-admin`, `act-writer`, `act-reader` role policies.
company-brain and hardware-program add `act-agent` (company-brain also named
agents), which write only on unprotected branches and cannot merge or delete
branches. Static actor-to-token JSON remains supported. `omnigraph access
--target NAME --graph ID --branch B` reports what a target's role may do. The
bearer token selects the trusted actor; a query's `$actor` is merely application
provenance. `config_manage` authorizes live deployment, and schema changes also
need graph `schema_apply`. Do not expand roles or change a running cluster
without task authorization.

Query the live graph to answer questions; seed files are load inputs. Discover
stored names and parameters with `omnigraph queries list --target NAME --graph
ID`. Aliases take parameters by name with `--params` and are read-only.
Mutations use `omnigraph mutate`; ad-hoc source uses `-e` or `--query`, never
the name slot. Parameterize values and supply every required field.

Use `load --mode append` once on an empty graph. `merge` upserts; `overwrite`
replaces the types present in the batch. Review larger writes on a branch, keep
the exact receipt and verify the effect; `branch diff` and `branch merge
--dry-run` show a branch's change and its merge before publishing. A failed
write's `disposition.effects` says whether it changed anything; a timeout or
`unknown` has an unknown outcome, so inspect before replay. Deployment status
is observed by its original ID.

`@embed` does not generate vectors during load. Prepare JSONL with the offline
embedding pipeline; query-time providers must match its model and dimensions.
Full-text calls (`bm25`, `fuzzy`, `match_text`, ...) need the property declared
`@index`.
Never claim empty semantic results prove there are no matching facts without
checking vector coverage: a ranked read answers a `ranking` object, and
`exhaustive: false` means the search left vector partitions unsearched, so a
nearer row may exist. Rows written on a branch are not covered by the graph's
indexes, so a read over them scans; `index build --branch B` covers them and
`optimize` covers only `main`. Both address the storage root directly and
refuse a server target with `target_incompatible`, so a served cookbook builds
a branch's indexes with its server stopped.
