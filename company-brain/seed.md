# Reference seed: "Lanternworks" (fictional software company)

Human-readable twin of `seed.jsonl`. Every name is made up, and every email
address is on the reserved `.example` domain. Change both files together.
Dates are fixed in 2026, and the date-based reads take the date as a
parameter, so the answers below do not change with the calendar.

**The company:** *Lanternworks* ships a shopping app. Payments is building
Checkout v2, Discovery is rebuilding search and redesigning onboarding, and
Platform has frozen a billing migration. Two agents read the company's
meetings and Slack: `act-notes-bot` (accountable: Alice) and `act-slack-bot`
(accountable: Eli).

**Totals (loaded):** 46 nodes and 92 edges.

| Node type | # | Edge type | # |
|---|---|---|---|
| Person | 6 | MemberOf | 8 |
| Team | 5 | PartOf | 4 |
| Identity | 11 | IdentifiesPerson | 10 |
| Agent | 2 | ActsFor | 2 |
| Project | 4 | OwnedBy | 4 |
| Source | 7 | RunBy | 4 |
| Decision | 6 | Involved | 13 |
| ActionItem | 5 | SourceAbout | 7 |
| | | DecisionAbout | 6 |
| | | DecidedIn | 7 |
| | | DecidedBy | 8 |
| | | SupersededBy | 1 |
| | | AssignedTo | 5 |
| | | ActionFrom | 5 |
| | | ActionAbout | 5 |
| | | Implements | 3 |

## People and teams

| Person | Title | Team (role) |
|---|---|---|
| `alice` Alice Park | Head of Payments | Payments (lead) |
| `bob` Bob Ortiz | Search lead | Discovery (lead) |
| `chen` Chen Wei | Software engineer | Payments (engineer); Discovery until 2026-06-30 |
| `dana` Dana Kim | Product designer | Discovery (designer) |
| `eli` Eli Novak | CTO | Lanternworks (CTO), Platform (acting lead) |
| `fay` Fay Okafor | Support lead | Support (lead) |

Payments, Discovery, Platform and Support are `PartOf` Lanternworks. Alice has
three identities (email, Slack, GitHub). Eli's email was ingested as
`Eli@Lanternworks.example`; its slug is lowercased. `slack:u09guest` is not
linked to anyone yet.

## Projects, sources and decisions

| Project | Status | Owner | Team |
|---|---|---|---|
| `checkout` Checkout v2 | active, target 2026-11-13 | Alice | Payments |
| `search` Search revamp | active, target 2026-12-15 | Bob | Discovery |
| `onboarding` New onboarding | planned | Dana | Discovery |
| `billing-migration` Billing migration | paused | Eli | Platform |

| Decision | Status | Decided in | By |
|---|---|---|---|
| `billing-freeze` Freeze the billing migration until Q1 | accepted | Billing migration plan (doc, Jul 20) | Eli |
| `search-vendor-buy` Buy a hosted search vendor | accepted, **superseded by** `search-in-house` | #search thread (Sep 15) | Bob |
| `search-in-house` Keep search in-house | accepted | Search review (Oct 2), Search vendor quote (email) | Bob, Eli |
| `checkout-launch-nov-13` Launch Checkout v2 on Nov 13 | accepted | Checkout v2 kickoff (Sep 30) | Alice, Eli |
| `checkout-saved-cards` Keep saved cards in Checkout v2 | accepted | Checkout v2 kickoff | Alice |
| `onboarding-three-steps` Cut onboarding to three steps | proposed | Onboarding design crit (Oct 6) | Dana |

| Action item | Status | Due | Owner | From | Implements |
|---|---|---|---|---|---|
| `launch-checklist` | open | 2026-11-06 | Chen | Checkout kickoff | `checkout-launch-nov-13` |
| `fix-saved-card-errors` | in progress | 2026-10-10 | Chen | SUP-1423 (ticket) | |
| `cancel-vendor-trial` | done | 2026-10-05 | Bob | Search review | `search-in-house` |
| `ship-search-prototype` | done | 2026-10-10 | Bob | Search review | `search-in-house` |
| `onboarding-copy` | open | 2026-10-20 | Dana | Onboarding crit | |

## What the seed demonstrates

- **`current_decisions`** returns four: `billing-freeze`,
  `checkout-launch-nov-13`, `checkout-saved-cards`, `search-in-house`.
  `search-vendor-buy` is still `accepted` in its row but no longer current,
  because an accepted decision supersedes it.
- **`project_decisions {"project":"checkout"}`**: Keep saved cards in Checkout
  v2 (accepted), Launch Checkout v2 on Nov 13 (accepted).
- **`decision_lineage {"decision":"search-in-house"}`**: `search-vendor-buy`.
  `decision_successor {"decision":"search-vendor-buy"}`: `search-in-house`.
- **`decision_sources {"decision":"search-in-house"}`**: Search vendor quote
  (email), Search review (meeting). `decision_deciders`: Bob Ortiz, Eli Novak.
- **`decisions_from_source {"source":"meet:checkout-kickoff-2026-09-30"}`**:
  `checkout-launch-nov-13`, `checkout-saved-cards`.
- **`proposed_decisions`**: `onboarding-three-steps`.
- **`unimplemented_decisions`**: `billing-freeze`, `checkout-saved-cards`.
- **`open_actions`**: `fix-saved-card-errors`, `onboarding-copy`,
  `launch-checklist`, earliest due first.
- **`overdue_actions {"as_of":"2026-10-14"}`**: `fix-saved-card-errors`
  (Chen, due 2026-10-10).
- **`quiet_projects {"since":"2026-09-14T00:00:00.000Z"}`**: Billing migration
  (paused; nothing since July).
- **`team_members {"team":"discovery"}`**: Bob Ortiz (lead), Dana Kim
  (designer). Chen's membership ended on 2026-06-30, so he is not listed.
- **`person_by_identity {"identity":"slack:u01alice"}`**: `alice`.
  **`unresolved_identities`**: `slack:u09guest`.
- **`agents`**: `act-notes-bot` (Alice Park), `act-slack-bot` (Eli Novak).
- **Hygiene:** `uncited_decisions`, `decisions_without_project`,
  `unowned_actions`, `uncited_actions` and `agents_without_owner` each return
  zero rows.

## The walkthrough in the README

Run against this seed, the README's "Agents propose, people merge" steps give:

- On `agent/notes-oct-14`, `project_decisions {"project":"checkout"}` shows
  Launch Checkout v2 on Nov 20 (proposed); on main it still shows Nov 13.
- After `accept_decision` and the merge (`fast_forward`), `current_decisions`
  lists `checkout-launch-nov-20` instead of `checkout-launch-nov-13`, and
  `decision_lineage {"decision":"checkout-launch-nov-20"}` returns
  `checkout-launch-nov-13`.
- A second branch that proposed `checkout-launch-nov-27` as another successor
  of `checkout-launch-nov-13` fails to merge with
  `merge conflicts: edge type 'SupersededBy' (cardinality_violation)`.
