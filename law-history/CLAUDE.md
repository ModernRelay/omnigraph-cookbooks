# CLAUDE.md — law-history

Scoped guidance for the `law-history/` cookbook. Repo-wide conventions live in
`../CLAUDE.md`. For general OmniGraph operations use the **omnigraph** skill;
this file covers only what is specific to this cookbook.

## What This Is

Statutes as they stood on any date: each provision, the citations it has
carried, its words while in force, the changes that rewrote it, the judgments
that applied or invalidated it, and the official document behind each fact.
Which text applies on a date, what an old citation names today and whether a
court read text that has since changed are derived by stored queries on every
read, never stored. Schema, seed, queries, policies, an agent skill, two
scripts that fetch the seed's official documents and rebuild the seed from
them, and a read check through the Omnigraph Python client. The seed is real
United States federal law, in the public domain.

## Key Files

- `schema.pg` — 10 node types, 19 edge types.
- `queries/law.gq` — 25 stored reads, four of them checks that should return
  nothing.
- `queries/mutations.gq` — 4 stored writes for judgments and holdings.
- `seed.jsonl` / `seed.md` — reference seed. Keep them in sync; `seed.md`
  lists what each read must return on the fresh seed.
- `examples/mcconnell-source.jsonl` — the source row for the add-a-case
  walkthrough in `README.md`, which the checker also runs.
- `sources/documents.json` — every official document behind the seed and the
  example, pinned by URL, SHA-256 and fetch time.
- `sources/fetch.py` — downloads them into `sources/documents/` (ignored by
  git) and refuses any whose bytes differ from the pin.
- `sources/build_seed.py` — writes `seed.jsonl` and the example source from
  those documents, checking each text, date and holding against them;
  `--check` compares a fresh build with the committed files.
- `client/check_reads.py` — runs every stored read through the Omnigraph
  Python client (`client/requirements.txt`) against a served fresh seed and
  compares the rows with `seed.md`; the checker runs it. A new stored read
  needs a check there, or the script fails.
- `policies/graph.policy.yaml` — reader, writer, admin and `act-agent` roles.
- `skill/SKILL.md` — guidance for an agent answering from a law graph.

## Rules

- Graph id `law`. Stored queries and parameters:
  `omnigraph queries list --target local --graph law`.
- Every fact comes from an official document named by a `Source` row with its
  URL, fetch time and sha256. Never write statutory text, a date or a holding
  from memory or from a secondary source. `versions_without_source` and
  `changes_without_source` must return nothing.
- A provision's identity is its slug; its numbers are `Designation` rows with
  validity intervals. Never put a section number in a `Provision` slug's
  meaning or rename a slug when a law renumbers.
- Text versions of one provision never overlap (`overlapping_versions`). Open
  intervals end on `9999-12-31`; nulls would drop rows from every date
  comparison.
- `TextVersion.text` omits the unit's own label, uses straight quotes and drops
  the codifier's footnote markers. `text_sha256` is the SHA-256 of that text,
  so equal hashes mean equal words.
- Do not store derived status: no "current", "repealed", "renumbered" or
  "good law" flags. Extend a query instead.
- `HeldInvalid` is keyed by judgment and provision. Agents write
  `propose_holding` (`ai_proposed`); only a person runs `confirm_holding`. The
  holding is the court's exact words with a pinpoint `locator`.
- `act-agent` writes only on unprotected branches and cannot merge, publish or
  delete a branch. The shared checker asserts this; do not widen the agent
  rules.
- `seed.jsonl` and `examples/mcconnell-source.jsonl` are generated. Never edit
  them by hand: change `sources/build_seed.py`, add any new document to
  `sources/documents.json`, run `sources/fetch.py`, rebuild, and confirm with
  `sources/build_seed.py --check`. Never update a pinned SHA-256 to make a
  refused document pass; a publisher that changed a document is a new source
  to read and record.
- After a schema, query or seed change, update `seed.md` and the matching
  checks in `client/check_reads.py`, then run
  `../scripts/check-cookbooks.py law-history` with a Python that has
  `client/requirements.txt` installed.
