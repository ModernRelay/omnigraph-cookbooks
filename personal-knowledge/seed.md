# Personal Knowledge — Seed Data

A fictional but coherent personal knowledge graph for "Alex Rivera," a product manager building a SaaS product. The seed demonstrates every major node type, multi-source ingestion, and identity overlaps across sources (so the dedup wizard has work to do).

All data is fabricated. No real persons, companies, or messages.

## Persons (12)

| slug | name | relation | email |
| --- | --- | --- | --- |
| `person-alex-rivera` | Alex Rivera (self) | other | alex@arivera.dev |
| `person-jane-park` | Jane Park | colleague | jane@kettle.so |
| `person-jane-park-personal` | Jane | colleague | (no email — Slack handle only) |
| `person-marcus-leblanc` | Marcus LeBlanc | mentor | marcus@leblancadvisors.com |
| `person-priya-shah` | Priya Shah | friend | priya.shah.97@gmail.com |
| `person-priya-shah-work` | Priya Shah | professional | priya@cardinaldev.com |
| `person-tomohiro-sato` | Tomohiro Sato | colleague | tom@kettle.so |
| `person-elena-nikolaidis` | Elena Nikolaidis | acquaintance | elena.n@stanford.edu |
| `person-david-chen` | David Chen | mentor | dchen@accelerent.vc |
| `person-rachel-hoffman` | Rachel Hoffman | family | rachel.hoffman.bk@gmail.com |
| `person-aaron-kim` | Aaron Kim | colleague | aaron@kettle.so |
| `person-sara-mitchell` | Sara Mitchell | friend | (none) |

Identity-resolution candidates: `person-jane-park` ↔ `person-jane-park-personal` (same person across email + Slack); `person-priya-shah` ↔ `person-priya-shah-work` (same person across personal + work email).

## Organizations (5)

| slug | name | kind |
| --- | --- | --- |
| `org-kettle` | Kettle | company |
| `org-cardinaldev` | Cardinal Dev | company |
| `org-leblanc-advisors` | LeBlanc Advisors | company |
| `org-accelerent` | Accelerent Capital | company |
| `org-stanford` | Stanford University | school |

## Places (3)

| slug | name | kind |
| --- | --- | --- |
| `place-sf` | San Francisco | city |
| `place-kettle-hq` | Kettle HQ (1455 Market St) | office |
| `place-blue-bottle-mint` | Blue Bottle Coffee — Mint Plaza | cafe |

## Areas (4)

| slug | name | kind |
| --- | --- | --- |
| `area-career` | Career | career |
| `area-learning` | Learning | learning |
| `area-relationships` | Relationships | relationships |
| `area-health` | Health | health |

## Projects (5)

| slug | name | kind | status |
| --- | --- | --- | --- |
| `proj-pk-launch` | Kettle PK feature launch | work | active |
| `proj-q2-research` | Q2 customer research sprint | work | active |
| `proj-pkm-system` | Personal PKM rebuild | personal | active |
| `proj-running-sub-90` | Half-marathon sub-1:30 | hobby | active |
| `proj-spanish-b2` | Spanish to B2 | learning | paused |

## Goals (3)

| slug | name | status |
| --- | --- | --- |
| `goal-ship-pk-q2` | Ship PK feature by end of Q2 | active |
| `goal-30-customer-calls` | 30 customer calls in Q2 | active |
| `goal-half-marathon-sub-90` | Run half marathon under 1:30 | active |

## Habits (3)

| slug | name | frequency |
| --- | --- | --- |
| `habit-morning-pages` | Morning pages | daily |
| `habit-weekly-review` | Weekly review (GTD) | weekly |
| `habit-strength-training` | Strength training | weekly |

## Tasks (8)

| slug | name | status |
| --- | --- | --- |
| `task-draft-pk-spec` | Draft PK feature spec | next |
| `task-call-priya` | Call Priya re: research interviews | next |
| `task-review-elena-paper` | Review Elena's paper draft | waiting |
| `task-book-flights-dec` | Book flights for December trip | inbox |
| `task-followup-marcus` | Follow up with Marcus on advisor agreement | next |
| `task-q2-okrs-draft` | Draft Q2 OKRs | inbox |
| `task-fix-onboarding-step3` | Fix onboarding step 3 dropoff | next |
| `task-renew-passport` | Renew passport | someday |

## Notes (15)

| slug | name | kind | source-via-Artifact |
| --- | --- | --- | --- |
| `note-pk-vision` | PK vision: agents writing into governed context | insight | obsidian |
| `note-bsbb-on-onboarding` | "Build Smaller, But Better" — Marcus on onboarding | quote | granola |
| `note-jane-customer-priorities` | Jane's framing of customer priorities | reflection | notion |
| `note-q2-okr-draft` | Q2 OKRs (draft) | idea | notion |
| `note-running-form-cue` | Running form cue: "tall, light, quick" | principle | obsidian |
| `note-spanish-conjunctions` | Spanish conjunction patterns | idea | apple-notes |
| `note-priya-onboarding-pain` | Priya: onboarding pain at Cardinal | reflection | granola |
| `note-context-graph-thesis` | Context graph thesis (own writing) | insight | obsidian |
| `note-david-fundraise-advice` | David's fundraise advice — narrative > numbers | quote | granola |
| `note-elena-rl-paper-summary` | Elena's RL paper summary | reflection | notion |
| `note-sara-trip-planning` | Trip ideas for December (with Sara) | journal | apple-notes |
| `note-team-offsite-themes` | Team offsite themes | idea | granola |
| `note-pkm-redesign-principles` | PKM redesign — atomic, not hierarchical | principle | obsidian |
| `note-half-marathon-training-plan` | Half-marathon training plan | idea | obsidian |
| `note-aaron-design-feedback` | Aaron's feedback on the spec | reflection | slack |

## Artifacts (15) — provenance for the notes above

| slug | source | kind |
| --- | --- | --- |
| `art-obsidian-pk-vision` | obsidian | document |
| `art-obsidian-running-form` | obsidian | document |
| `art-obsidian-context-graph-thesis` | obsidian | document |
| `art-obsidian-pkm-principles` | obsidian | document |
| `art-obsidian-half-marathon-plan` | obsidian | document |
| `art-notion-customer-priorities` | notion | document |
| `art-notion-q2-okrs` | notion | document |
| `art-notion-rl-paper-notes` | notion | document |
| `art-apple-spanish-conjunctions` | apple-notes | document |
| `art-apple-trip-dec-ideas` | apple-notes | document |
| `art-granola-marcus-2026-04-12` | granola | transcript |
| `art-granola-priya-2026-04-22` | granola | transcript |
| `art-granola-david-2026-05-01` | granola | transcript |
| `art-granola-team-offsite-2026-04-30` | granola | transcript |
| `art-slack-aaron-feedback-2026-05-06` | slack | message |

## Conversations (3)

| slug | source | participants |
| --- | --- | --- |
| `conv-slack-pk-launch` | slack | alex, jane, aaron, tomohiro |
| `conv-slack-research` | slack | alex, priya |
| `conv-email-marcus-thread` | email | alex, marcus |

## Emails (4)

| slug | from | to | subject |
| --- | --- | --- | --- |
| `email-marcus-2026-04-10` | marcus@leblancadvisors.com | alex@arivera.dev | "Advisor agreement — final draft" |
| `email-marcus-2026-04-15` | alex@arivera.dev | marcus@leblancadvisors.com | "Re: Advisor agreement — final draft" |
| `email-priya-intro-2026-04-18` | priya@cardinaldev.com | alex@arivera.dev | "Intro — Cardinal Dev customer chat?" |
| `email-jane-spec-2026-05-05` | jane@kettle.so | alex@arivera.dev | "Spec review notes" |

## Events (4)

| slug | name | kind |
| --- | --- | --- |
| `event-marcus-1on1-2026-04-12` | Marcus 1:1 — advisor onboarding | meeting |
| `event-priya-research-2026-04-22` | Priya — Cardinal customer interview | meeting |
| `event-david-fundraise-2026-05-01` | David — fundraise prep call | call |
| `event-team-offsite-2026-04-30` | Kettle team offsite Q2 | conference |

## ExternalIDs (cross-source identity)

The dedup wizard should propose merges between:
- `person-jane-park` (email) and `person-jane-park-personal` (Slack) — both Jane.
- `person-priya-shah` (personal Gmail) and `person-priya-shah-work` (work email at Cardinal Dev) — both Priya.
