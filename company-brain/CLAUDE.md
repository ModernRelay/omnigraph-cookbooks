# CLAUDE.md — company-brain

Scoped guidance for the `company-brain/` cookbook. Repo-wide conventions live
in `../CLAUDE.md`. For general OmniGraph operations use the **omnigraph** skill;
this file covers only what is specific to the company brain.

## What This Is

The shared context of one company: people, teams, projects, the meetings,
threads and documents the brain learned from, the claims people made in them,
and the decisions and action items promoted from those claims. Agents extract
and propose on branches; people verify, accept and merge. The seed is a
fictional company, "Lanternworks"; all names are made up.

## Key Files

- `schema.pg` — 8 node types (`Person`, `Actor`, `Team`, `Project`, `Source`,
  `Claim`, `Decision`, `ActionItem`), 18 edge types.
- `queries/claims.gq`, `queries/decisions.gq`, `queries/people.gq`,
  `queries/actions.gq` — reads.
- `queries/hygiene.gq` — reads that must return zero rows; run them on a
  branch before merging it with `omnigraph query <name> --branch …`. The
  `lint-*` aliases read main only.
- `queries/mutations.gq` — stored writes.
- `seed.jsonl` / `seed.md` — 55 nodes and 114 edges. Keep them in sync;
  `seed.md` lists what each read returns.

## Rules

- Graph id `company`. Stored queries and parameters:
  `omnigraph queries list --target local --graph company`.
- Two steps, never one. Record what a source says with `record_claim`
  (verbatim `quote`, `locator`, speaker); it starts `unverified`. Check new
  claims against main (`decision_evidence`, `mark_contradiction`,
  `decisions_at_risk`) before promoting them with `promote_claim`,
  `propose_successor` or `add_action_item`.
- Write facts with the stored mutations, not raw inserts: they write the fact
  and the edge to what it rests on in one commit. `@card(1..)` on `BasedOn`
  and `ClaimFrom` does not stop an insert without one; `unsupported_decisions`
  and `claims_without_source` catch it.
- Creates refuse an existing slug. Inserting a keyed node replaces the whole
  row, so `ClaimFrom`, `DecisionAbout`, `AssignedTo` and `ActsFor` are
  unkeyed and capped at one: `record_claim`, `promote_claim`,
  `propose_successor`, `add_action_item` and `add_actor` on a slug that
  exists fail with a `@card` violation and write nothing. Keep those four
  edges unkeyed; pick a new slug on refusal. `add_person` has no edge to
  guard with: run it only when `person_by_handle` resolves nobody.
- Every claim has a speaker: `ClaimedBy` is `@card(1..1)` and `record_claim`
  requires one. A raw load without it shows up in `claims_without_speaker`.
- Never edit a claim's `quote` or `statement`, or a decision's `statement`.
  Reject the claim and record a new one; change a decision with
  `propose_successor`, which needs a claim and a reason. Do not store
  `current`, `superseded` or `contested`; they are derived from
  `SupersededBy` and `Contradicts`. An accepted or deprecated successor
  replaces a decision; a rejected one does not, and `withdraw_successor`
  (after `reject_decision`) frees the original's single `SupersededBy` slot.
  `omnigraph lint` warns that no update sets `Claim.locator`, `decided_at`,
  `rationale` or `Actor.purpose`; that is intended. An agent whose job
  changes gets a new actor id, so history says which job wrote what.
- Point `Contradicts` from the newer claim to the older one. Leave both until
  a person rejects one.
- Agents create on a branch; they cannot write main, merge or delete a
  branch. A person reviews the branch's commits, merges it, then runs
  `verify_claim`, `reject_claim`, `accept_decision` or `reject_decision` on
  main. The policy cannot stop an agent writing on another agent's branch or
  running those four there (`invoke_query` covers the whole catalog), so
  before merging, check that no agent commit updated a Claim, Decision or
  ActionItem (README, "Agents extract, people decide"). Accept only decisions
  whose claims are verified (`accepted_on_unverified` must return zero rows).
- A Person is anyone in the real world; an Actor is an OmniGraph actor id that
  reads or writes, linked to its person with `ActsFor`. Resolve every handle
  with `person_by_handle` before creating a person. Handles (`email`,
  `slack`, `github`) are lowercased properties of Person; change them, a name
  or a title with `update_person`, which leaves `active` alone. Someone who
  leaves gets `deactivate_person` and `end_membership`; a retired agent gets
  `deactivate_actor` (and its token revoked). Nothing is deleted.
- A membership is a stint, `MemberOf {role, since}` keyed by its start date.
  `end_membership` writes `LeftTeam` for that stint; `add_member` cannot
  reopen it, and rejoining is a new stint with a new `since`.
- Source slugs are `<system>:<native id>` (`meet:…`, `slack:<channel>/<ts>`,
  `doc:…`, `ticket:…`), so ingesting the same item twice upserts.
- Use fixed dates in reads that compare to a date (`overdue_actions`,
  `quiet_projects`) and in the seed.
- Keys and cardinalities are fixed at creation. Before adding a type, decide
  its key and any `@card`; add properties as nullable.
