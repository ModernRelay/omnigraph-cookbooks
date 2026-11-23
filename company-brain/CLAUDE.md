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
  and the edge to what it rests on in one commit. The `@card` minimums on
  `BasedOn` (`1..`) and `ClaimFrom` (`1..1`) refuse a write that leaves the
  node short, so a raw insert or load of a bare `Claim` or `Decision` fails
  with a `@card` violation and changes nothing. `unsupported_decisions` and `claims_without_source` still earn
  their place: a minimum counts a node only when a write touches it, so they
  are the only thing that finds rows an earlier release let in.
- Creates refuse an existing slug. Inserting a keyed node replaces the whole
  row, so `ClaimFrom`, `DecisionAbout`, `AssignedTo` and `ActsFor` are
  unkeyed and capped at one: `record_claim`, `promote_claim`,
  `propose_successor`, `add_action_item` and `add_actor` on a slug that
  exists fail with a `@card` violation and write nothing. Keep those four
  edges unkeyed; pick a new slug on refusal. `add_person` has no edge to
  guard with: run it only when `person_by_handle` resolves nobody.
- Every claim has a speaker: `ClaimedBy` is `@card(1..1)` and `record_claim`
  requires one. A load whose batch has the claim but not its `ClaimedBy` is
  refused; `claims_without_speaker` finds claims an earlier release admitted.
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
  ActionItem ("Agents extract, people decide" below). Accept only decisions
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

## Running it

Use the shared [local setup](../README.md#local-setup) with folder
`company-brain` and graph `company`, then load `seed.jsonl` (described in
[seed.md](seed.md)). With the server up:

```bash
omnigraph query current_decisions --target local-reader --graph company
omnigraph query decision_evidence --target local-reader --graph company \
  --params '{"decision":"search-in-house"}'
omnigraph query why_superseded --target local-reader --graph company \
  --params '{"decision":"search-vendor-buy"}'
omnigraph query contested_claims --target local-reader --graph company
omnigraph query actions_from_source --target local-reader --graph company \
  --params '{"source":"meet:search-review-2026-10-02"}'
omnigraph query overdue_actions --target local-reader --graph company \
  --params '{"as_of":"2026-10-14"}'
```

## What the model encodes

- **Extracting is not deciding.** An agent records what was said as an
  unverified claim. Checking it against the graph, verifying it, and
  promoting it to a decision or action item are separate steps, often by a
  different actor. Someone saying "let's double Chen's equity" is a claim;
  whether it is a decision depends on who said it, whether they could decide
  it, and what else is known.
- **Everything points at the exact words.** A decision rests on claims, and a
  claim quotes its source with a locator, so a reviewer can check the
  extraction against the text instead of trusting a summary. The same
  statement in two sources is two claims; corroboration is a decision resting
  on both.
- **Contradictions are data.** `Contradicts` links a newer claim to the older
  one it disputes. Both stay until a person rejects one. Contested claims and
  decisions at risk are derived on every read.
- **Decisions are never edited.** To change one, propose a successor:
  `Decision(old) -SupersededBy {reason}-> Decision(new)`. The one-line reason
  sits on the edge; the full why is in the nodes, because the successor
  rests on a claim that contradicts one behind the original. A decision is
  superseded at most once (`@card(0..1)`), so two agents proposing competing
  successors on two branches collide when the second merges. A decision
  stays replaced once its successor was accepted, even if that successor is
  deprecated later. A rejected successor replaces nothing, and
  `withdraw_successor` frees the slot for another.
- **People are not logins.** A Person exists whether or not they ever touch
  the graph. An Actor is an OmniGraph identity that can; it `ActsFor` a
  person. Agents resolve a handle with `person_by_handle` before creating
  anyone, so the same person does not appear three times. Someone who leaves
  is marked with `deactivate_person` and `end_membership`, never deleted, and
  `update_person` changes a name, title or handle without reactivating them.
- **Two kinds of time.** When something happened in the world is in the
  schema (`occurred_at`, `decided_at`, `due`, `since`, `until`). When the brain
  learned it is `recorded_at` on claims and facts, plus the commit history.
- **Creating never overwrites.** Inserting a keyed node replaces the whole
  row, so each create also writes one unkeyed edge capped at one
  (`ClaimFrom`, `DecisionAbout`, `AssignedTo`, `ActsFor`). Creating a claim,
  decision, action item or actor under a slug that already exists adds a
  second one, and the whole write is refused with a `@card` violation. An
  agent that ingests the same meeting twice is refused at the first claim it
  already recorded, and nothing a person verified, accepted, closed or
  retired is reset. A new person has no edge to guard with, so `add_person`
  relies on `person_by_handle` first. Every other edge is keyed, so
  re-running a link is a no-op, and a membership stint recorded again stays
  closed if `LeftTeam` closed it.

## Derived reads

| Question | Stored query |
|---|---|
| What is decided right now? | `current_decisions` |
| What is decided about this project, including proposals on a branch? | `project_decisions` |
| What does this decision rest on, in whose words? | `decision_evidence`, `decision_deciders` |
| Why was it replaced, and by what? | `why_superseded`, `superseding_contradictions`, `decision_lineage`, `decision_successor` |
| Which claims dispute each other? | `contested_claims` |
| Which current decisions do new claims put in question, or rest on a rejected one? | `decisions_at_risk`, `current_on_rejected` |
| What still needs a person to verify or accept? | `unverified_claims`, `proposed_decisions` |
| What came out of Tuesday's sync? | `claims_from_source`, `decisions_from_source`, `actions_from_source` |
| Which accepted decisions have no action following from them? | `unimplemented_decisions` |
| What is overdue, and who owns it? | `overdue_actions`, `person_actions` |
| Which projects went quiet? | `quiet_projects` |
| Who is this Slack user? Who answers for this agent? | `person_by_handle`, `actors` |
| Which claim said these words? | `search_quotes` |

Overdue and quiet take a fixed date or time as a parameter, so the seed's
answers do not change with the calendar.

## Agents extract, people decide

The policy gives every agent its own actor (`act-notes-bot`, `act-slack-bot`,
or the generic `act-agent`). Agents read everything, create branches and write
only on unprotected branches; they cannot write main, merge or delete a
branch. People (`act-alice`, `act-admin`, `act-writer`) review and merge, then
verify and accept on main, where no agent can write. Each commit records the
actor from the bearer token, so the history says which agent wrote what, and
`actors` says who answers for it.

The shared [local setup](../README.md#local-setup) has a token and a target
for admin, writer, reader and the generic `act-agent`. The walkthrough adds a
token and a target for each of the two named agents. The server reads static
tokens only at start, so stop it (Ctrl-C) and start it again with all six:

```bash
export OMNIGRAPH_SERVER_BEARER_TOKENS_JSON='{"act-admin":"local-admin-token","act-writer":"local-writer-token","act-reader":"local-reader-token","act-agent":"local-agent-token","act-notes-bot":"local-notes-token","act-slack-bot":"local-slack-token"}'
omnigraph-server --cluster . --bind 127.0.0.1:8080
```

Then add their targets under `targets:` in `$OMNIGRAPH_HOME/config.yaml`, in
the same shape as the shared ones, and export their tokens:

```yaml
  local-notes:
    kind: server
    endpoint: https://localhost:8443
    auth: {provider: token, source: {env: OG_LOCAL_NOTES_TOKEN}}
    transport: {tls: {ca: {mode: append, file: local-tls/ca.pem}}}
  local-slack:
    kind: server
    endpoint: https://localhost:8443
    auth: {provider: token, source: {env: OG_LOCAL_SLACK_TOKEN}}
    transport: {tls: {ca: {mode: append, file: local-tls/ca.pem}}}
```

```bash
export OG_LOCAL_NOTES_TOKEN=local-notes-token OG_LOCAL_SLACK_TOKEN=local-slack-token
omnigraph config validate
```

The meeting notes agent hears in the Oct 14 Checkout sync that the payment
provider moved certification. Writing on main is refused (403), so it works on
a branch. First it records what was said, nothing more:

```bash
AGENT=(--target local-notes --graph company)
B=(--branch agent/notes-oct-14)
omnigraph branch create agent/notes-oct-14 --from main "${AGENT[@]}"
omnigraph mutate record_source "${AGENT[@]}" "${B[@]}" --params \
  '{"slug":"meet:checkout-sync-2026-10-14","kind":"meeting","title":"Checkout sync","occurred_at":"2026-10-14T15:00:00.000Z","url":null,"summary":null}'
omnigraph mutate record_claim "${AGENT[@]}" "${B[@]}" --params \
  '{"slug":"provider-certifies-nov-13","kind":"fact","statement":"The payment provider moved Checkout v2 certification to Nov 13.","quote":"The provider pushed our certification back a week, to November 13.","locator":"00:03:40","recorded_at":"2026-10-14T16:00:00.000Z","source":"meet:checkout-sync-2026-10-14","speaker":"alice"}'
```

Then it checks the claim against what main trusts. The Nov 13 launch rests on
a kickoff claim that the new one disputes:

```bash
omnigraph query decision_evidence "${AGENT[@]}" --params '{"decision":"checkout-launch-nov-13"}'
#   launch-nov-13            | Alice Park | We go live for everyone on November 13.
#   provider-certifies-nov-6 | Chen Wei   | The provider confirmed certification by November 6, a week before launch.
omnigraph mutate mark_contradiction "${AGENT[@]}" "${B[@]}" --params \
  '{"claim":"provider-certifies-nov-13","contradicts":"provider-certifies-nov-6"}'
omnigraph query decisions_at_risk "${AGENT[@]}" "${B[@]}"
#   checkout-launch-nov-13 | The payment provider certifies … by Nov 6. | … moved … certification to Nov 13.
#   (on main: 0 rows)
```

It proposes a successor that rests on the new claim, with a one-line reason:

```bash
omnigraph mutate propose_successor "${AGENT[@]}" "${B[@]}" --params \
  '{"previous":"checkout-launch-nov-13","claim":"provider-certifies-nov-13","reason":"The payment provider moved certification back a week.","slug":"checkout-launch-nov-20","title":"Launch Checkout v2 on Nov 20","statement":"Checkout v2 goes live for all customers on Nov 20.","rationale":"Launch stays a week after certification, which moved to Nov 13.","decided_at":"2026-10-14T15:20:00.000Z","recorded_at":"2026-10-14T16:00:00.000Z","project":"checkout"}'
omnigraph query project_decisions "${AGENT[@]}" "${B[@]}" --params '{"project":"checkout"}'
#   Launch Checkout v2 on Nov 20 | proposed      (main still says Nov 13)
```

A person, here the admin, reviews the branch before merging it. `branch diff`
shows what the branch would bring into main: each node and edge it added or
changed since it left main, with the claim's quote and locator to check
against the source. The policy cannot tell one agent's branch from another's,
or which stored query an agent ran, so the review also checks the history:
who wrote each of the branch's commits, and whether any of them updated a
claim, decision or action item. An agent only creates those; a status change
is a person's job on main. The diff cannot show this, because it is the net
change: a claim an agent recorded and then verified on its branch is one
insert there. On a clean branch the loop prints no changes (it uses `jq`):

```bash
PERSON=(--target local --graph company)
omnigraph branch diff agent/notes-oct-14 "${PERSON[@]}"   # 3 nodes and 6 edges, all inserts
omnigraph commit list "${PERSON[@]}" "${B[@]}"            # one line per commit, with its actor
for c in $(omnigraph commit list "${PERSON[@]}" "${B[@]}" --json \
             | jq -r '.commits[] | select(.graph_branch == "agent/notes-oct-14") | .graph_commit_id'); do
  omnigraph commit changes "$c" "${PERSON[@]}" --op update --type Claim --type Decision --type ActionItem --json \
    | jq -c '.cause.actor_id as $a | .changes[] | {actor: $a, type: .type.name, id}'
done
```

`omnigraph branch list --detailed "${PERSON[@]}"` shows every open branch with
its head and when it last moved, which is how a person finds the agent work
waiting on them without reading each branch's history. Rows an agent writes on
its branch are not covered by the graph's indexes, so `search_claims` and
`search_quotes` scan them: covering them takes `omnigraph index build --target
. --graph company --branch agent/notes-oct-14` against the root with the server
stopped, which a short-lived review branch does not need.

Then the person runs the [hygiene](queries/hygiene.gq) reads on the branch,
previews the merge, merges, and settles the contradiction and the proposal on
main:

```bash
for q in unsupported_decisions accepted_on_unverified current_on_rejected \
         decisions_without_project claims_without_source claims_without_speaker \
         unowned_actions unsupported_actions agents_without_owner; do
  omnigraph query "$q" "${PERSON[@]}" "${B[@]}"    # each 0 rows
done
omnigraph branch merge agent/notes-oct-14 --into main --dry-run "${PERSON[@]}"   # would be: fast_forward
omnigraph branch merge agent/notes-oct-14 --into main "${PERSON[@]}"
omnigraph branch delete agent/notes-oct-14 "${PERSON[@]}" --yes
omnigraph mutate verify_claim "${PERSON[@]}" --params '{"slug":"provider-certifies-nov-13"}'
omnigraph mutate reject_claim "${PERSON[@]}" --params '{"slug":"provider-certifies-nov-6"}'
omnigraph mutate accept_decision "${PERSON[@]}" --params '{"slug":"checkout-launch-nov-20"}'
omnigraph query accepted_on_unverified "${PERSON[@]}"   # 0 rows
omnigraph query current_on_rejected "${PERSON[@]}"      # 0 rows: Nov 13 is replaced
omnigraph query why_superseded "${PERSON[@]}" --params '{"decision":"checkout-launch-nov-13"}'
#   checkout-launch-nov-20 | accepted | The payment provider moved certification back a week.
omnigraph query superseding_contradictions "${PERSON[@]}" --params '{"decision":"checkout-launch-nov-13"}'
#   checkout-launch-nov-20 | The payment provider moved … certification to Nov 13. |
#     The payment provider certifies … by Nov 6.
```

Between `reject_claim` and `accept_decision`, `current_on_rejected` lists
`checkout-launch-nov-13`: a current decision resting on a claim a person just
rejected. Accepting the successor clears it.

Had the person rejected the proposal instead, `reject_decision` and then
`withdraw_successor {"previous":"checkout-launch-nov-13","successor":"checkout-launch-nov-20"}`
leave Nov 13 current and free to be replaced again.

If the Slack agent (`local-slack`) had heard "two weeks" and proposed Nov 27
as another successor on its own branch, merging that branch now fails with
`merge conflicts: edge type 'SupersededBy' (cardinality_violation)`. Its dry
run reports the same conflict before anyone merges. Nothing lands; a person
decides which date is right.

Each [hygiene](queries/hygiene.gq) read returns zero rows on a healthy graph.
They exist because the schema cannot force an edge to exist when a node is
inserted: `@card(1..)` on `BasedOn` and `ClaimFrom` stops the last link from
being removed, and the stored mutations write the fact and what it rests on in
one commit. `accepted_on_unverified` enforces the two steps: verify the claims
before accepting the decision. Run them on a branch with `omnigraph query
<name> --branch …`, as above. The `lint-*` aliases in
[`omnigraph-config.example.yaml`](omnigraph-config.example.yaml) read main
only, because an alias cannot choose a branch.

## Extending

Each extension is a live, in-place schema change (see
[live updates](../README.md#live-updates)): add the type, its edges and its
queries, then `cluster plan`/`apply` through the running server. Add one when a
question you care about needs it, not before.

| Extension | Shape | Add it when |
|---|---|---|
| Spans | `Span { text, locator, embedding? }`, `SpanOf: Span -> Source`, `QuotedIn: Claim -> Span` | You chunk source text for semantic search, or one snippet backs many claims |
| Events | `Event { title, happened_at }`, `Triggered: Event -> Claim` | Things that happen outside any source (an outage, a funding round) explain why claims change |
| Goals | `Goal { title, quarter? }`, `Contributes: Project -> Goal` | The company runs goals or OKRs |
| Questions | `Question { text, status }`, `Answers: Decision -> Question` | Open questions need to be visible before anyone decides |
| Organizations | `Organization`, `WorksAt: Person -> Organization {since, until}` | Customers, vendors or partners are in scope |
| Semantic search | `embedding: Vector(N)? @embed("statement")` on `Claim` plus an embedding provider in `cluster.yaml` | Full-text search is not enough |

Keys, cardinalities and required properties are fixed when a type is created;
changing them later means a rebuild. New types, nullable properties, wider
enums and renames apply in place.

## What it does not do

- **Access is per graph and branch, not per row.** Anything ingested is
  readable by everyone who can read the graph. Ingest only sources whose
  audience includes every reader, and use separate graphs for separate
  audiences.
- **Merges compare whole rows.** Two agents changing different fields of the
  same action item still conflict.
- **The policy keeps agents off main, not off each other.** Rules are per
  graph and per protected or unprotected branch, and `invoke_query` covers
  the whole catalog. Any agent can write on any unprotected branch, and run
  `verify_claim` or `accept_decision` there; the review step above catches
  both from the history before a merge.
- **Handles live on the person.** A handle nobody has claimed yet cannot wait
  in the graph on its own; the agent creates the person or leaves the claim
  for a human.
- **The graph does not hold source text.** A claim's quote is what the agent
  copied; checking it against the original means opening the source's `url`.
- **No activity data.** Views, reactions and "works with" inferences are
  high-volume and short-lived; keep them out.
- **No embeddings in the seed.** See Extending above.
