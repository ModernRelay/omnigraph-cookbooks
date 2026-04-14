# Custom Domain Setup — Elicitation

Full elicitation flow for Phase 1–4 of the custom path. Use AskUserQuestion throughout to give the user structured multi-select rather than free-form typing where possible.

## Phase 1 — Domain Identification

### 1a. Pick the domain

AskUserQuestion (single-select with "Other"):

> **Which domain do you want to track?**
>
> - Biotech / therapeutics
> - Fintech / financial services
> - Crypto / web3
> - Geopolitics / policy
> - Macroeconomics
> - SaaS / enterprise software
> - Climate tech / energy transition
> - Other (I'll describe it)

### 1b. Narrow the scope

Free-form follow-ups:

> **How wide is the scope?**
> Examples: "all of biotech" vs "only oncology therapeutics"; "all crypto" vs "only DeFi on Ethereum L2s".

> **Geographic focus?**
> Global, or a specific region (US, EU, APAC, LATAM, etc.)?

### 1c. Project slug

Generate a project slug from the domain. Examples:
- Biotech → `bio-intel`
- Crypto → `crypto-intel`
- Geopolitics → `geo-intel`
- Macroeconomics → `macro-intel`
- SaaS → `saas-intel`

This becomes:
- The starter folder name: `<slug>/`
- The repo URI: `s3://omnigraph-local/repos/<slug>`
- The project name in `omnigraph.yaml`

Confirm with the user before proceeding.

## Phase 2 — Key Questions (Multi-Select)

### 2a. Actors to track

AskUserQuestion (multi-select):

> **Which kinds of actors matter most in this domain?**
>
> - Companies (commercial entities)
> - Labs / research institutions
> - Regulators / government bodies
> - Individuals (experts, founders, analysts)
> - Protocols / standards bodies
> - Investors (VCs, funds, allocators)
> - DAOs / community orgs (crypto-specific)

The selection drives which `Company.type` enum values are needed and whether you add an `Investor` or `DAO` node type.

### 2b. Time horizon

AskUserQuestion (single-select):

> **Are we tracking only recent signals, or also historical context?**
>
> - Recent only (last 3 months)
> - Medium (last 12 months)
> - Full historical (multi-year, including foundational events)

Drives how much research depth to aim for in Phase 6.

### 2c. Update cadence

AskUserQuestion (single-select):

> **How often will the graph be updated and consumed?**
>
> - Daily
> - Weekly
> - Monthly
> - Ad-hoc (on demand)

Drives whether to set up branch-review flow in later docs.

### 2d. Primary consumer

AskUserQuestion (single-select):

> **Who or what consumes the graph's output?**
>
> - Human analysts (briefings, newsletters)
> - Internal dashboard
> - Other AI agents (via queries)
> - Mixed

Drives `cli.output_format` default and whether to emphasize aliases for agent consumers.

## Phase 3 — Sources (Most Important)

**Sources are the lifeblood of a SPIKE graph. The quality of everything downstream is bounded by source quality.** Spend time here — don't rush.

Ask each question sequentially. Free-form answers are fine here; AskUserQuestion is overkill for open-ended lists.

### 3a. Primary reading list

> **What sources do you already read regularly in this domain? Newsletters, blogs, publications, major outlets, podcasts.**
>
> Aim for 5–15 entries. Don't stop at 3.

Capture each as: `name | url | type (blog/newsletter/podcast/publication) | why it matters`.

### 3b. Priority analysts / experts

> **Which individual analysts, researchers, or practitioners whose takes you want to track?**
>
> Aim for 3–10 people. First-class Expert entities in the graph.

Capture: `name | affiliation | platform (X, Substack, blog) | url`.

### 3c. Regulatory / authoritative sources

> **Which regulatory, governmental, or authoritative bodies publish in this domain?**

Examples to prompt with:
- Biotech: FDA, EMA, NIH, PMDA, clinicaltrials.gov
- Fintech: SEC, CFPB, Federal Reserve, OCC, FCA, BIS
- Crypto: SEC, CFTC, FinCEN, MAS, MiCA regulators
- Geopolitics: State Department, Foreign Ministries, UN agencies, major think tanks
- Macroecon: BLS, Fed, BEA, ECB, BOJ, major central banks

### 3d. Academic / primary sources

> **Are there academic venues or primary research sources to track?**

Examples:
- Biotech: Nature, Science, Cell, NEJM, JAMA, bioRxiv
- Crypto: protocol governance forums, Messari research, DefiLlama
- Macro: BIS papers, NBER, Fed research, IMF WEO
- Geopolitics: Foreign Affairs, CFR, CSIS, RAND

### 3e. Social / community

> **Any X/Twitter accounts, podcasts, Discord/Telegram forums, or community sources?**

Capture: `name | platform | handle_or_url`.

## Phase 4 — Confirm Summary

Before touching any code, echo the captured info back:

```markdown
# Setup notes — <domain>

**Project slug:** <slug>
**Repo URI:** s3://omnigraph-local/repos/<slug>
**Scope:** <narrow/broad + geographic focus>

## Actors
- <list>

## Horizon + cadence
- Horizon: <recent/medium/full>
- Cadence: <daily/weekly/...>
- Consumer: <humans/dashboard/agents/mixed>

## Sources

### Primary reading list
| Name | URL | Type | Notes |

### Priority experts
| Name | Affiliation | Platform | URL |

### Regulatory / authoritative
| Name | URL | Type |

### Academic / primary
| Name | URL | Type |

### Social / community
| Name | Platform | Handle |
```

Save this as `<slug>/setup-notes.md`. Commit it — it's also documentation.

**Explicitly ask the user to review and confirm before Phase 5.** Reworking the schema is cheaper than reworking the seed, so catch errors here.

## Tips

- **Don't accept "just pick what makes sense"** — the domain expert has context you don't. Push back gently with examples.
- **Treat source lists as incomplete by default.** After the first pass, ask: "anything else? any sources that don't fit the categories above?"
- **Deduplicate** — if a source appears in both "primary reading" and "analyst accounts", pick one canonical entry (usually the analyst as an Expert, with the outlet as a SourceEntity).
- **If the user is vague about sources**, offer a starter set based on the domain (see `references/domain-examples.md`) and ask which to add/remove.
