# Law history: statutes as they stood on any date

One typed graph for the history of a body of law: each provision, the citations
it has carried, its words while they were in force, every change that rewrote
it, the judgments that applied or invalidated it, and the official document
behind each fact. Graph ID `law`.

A legal question usually comes with a date: the words in force when a contract
was signed or a case was filed, which are not always the words in force today,
and they are hard to get right. Laws are renumbered, so an old citation names nothing until you
translate it. A court can strike down a provision that the code keeps printing.
A later law can reach back and govern cases filed before it existed. An agent
answering from memory gets these wrong while sounding certain. Here each answer
is a stored query over recorded text, dates and holdings, with the source
document for every row and an explicit record of what the graph does not cover.

The seed is real United States federal law, in the public domain; see
[seed.md](seed.md). It follows the corporate expenditure ban, FECA § 316
(2 U.S.C. § 441b, now 52 U.S.C. § 30118), through its 2002 amendment, its
2014 renumbering and *Citizens United*, and the Subchapter V "debtor"
definition, 11 U.S.C. § 1182(1), through five versions in five years.

This is a data model and a set of queries, not legal advice. The seed covers
two provisions, not a jurisdiction.

## Quick start

Use the shared [local setup](../README.md#local-setup) with folder
`law-history` and graph `law`, and load `seed.jsonl`. Its four targets are the
roles used below: `local` (admin), `local-writer` for legal editors,
`local-reader`, and `local-agent` for an AI agent. With the server and gateway
up:

```bash
omnigraph query text_on --target local-reader --graph law \
  --params '{"label":"11 U.S.C. § 1182(1)","on":"2022-05-01"}'
omnigraph query later_law_reaching_back --target local-reader --graph law \
  --params '{"label":"11 U.S.C. § 1182(1)","event_on":"2022-05-01"}'
```

On 1 May 2022 a Subchapter V debtor had to be a "small business debtor": the
CARES Act's higher debt limit had lapsed on 27 March. The second read shows why
that is not the whole answer. Pub. L. 117-151, in force on 21 June 2022,
restored the higher limit for cases commenced from 27 March 2020 that were
still pending, so a case filed on 1 May 2022 may be governed by text that did
not exist on the day it was filed.

Merge the `aliases:` of [`omnigraph-config.example.yaml`](omnigraph-config.example.yaml)
into `$OMNIGRAPH_HOME/config.yaml` for a short name per read, such as
`omnigraph alias coverage` or
`omnigraph alias cited-as --params '{"label":"2 U.S.C. § 441b(a)","on":"2026-10-31"}'`.

## Model

[`schema.pg`](schema.pg) has 10 node types and 19 edge types.

| Area | Types | Holds |
|---|---|---|
| Law | `Jurisdiction`, `Instrument`, `Provision`, `Designation` | Acts, code titles and codifiers' reclassifications; the units of law; the numbers each unit has carried |
| Text | `TextVersion`, `Change`, `DefinedTerm` | The words of a unit while in force; each instruction that rewrote them; the terms they define and use |
| Courts | `Judgment` | Decisions, the text each one read and what each held invalid |
| Provenance | `Source`, `Coverage` | The official documents, with URL, fetch time, hash and reuse terms; what the graph records of each provision |

The design rests on a few separations:

- **A provision is not its number.** `Provision` is the unit of law; its key
  never changes. Its numbers are `Designation` rows, each valid for an interval
  and marked as a code citation or the enacting act's own. A renumbering ends
  one designation and starts another, and every read accepts any number the
  provision has carried.
- **Two kinds of time.** When text was in force, and which events a change
  governs, are data: `in_force_from` / `in_force_to` on `TextVersion`,
  `in_force_on` and `applies_from_event` on `Change`. When the graph learned
  something is its commit history: a correction is a new commit, and any read
  can run against an earlier snapshot with `--snapshot`.
- **Every date has its reason.** A change stores the law's instruction, the
  date it took force and `in_force_basis`, the law's words for that date. When
  a change reaches events before it took force, `applies_text` quotes the rule.
- **How far each version is verified.** `verification` on a change says
  whether an official edition prints its result (`official_version`) or the
  graph has it only from the law's own words (`law_text`).
- **A holding is not a text change.** A court's decision leaves the printed
  text alone. `HeldInvalid` records the court's words, the page and the scope
  (`facial`, `as_applied`, `in_part`) on the narrowest provision they reach,
  and `review_status` says whether a person has checked it.
- **What is missing is stated.** `Coverage` gives each provision's recorded
  period and method. A date outside it means the graph does not know, not
  that there was no law.

Open intervals end on `9999-12-31`, so every date range is two plain
comparisons.

### Derived, not stored

| Question | Stored query |
|---|---|
| What did this citation say on a date? | `text_on`, `versions`, `version_sources` |
| Does a later law govern this past event? | `later_law_reaching_back` |
| What changed this provision, and when? | `changes_to`, `changes_between` |
| What is this old citation called now? | `cited_as_on`, `citations`, `renumberings` |
| What does this text cite, under today's numbers? | `citations_from` |
| Has a court held it invalid? | `held_invalid`, `held_invalid_enclosing` |
| Which cases read this text, and was it the text in force today? | `judgments_applying`, `precedents_on_changed_text` |
| Does a later holding undercut this precedent's text? | `later_invalidations` |
| What does a change to this definition touch? | `definition_reach`, `term_users` |
| Where do these words appear? | `search_text` |
| What is behind the graph, and what does it cover? | `laws`, `sources`, `coverage` |
| Is the record consistent? | `overlapping_versions`, `versions_without_source`, `changes_without_source` (each should return nothing), `holdings_to_review` |

`omnigraph queries list --target local --graph law` prints all 25 reads and 4
mutations with their parameters.

## Workflows

### Which text governed an event

Ask for the text in force on the event's date, then for later law that reaches
back to it:

```bash
omnigraph query text_on --target local-reader --graph law \
  --params '{"label":"11 U.S.C. § 1182(1)","on":"2022-05-01"}' --json
omnigraph query later_law_reaching_back --target local-reader --graph law \
  --params '{"label":"11 U.S.C. § 1182(1)","event_on":"2022-05-01"}' --json
```

Each `text_on` row carries the provision's coverage. When the date falls after
`covered_to`, the row is the last version the graph recorded and a later change
may be missing; an empty result means no text was in force under that citation
on that date or the date is outside the record. `later_law_reaching_back`
returns each change with its `applies_text`: the conditions, such as "pending on
the date of enactment", are for the reader to apply to the facts.

### Following an old citation

A brief from 2010 cites 2 U.S.C. § 441b(a). Today that number names nothing:

```bash
omnigraph query cited_as_on --target local-reader --graph law \
  --params '{"label":"2 U.S.C. § 441b(a)","on":"2026-10-31"}'
```

returns `52 U.S.C. § 30118(a)` and the act's own number, `FECA § 316(a)`.
`citations` lists every number the provision has carried with its dates;
`citations_from` shows that the 2006 text's "section 431 of this title" is
today's 52 U.S.C. § 30101. `positive_law` on a code designation says whether
the code's text is the law itself (Title 11) or evidence of it, with the act
governing (Titles 2 and 52).

### Is the text still good law

Run both court reads. A holding on a section reaches its subsections, and the
code still prints what a court struck:

```bash
omnigraph query held_invalid --target local-reader --graph law --params '{"label":"52 U.S.C. § 30118(a)"}'
omnigraph query held_invalid_enclosing --target local-reader --graph law --params '{"label":"52 U.S.C. § 30118(a)"}'
```

The first returns nothing; the second returns *Citizens United*'s holding on
the section, with the court's words and page. `precedents_on_changed_text`
finds cases that read words no longer in force, and `later_invalidations` finds
later holdings against the text a given case applied. The graph records
holdings, not every way one case treats another, so it is not a citator.

### Adding a case

Judgments, the text they read and what they held are judgments about the law,
so they reach `main` through review. An agent records them on its own branch;
an editor checks them against the opinion, merges and confirms.

*McConnell v. FEC*, 540 U.S. 93 (2003), upheld BCRA § 203's extension of the
corporate ban, and *Citizens United* overruled that part. Record the opinion's
source first, then the case and the text it read, then propose the holding:

```bash
omnigraph load --target local-agent --graph law --branch agent-mcconnell --from main \
  --data examples/mcconnell-source.jsonl --mode append
omnigraph mutate record_judgment --target local-agent --graph law --branch agent-mcconnell --params '{
  "slug":"jud-mcconnell","title":"McConnell v. Federal Election Commission",
  "court":"Supreme Court of the United States","citation":"540 U.S. 93","docket":"No. 02-1674",
  "decided_on":"2003-12-10","source":"src-us-reports-540-93"}'
omnigraph mutate record_applied --target local-agent --graph law --branch agent-mcconnell \
  --params '{"judgment":"jud-mcconnell","version":"tv-feca-316-b-2-2"}'
cat > holding.json <<'EOF'
{"judgment":"jud-citizens-united","provision":"prov-feca-316-b-2","scope":"in_part",
 "holding":"Given our conclusion we are further required to overrule the part of McConnell that upheld BCRA § 203's extension of § 441b's restrictions on corporate independent expenditures.",
 "locator":"558 U.S. at 365","effective_from":"2010-01-21"}
EOF
omnigraph mutate propose_holding --target local-agent --graph law --branch agent-mcconnell --params-file holding.json
```

`record_applied` takes the version `text_on` returns for the decision date.
The holding goes on paragraph (b)(2), which § 203 amended, not on the whole
section. `propose_holding` writes it as `ai_proposed`, and
`holdings_to_review --branch agent-mcconnell` lists it.

The editor reviews the branch, merges it and confirms the holding with the same
fields, corrected where the proposal was wrong:

```bash
omnigraph branch diff agent-mcconnell --target local-writer --graph law
omnigraph branch merge agent-mcconnell --into main --target local-writer --graph law
omnigraph mutate confirm_holding --target local-writer --graph law --params-file holding.json
omnigraph branch delete agent-mcconnell --target local-writer --graph law --yes
```

`HeldInvalid` is keyed by judgment and provision, so the confirmation replaces
the proposal rather than adding a second row. `later_invalidations` for
`540 U.S. 93` now returns *Citizens United*. [seed.md](seed.md#after-the-add-a-case-walkthrough)
lists the results. The agent's own writes on `main` are refused, as are its
merge and branch deletion.

### Adding text and changes

Text versions, changes and designations come in batches from official sources,
with one `Source` row per document. Load a batch on a branch, run the checks
against it, and merge:

```bash
omnigraph load --target local-writer --graph law --branch add-title-11-2025 --from main \
  --data batch.jsonl --mode merge
omnigraph query overlapping_versions --target local-reader --graph law --branch add-title-11-2025
omnigraph query versions_without_source --target local-reader --graph law --branch add-title-11-2025
omnigraph branch merge add-title-11-2025 --into main --target local-writer --graph law
```

When a version replaces an open one, the batch closes the old row's
`in_force_to` and adds the new version, the `Change` with its `ChangedFrom` and
`ChangedTo` edges, and its evidence; extend the provision's `Coverage` to the
new edition's `current_through`. `merge` mode upserts by key, so the closed row
is replaced in place. Use `--as-commit` on the merge to run the checks against
the exact merged result before publishing it, as in the
[hardware-program review gate](../hardware-program/README.md#check-the-merged-result-before-publishing).

### Rebuilding the seed from its sources

The seed is built by a script, not typed. `sources/documents.json` pins the 22
official documents behind it, the seed's 21 and the *McConnell* report, by URL
and SHA-256. `sources/fetch.py` downloads them and refuses any document whose
bytes no longer match its pin. `sources/build_seed.py` reads only those bytes,
checks each text, date and holding against them, and writes `seed.jsonl` and
`examples/mcconnell-source.jsonl`. The same documents give the same files, byte
for byte:

```bash
python3 sources/fetch.py
python3 sources/build_seed.py --check
```

Both scripts use only the Python standard library; the checks on the two court
reports also need `pdftotext` from poppler. A refused document means its
publisher now serves different bytes. Read the new version and, if it still
supports the seed, pin it as a new source with its own hash and fetch time;
never change a pin to make a refused document pass.

### Agents

The graph policy gives an AI agent its own actor, `act-agent`. It reads
everything and invokes stored queries, but it writes only on unprotected
branches and cannot merge, publish or delete a branch, so every agent change
reaches `main` through an editor:

```bash
omnigraph access --target local-agent --graph law --branch main
```

An agent host such as Claude Code or Codex can reach the same reads over MCP.
`omnigraph mcp` relays the agent's MCP over stdio to the server through a
registered target, so the token never enters the agent's configuration:

```json
{"command": "omnigraph", "args": ["mcp", "--target", "local-agent", "--graph", "law"],
 "env": {"OMNIGRAPH_HOME": "/Users/you/.omnigraph-cookbooks", "OG_LOCAL_AGENT_TOKEN": "local-agent-token"}}
```

[`skill/SKILL.md`](skill/SKILL.md) is a skill for such an agent: always ask for
a date, check coverage, report the verification and the reach-back rules, run
both court reads, cite the sources, and never write statutory text from memory.
The policy cannot limit which stored queries an agent runs, so before merging
an agent's branch, check its commits for a `confirm_holding` by `act-agent`.

### Reacting to changes

The change feed reports every committed row change. An agent can follow it and
re-check what it has told people when text or holdings move:

```bash
omnigraph changes poll --target local-agent --graph law --start after:<COMMIT_ID> \
  --type TextVersion --type Change --type Judgment --json
```

Keep the returned cursor and pass it back with `--cursor` on the next poll.

## Limits

- The seed holds two provisions of US federal law, not a code. Subsection
  (a) and paragraph (b)(2) are the only parts of § 316 with text.
- The record starts at the 2000 edition. `from_is_record_start: true` marks a
  version whose start date is the start of the record, not of the words.
- Annual editions miss text that was in force only between them. Such a
  version comes from the law's own words and its change says `law_text`.
- The graph records holdings that a provision is invalid. It does not record
  how cases treat each other (followed, distinguished, overruled), so it does
  not replace a citator.
- Agency rules, state law and other jurisdictions fit the model
  (`Jurisdiction.level`, `Instrument.kind`) but are not in the seed.

## Extending

- Add `Overrules: Judgment -> Judgment` with the court's words, to record
  treatment between cases alongside holdings on provisions.
- Add regulations as `Instrument` rows with their own designations (C.F.R.
  sections), and an `Implements` edge to the statute they carry out.
- Record a statute's legislative history as `Source` rows linked to the
  `Change` they explain.
- Add a state code as a `subnational` jurisdiction `WithinJurisdiction` of the
  United States.

Change the schema with `cluster plan` and `cluster apply` against the running
server, as in [live updates](../README.md#live-updates).
