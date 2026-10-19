# Reference seed: "Lanternworks" (fictional software company)

Human-readable twin of `seed.jsonl`. Every name is made up, and every email
address is on the reserved `.example` domain. Change both files together.
Dates are fixed in 2026, and the date-based reads take the date as a
parameter, so the answers below do not change with the calendar.

**The company:** *Lanternworks* ships a shopping app. Payments is building
Checkout v2, Discovery has rebuilt search in-house and is redesigning
onboarding, and Platform has frozen a billing migration. Two agents read the
company's meetings and Slack: `act-notes-bot` (accountable: Alice) and
`act-slack-bot` (accountable: Eli).

**Totals (loaded):** 55 nodes and 113 edges.

| Node type | # | Edge type | # |
|---|---|---|---|
| Person | 6 | MemberOf | 8 |
| Actor | 3 | PartOf | 4 |
| Team | 5 | ActsFor | 3 |
| Project | 4 | OwnedBy | 4 |
| Source | 8 | RunBy | 4 |
| Claim | 18 | SourceAbout | 8 |
| Decision | 6 | ClaimFrom | 18 |
| ActionItem | 5 | ClaimedBy | 18 |
| | | Contradicts | 2 |
| | | BasedOn | 11 |
| | | DecidedBy | 8 |
| | | DecisionAbout | 6 |
| | | SupersededBy | 1 |
| | | AssignedTo | 5 |
| | | ActionFrom | 5 |
| | | FollowsFrom | 3 |
| | | ActionAbout | 5 |

## People, actors and teams

| Person | Title | Team (role) | Handles |
|---|---|---|---|
| `alice` Alice Park | Head of Payments | Payments (lead) | email, Slack `u01alice`, GitHub `apark` |
| `bob` Bob Ortiz | Search lead | Discovery (lead) | email, Slack `u02bob` |
| `chen` Chen Wei | Software engineer | Payments (engineer); Discovery until 2026-06-30 | email, GitHub `chenwei` |
| `dana` Dana Kim | Product designer | Discovery (designer) | email |
| `eli` Eli Novak | CTO | Lanternworks (CTO), Platform (acting lead) | email |
| `fay` Fay Okafor | Support lead | Support (lead) | email |

Emails are `<slug>@lanternworks.example`. Payments, Discovery, Platform and
Support are `PartOf` Lanternworks.

| Actor | Kind | Acts for |
|---|---|---|
| `act-alice` | human | Alice |
| `act-notes-bot` Meeting notes agent | agent | Alice |
| `act-slack-bot` Slack agent | agent | Eli |

## Projects and sources

| Project | Status | Owner | Team |
|---|---|---|---|
| `checkout` Checkout v2 | active, target 2026-11-13 | Alice | Payments |
| `search` Search revamp | active, target 2026-12-15 | Bob | Discovery |
| `onboarding` New onboarding | planned | Dana | Discovery |
| `billing-migration` Billing migration | paused | Eli | Platform |

| Source | Kind | When | About |
|---|---|---|---|
| `doc:billing-plan` Billing migration plan | document | Jul 20 | billing-migration |
| `slack:c-search/1789466400` #search: hosted vendor or in-house? | thread | Sep 15 | search |
| `email:search-vendor-quote` Search vendor quote | email | Sep 25 | search |
| `meet:checkout-kickoff-2026-09-30` Checkout v2 kickoff | meeting | Sep 30 | checkout |
| `meet:search-review-2026-10-02` Search review | meeting | Oct 2 | search |
| `meet:onboarding-crit-2026-10-06` Onboarding design crit | meeting | Oct 6 | onboarding |
| `slack:c-support/1791363600` #support: where-is-my-order tickets | thread | Oct 7 | onboarding |
| `ticket:sup-1423` SUP-1423: checkout errors on saved cards | ticket | Oct 8 | checkout |

## Claims

Each claim has a verbatim `quote` and a `locator` (a meeting timestamp, a
Slack message ts, a document section). The table shows the statement.

| Claim | Kind | Status | Said by | Source |
|---|---|---|---|---|
| `billing-freeze-until-q1` Pause the billing migration until January | proposal | verified | Eli | Billing plan |
| `vendor-cheaper` A hosted vendor is cheaper and faster than in-house | fact | **rejected** | Bob | #search |
| `buy-hosted-search` Buy a hosted search vendor | proposal | verified | Bob | #search |
| `vendor-quote-3x` The vendor's quote is three times the budget | fact | verified | Bob | Vendor quote |
| `prototype-meets-latency` The in-house prototype meets the 200 ms target | fact | verified | Bob | Search review |
| `keep-search-in-house` Build search in-house, cancel the vendor trial | proposal | verified | Eli | Search review |
| `bob-cancels-trial` Bob cancels the trial by Oct 5 | commitment | verified | Eli | Search review |
| `bob-ships-prototype` Bob ships the prototype to staging by Oct 10 | commitment | verified | Bob | Search review |
| `provider-certifies-nov-6` The payment provider certifies Checkout v2 by Nov 6 | fact | verified | Chen | Checkout kickoff |
| `launch-nov-13` Launch Checkout v2 on Nov 13 | proposal | verified | Alice | Checkout kickoff |
| `keep-saved-cards` Keep saved cards in Checkout v2 | proposal | verified | Alice | Checkout kickoff |
| `chen-writes-checklist` Chen writes the launch checklist by Nov 6 | commitment | verified | Alice | Checkout kickoff |
| `three-step-onboarding` Cut onboarding from seven steps to three | proposal | unverified | Dana | Onboarding crit |
| `later-steps-not-needed` Nothing in steps 4–7, including the address, is needed before a first order | fact | unverified | Dana | Onboarding crit |
| `dana-drafts-copy` Dana drafts the three-step copy by Oct 20 | commitment | unverified | Dana | Onboarding crit |
| `address-step-tickets` A third of where-is-my-order tickets come from skipping the address step | fact | unverified | Fay | #support |
| `saved-card-error` Saved-card payments show a generic error | fact | verified | Fay | SUP-1423 |
| `chen-fixes-saved-cards` Chen fixes the saved-card errors by Oct 10 | commitment | verified | Fay | SUP-1423 |

Two contradictions, each pointing from the newer claim to the older one:

- `vendor-quote-3x` contradicts `vendor-cheaper`. Settled: `vendor-cheaper`
  is rejected and the decision resting on it was superseded.
- `address-step-tickets` contradicts `later-steps-not-needed`. Open: both are
  unverified, so the onboarding proposal is contested.

## Decisions and action items

| Decision | Status | Rests on | By |
|---|---|---|---|
| `billing-freeze` Freeze the billing migration until Q1 | accepted | `billing-freeze-until-q1` | Eli |
| `search-vendor-buy` Buy a hosted search vendor | accepted, **superseded by** `search-in-house` | `buy-hosted-search`, `vendor-cheaper` | Bob |
| `search-in-house` Keep search in-house | accepted | `keep-search-in-house`, `prototype-meets-latency`, `vendor-quote-3x` | Bob, Eli |
| `checkout-launch-nov-13` Launch Checkout v2 on Nov 13 | accepted | `launch-nov-13`, `provider-certifies-nov-6` | Alice, Eli |
| `checkout-saved-cards` Keep saved cards in Checkout v2 | accepted | `keep-saved-cards` | Alice |
| `onboarding-three-steps` Cut onboarding to three steps | proposed | `three-step-onboarding`, `later-steps-not-needed` | Dana |

`search-vendor-buy -SupersededBy-> search-in-house` carries the reason "The
vendor quoted three times the budget, and the in-house prototype met the
latency target."

| Action item | Status | Due | Owner | From claim | Follows from |
|---|---|---|---|---|---|
| `launch-checklist` | open | 2026-11-06 | Chen | `chen-writes-checklist` | `checkout-launch-nov-13` |
| `fix-saved-card-errors` | in progress | 2026-10-10 | Chen | `chen-fixes-saved-cards` | |
| `cancel-vendor-trial` | done | 2026-10-05 | Bob | `bob-cancels-trial` | `search-in-house` |
| `ship-search-prototype` | done | 2026-10-10 | Bob | `bob-ships-prototype` | `search-in-house` |
| `onboarding-copy` | open | 2026-10-20 | Dana | `dana-drafts-copy` | |

## What the seed demonstrates

- **`current_decisions`** returns four: `billing-freeze`,
  `checkout-launch-nov-13`, `checkout-saved-cards`, `search-in-house`.
  `search-vendor-buy` is still `accepted` in its row but no longer current,
  because an accepted decision supersedes it.
- **`project_decisions {"project":"checkout"}`**: Keep saved cards in Checkout
  v2 (accepted), Launch Checkout v2 on Nov 13 (accepted).
- **`decision_evidence {"decision":"search-in-house"}`**: `vendor-quote-3x`
  (Bob, Search vendor quote), then `keep-search-in-house` (Eli) and
  `prototype-meets-latency` (Bob), both from the Search review, each with
  its quote.
- **`why_superseded {"decision":"search-vendor-buy"}`**: replaced by
  `search-in-house`, with the edge's reason, because "The hosted vendor's
  quote is three times the search budget." contradicts "A hosted search
  vendor is cheaper and faster than building ranking in-house."
- **`decision_lineage {"decision":"search-in-house"}`**: `search-vendor-buy`.
  `decision_successor {"decision":"search-vendor-buy"}`: `search-in-house`.
  `decision_deciders {"decision":"search-in-house"}`: Bob Ortiz, Eli Novak.
- **`decisions_from_source {"source":"meet:checkout-kickoff-2026-09-30"}`**:
  `checkout-launch-nov-13` (2 claims), `checkout-saved-cards` (1).
- **`claims_from_source {"source":"meet:onboarding-crit-2026-10-06"}`**:
  `three-step-onboarding` (00:04:20), `later-steps-not-needed` (00:07:45),
  `dana-drafts-copy` (00:31:00).
- **`contested_claims`**: `address-step-tickets` against
  `later-steps-not-needed`. **`decisions_at_risk`**: zero rows, because the
  contested claim backs a proposal, not an accepted decision.
- **`unverified_claims`**: the three onboarding-crit claims, then
  `address-step-tickets`.
- **`proposed_decisions`**: `onboarding-three-steps`.
- **`unimplemented_decisions`**: `billing-freeze`, `checkout-saved-cards`.
- **`open_actions`**: `fix-saved-card-errors`, `onboarding-copy`,
  `launch-checklist`, earliest due first.
- **`overdue_actions {"as_of":"2026-10-14"}`**: `fix-saved-card-errors`
  (Chen, due 2026-10-10).
- **`actions_from_source {"source":"meet:search-review-2026-10-02"}`**: Cancel
  the hosted search trial, Ship the in-house search prototype to staging.
- **`quiet_projects {"since":"2026-09-14T00:00:00.000Z"}`**: Billing migration
  (paused; nothing since July).
- **`team_members {"team":"discovery"}`**: Bob Ortiz (lead), Dana Kim
  (designer). Chen's membership ended on 2026-06-30, so he is not listed.
- **`person_by_handle {"handle":"u01alice"}`**: `alice`.
- **`actors`**: `act-alice` (human, Alice Park), `act-notes-bot` (agent, Alice
  Park), `act-slack-bot` (agent, Eli Novak).
- **Hygiene:** `unsupported_decisions`, `accepted_on_unverified`,
  `decisions_without_project`, `claims_without_source`, `unowned_actions`,
  `unsupported_actions` and `agents_without_owner` each return zero rows.

## The walkthrough in the README

Run against this seed, the README's "Agents extract, people decide" steps
give:

- On `agent/notes-oct-14`, after `mark_contradiction`, `decisions_at_risk`
  returns `checkout-launch-nov-13`: it rests on "The payment provider
  certifies Checkout v2 by Nov 6.", which the new claim contradicts. On main
  it returns zero rows.
- After `propose_successor`, `project_decisions {"project":"checkout"}` on
  the branch shows Launch Checkout v2 on Nov 20 (proposed); main still shows
  Nov 13.
- The review loop prints nothing and each hygiene read returns zero rows on
  the branch. After the merge (`fast_forward`) and `verify_claim`,
  `reject_claim` and `accept_decision` on main, `current_decisions` lists
  `checkout-launch-nov-20` instead of `checkout-launch-nov-13`. `why_superseded
  {"decision":"checkout-launch-nov-13"}` returns the reason and the two
  contradicting claims, and `decisions_at_risk` is empty again.
- A second branch that proposed `checkout-launch-nov-27` as another successor
  of `checkout-launch-nov-13` fails to merge with
  `merge conflicts: edge type 'SupersededBy' (cardinality_violation)`.
