# CLAUDE.md — company-brain

Scoped guidance for the `company-brain/` cookbook. Repo-wide conventions live
in `../CLAUDE.md`. For general OmniGraph operations use the **omnigraph** skill;
this file covers only what is specific to the company brain.

## What This Is

The shared context of one company: people, teams, projects, the meetings,
threads and documents the brain learned from, and the decisions and action
items extracted from them. Agents propose on branches; people accept and
merge. The seed is a fictional company, "Lanternworks"; all names are made up.

## Key Files

- `schema.pg` — 8 node types (`Person`, `Identity`, `Agent`, `Team`,
  `Project`, `Source`, `Decision`, `ActionItem`), 16 edge types.
- `queries/decisions.gq`, `queries/people.gq`, `queries/actions.gq` — reads.
- `queries/hygiene.gq` — reads that must return zero rows; run them on a
  branch before merging it.
- `queries/mutations.gq` — stored writes.
- `seed.jsonl` / `seed.md` — 46 nodes and 92 edges. Keep them in sync;
  `seed.md` lists what each read returns.

## Rules

- Graph id `knowledge`. Stored queries and parameters:
  `omnigraph queries list --cluster . --graph knowledge`.
- Write facts with the stored mutations, not raw inserts: `propose_decision`,
  `propose_successor` and `add_action_item` write the fact and the edge to its
  `Source` in one commit. `@card(1..)` on `DecidedIn` does not stop an insert
  without a citation; `uncited_decisions` catches one.
- Never edit a decision's `statement`. Change a decision with
  `propose_successor`. Do not add a stored `superseded` or `current` status;
  both are derived from `SupersededBy`. `omnigraph lint` warns that no update
  sets `decided_at` or `rationale`; that is intended.
- Agents write `status: proposed` on their own branch. Only a person runs
  `accept_decision` or `reject_decision` and merges.
- Resolve identifiers before creating a person: run `person_by_identity` for
  every identifier the source gives, and create a `Person` only when none
  resolves. Identity slugs are `<system>:<value>`, lowercased.
- Source slugs are `<system>:<native id>` (`meet:…`, `slack:<channel>/<ts>`,
  `doc:…`, `ticket:…`), so ingesting the same item twice upserts.
- Use fixed dates in reads that compare to a date (`overdue_actions`,
  `quiet_projects`) and in the seed.
- Keys and cardinalities are fixed at creation. Before adding a type, decide
  its key and any `@card`; add properties as nullable.
