# Domain Examples

Ready-made enum sets and source lists for four reference domains. Use as starting points — adapt to the user's specific scope.

## Biotech

### Enums

```pg
// Element.kind
kind: enum(therapeutic, mechanism, trial, platform, device, reagent, diagnostic)

// domain (on Signal and Element)
domain: enum(oncology, neuro, cardio, immuno, rare-disease, metabolic, infectious, gene-therapy)?

// Company.type
type: enum(pharma, biotech, cro, academic, investor, regulator)?

// SourceType
type: enum(journal, newsletter, conference, regulatory-filing, blog, podcast)?

// ArtifactType
artifactType: enum(paper, preprint, trial-registration, fda-filing, article, pdf)
```

### Element properties (replace AI-specific)

```pg
// Therapeutic / trial specific
phase: enum(preclinical, phase-1, phase-2, phase-3, approved, withdrawn)?
indication: String?
moa: String?                // mechanism of action
modality: String?           // small-molecule, biologic, cell-therapy, gene-therapy
sponsor: String?
trial_id: String?           // NCT identifier
fda_status: String?
```

### Starter source list

| Name | URL | Type |
|------|-----|------|
| Endpoints News | endpts.com | newsletter |
| STAT News | statnews.com | publication |
| Nature Biotechnology | nature.com/nbt | journal |
| BioSpace | biospace.com | publication |
| FiercePharma | fiercepharma.com | publication |
| clinicaltrials.gov | clinicaltrials.gov | regulatory-filing |
| FDA Press Announcements | fda.gov/news-events | regulatory |
| bioRxiv | biorxiv.org | preprint |
| Derek Lowe (In The Pipeline) | science.org/blogs/pipeline | blog |

### Likely pattern themes

- FDA approval cascades in a therapeutic area
- Platform-vs-modality competition (e.g., mRNA vs viral-vector)
- Trial-failure clusters revealing mechanism issues
- M&A as regulatory uncertainty rises
- Academia-to-biotech translation loops

---

## Crypto / Web3

### Enums

```pg
// Element.kind
kind: enum(protocol, token, dapp, standard, l1-chain, l2-chain, dao, bridge, oracle)

// domain
domain: enum(defi, gaming, infra, memecoins, stablecoins, privacy, identity, dex, lending, staking)?

// Company.type
type: enum(protocol, exchange, investor, dao, l1, l2, media, market-maker, infra-provider)?

// SourceType
type: enum(blog, newsletter, podcast, governance-forum, on-chain-data, exchange-feed, research)?

// ArtifactType
artifactType: enum(article, proposal, governance-vote, on-chain-tx, podcast-episode, research-report, pdf)
```

### Element properties

```pg
chain: String?              // ethereum, solana, base, etc.
token_symbol: String?
contract_address: String?
tvl_usd: F64?
mcap_usd: F64?
governance_model: String?
audit_status: String?
launch_date: Date?
```

### Starter source list

| Name | URL | Type |
|------|-----|------|
| Bankless | bankless.com | newsletter/podcast |
| The Defiant | thedefiant.io | publication |
| Messari | messari.io | research |
| The Block | theblock.co | publication |
| Blockworks | blockworks.co | publication |
| DefiLlama | defillama.com | on-chain-data |
| Snapshot | snapshot.org | governance-forum |
| protocol governance forums | (per-protocol) | governance-forum |
| Vitalik's blog | vitalik.eth.limo | blog |

### Likely pattern themes

- L2 fragmentation vs consolidation
- Stablecoin regulation shifts
- DEX/CEX liquidity redistribution
- Governance-attack patterns
- Bridge-exploit clusters

---

## Fintech / Financial Services

### Enums

```pg
// Element.kind
kind: enum(product, platform, regulation, rail, asset-class, license)

// domain
domain: enum(lending, payments, bnpl, neobank, wealth, infra, compliance, crypto-banking)?

// Company.type
type: enum(bank, fintech, card-network, neobank, regulator, investor, processor, aggregator)?

// SourceType
type: enum(blog, newsletter, publication, regulatory-filing, earnings-call, podcast)?

// ArtifactType
artifactType: enum(article, earnings-report, regulatory-filing, sec-disclosure, press-release, pdf)
```

### Element properties

```pg
jurisdiction: String?
license_type: String?
asset_class: String?
volume_usd: F64?
customer_count: I64?
launch_year: I32?
```

### Starter source list

| Name | URL | Type |
|------|-----|------|
| Fintech Takes (Alex Johnson) | fintechtakes.com | newsletter |
| This Week in Fintech | thisweekinfintech.com | newsletter |
| PYMNTS | pymnts.com | publication |
| American Banker | americanbanker.com | publication |
| Not Boring (Packy McCormick) | notboring.co | newsletter |
| SEC EDGAR | sec.gov/edgar | regulatory |
| CFPB | consumerfinance.gov | regulatory |
| BIS | bis.org | research |
| Matt Levine (Money Stuff) | bloomberg.com/opinion/levine | newsletter |

### Likely pattern themes

- Rail modernization (RTP, FedNow, SEPA Instant)
- Embedded finance adoption curves
- Stablecoin-as-payment-rail shifts
- BaaS consolidation after regulatory scrutiny
- Open banking rollout by jurisdiction

---

## Geopolitics / Policy

### Enums

```pg
// Element.kind
kind: enum(treaty, sanction, conflict, election, policy, institution, actor)

// domain
domain: enum(us-china, europe-russia, middle-east, trade, climate-negotiations, nuclear, cyber, migration)?

// Company.type  (used for institutions/entities)
type: enum(government, multilateral, think-tank, media, analyst, ngo, alliance)?

// SourceType
type: enum(publication, newsletter, podcast, research-institute, government-release, academic-journal)?

// ArtifactType
artifactType: enum(article, policy-paper, communique, treaty-text, sanctions-list, speech, pdf)
```

### Element properties

```pg
jurisdiction: String?           // country or bloc
effective_date: Date?
status: enum(proposed, active, expired, withdrawn)?
signatories: [String]?
```

### Starter source list

| Name | URL | Type |
|------|-----|------|
| Foreign Affairs | foreignaffairs.com | publication |
| The Economist | economist.com | publication |
| CSIS | csis.org | think-tank |
| CFR | cfr.org | think-tank |
| Chatham House | chathamhouse.org | think-tank |
| Bruegel (EU) | bruegel.org | think-tank |
| Lawfare | lawfareblog.com | blog |
| Noahpinion | noahpinion.blog | newsletter |
| State Department | state.gov | government |
| UN News | news.un.org | multilateral |

### Likely pattern themes

- Sanctions regime expansions and workarounds
- Multi-polar alignment shifts
- Technology-export-control cascades
- Climate-finance commitments and delivery gaps
- Conflict-to-negotiation transitions

---

## Macroeconomics

### Enums

```pg
// Element.kind
kind: enum(indicator, policy, asset-class, institution, event)

// domain
domain: enum(monetary, fiscal, trade, labor, housing, energy, currency, inflation)?

// Company.type
type: enum(central-bank, government, research-institute, bank, asset-manager, media)?

// SourceType
type: enum(statistical-agency, central-bank-release, publication, newsletter, research-paper, podcast)?
```

### Starter source list

| Name | URL | Type |
|------|-----|------|
| FT Alphaville | ft.com/alphaville | publication |
| Odd Lots | bloomberg.com/podcasts/odd-lots | podcast |
| Macro Musings (David Beckworth) | macromusings.com | podcast |
| Joseph Politano (Apricitas) | apricitas.io | newsletter |
| Brad Setser (CFR) | cfr.org/blog/follow-money | blog |
| BIS | bis.org | research |
| Fed FRED | fred.stlouisfed.org | statistical-agency |
| IMF WEO | imf.org/en/Publications/WEO | research |

---

## Using These as Defaults

If the user is vague about a domain, present the relevant default source list (first 5–7 entries) and ask:

> I have a default starter set for <domain>. Are any of these wrong for your scope? Anything to add?

This is much faster than eliciting from scratch. Most users just want to confirm and add 1–2 of their own.
