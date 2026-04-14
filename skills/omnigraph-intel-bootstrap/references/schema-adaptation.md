# Schema Adaptation

What to **keep** vs **change** when adapting the `industry-intel` schema for a new domain.

## What Stays (Domain-Agnostic)

These are SPIKE invariants. Changing them means you're not doing SPIKE anymore.

### Node types

Keep all 10 node types unchanged:
- **SPIKE nodes**: Signal, Pattern, Insight, KnowHow, Element
- **Supportive**: Company, SourceEntity, Expert, InformationArtifact, Chunk

If a domain seems to want a new node type (e.g., DAO for crypto, ClinicalTrial for biotech), prefer modeling it as `Element.kind = dao` or adding a `trial_id` property to Element. Resist adding node types — the SPIKE core works better when it stays narrow.

### Core analytical edges

- FormsPattern, ContradictsPattern (Signal → Pattern)
- DrivesPattern, ReliesOnPattern, ContradictsToPattern (Pattern → Pattern)
- HighlightsPattern (Insight → Pattern)
- OnElement (Signal → Element)
- EnablesElement, UsesElement (Element → Element)
- ExemplifiesPattern, EnablesPattern (Element → Pattern)
- ReferencesElement (KnowHow → Element)

These are the analytical skeleton. Don't touch them.

### Classification / provenance edges

- DevelopedByCompany (Element → Company)
- RelevantCompany (Signal → Company)
- AffiliatedWithCompany (Expert → Company)
- SpottedInArtifact (Signal → InformationArtifact)
- IdentifiedInArtifact (Element → InformationArtifact)
- SourcedFromArtifact (KnowHow → InformationArtifact)
- SourcedFromSource (Signal → SourceEntity)
- PublishedBySource (InformationArtifact → SourceEntity)
- ContributedByExpert (InformationArtifact → Expert)
- PartOfArtifact (Chunk → InformationArtifact)

Keep.

### Fixed properties

- `slug: String @key` on every node
- `stagingTimestamp`, `createdAt`, `updatedAt` timestamps where they are
- `embedding: Vector(3072) @embed("text") @index` on Chunk
- Slug prefixes: `sig-`, `pat-`, `el-`, `ins-`, `how-to-`, `co-`, `exp-`, `ia-`, `source-`

## What Changes (Domain-Specific)

### 1. `Element.kind` enum

The AI schema:
```pg
kind: enum(product, technology, framework, concept, ops)
```

Replace with domain-appropriate kinds. See `references/domain-examples.md` for worked examples:
- Biotech: `therapeutic, mechanism, trial, platform, device, reagent`
- Crypto: `protocol, token, dapp, standard, l1-chain, l2-chain, dao`
- Fintech: `product, platform, regulation, rail, asset-class`
- Geopolitics: `treaty, sanction, conflict, election, policy, institution`

Rule of thumb: 4–7 kinds. Fewer = coarse and useless for filtering; more = overfit.

### 2. `domain` enum on Signal + Element

The AI schema:
```pg
domain: enum(training, inference, infra, harness, robotics, security, data-eng, context)?
```

Replace with sub-fields of the target domain:
- Biotech: `oncology, neuro, cardio, immuno, rare-disease, metabolic, infectious`
- Crypto: `defi, gaming, infra, memecoins, stablecoins, privacy, identity, dex`
- Fintech: `lending, payments, bnpl, neobank, wealth, infra, compliance`

Must be declared **identically on both Signal and Element** — it's duplicated inline because the parser doesn't support shared enums.

### 3. `Company.type` enum

The AI schema:
```pg
type: enum(bigtech, developer, investor, research, hardware, media)?
```

Replace with ecosystem roles:
- Biotech: `pharma, biotech, cro, academic, investor, regulator`
- Crypto: `protocol, exchange, investor, dao, l1, l2, media`
- Fintech: `bank, fintech, card-network, neobank, regulator, investor`
- Geopolitics: `government, multilateral, think-tank, media, analyst`

### 4. `SourceType` enum on SourceEntity

The AI schema:
```pg
type: enum(blog, newsletter, video_channel, academic_repository, podcast, organization)?
```

Usually only needs minor additions. Add anything domain-specific:
- Biotech: `journal, conference, regulatory-filing`
- Crypto: `governance-forum, on-chain-data, exchange-feed`
- Macro: `central-bank, statistical-agency, research-institute`

### 5. `ArtifactType` enum on InformationArtifact

The AI schema:
```pg
artifactType: enum(email, youtube, pdf, article)
```

Add domain-specific formats:
- Biotech: `paper, preprint, trial-registration, fda-filing`
- Crypto: `proposal, governance-vote, block-explorer, on-chain-tx`
- Macro: `statistical-release, policy-statement, transcript`

### 6. Kind-specific Element properties

The AI schema has these optional properties tied to `kind`:

```pg
// Product / Framework shared
website: String?
release_year: I32?
license: String?

// Framework-specific
repository: String?
use_cases: [String]?
key_features: [String]?
target_users: String?

// Concept-specific
definition: String?
key_points: [String]?
```

Keep the shared ones (`website`, `release_year`) if they fit. Replace kind-specific with domain-relevant:

**Biotech:**
```pg
// Therapeutic-specific
phase: enum(preclinical, phase-1, phase-2, phase-3, approved, withdrawn)?
indication: String?
moa: String?           // mechanism of action
sponsor: String?
trial_id: String?

// Platform-specific
modality: String?      // small-molecule, biologic, cell-therapy, etc.
```

**Crypto:**
```pg
// Protocol/token specific
chain: String?          // ethereum, solana, etc.
token_symbol: String?
tvl_usd: F64?
contract_address: String?
governance_model: String?
```

**Fintech:**
```pg
// Product specific
jurisdiction: String?
license_type: String?
asset_class: String?
```

### 7. `Pattern.kind` enum — usually keep

```pg
kind: enum(challenge, disruption, dynamic)
```

This is intentionally abstract and works across domains. **Only change if the user has strong reasons.** Resist the urge to over-specify.

## Update omnigraph.yaml

After schema changes, update `<slug>/omnigraph.yaml`:

```yaml
project:
  name: <domain> Intel — SPIKE Framework

graphs:
  local_s3:
    uri: s3://omnigraph-local/repos/<slug>    # was: repos/spike-intel
  local_server:
    uri: http://127.0.0.1:8080
```

If the domain-specific enums changed, aliases referring to enum values (e.g., `patterns disruption`) still work since we kept Pattern.kind. But if you added kind-specific aliases (e.g., `elements product`), audit them for the new kinds.

## Validate

After every schema edit:

```bash
cd <slug>
omnigraph query lint --schema ./schema.pg --query ./queries/signals.gq
```

The queries themselves probably don't need changes — they mostly operate on slugs and don't reference enum values. Lint will flag anything that broke.

## Checklist

Before moving to Phase 6:

- [ ] Copied `industry-intel/` to `<slug>/`
- [ ] Updated `Element.kind` enum
- [ ] Updated `domain` enum (on both Signal and Element)
- [ ] Updated `Company.type` enum
- [ ] Updated `SourceType` enum if needed
- [ ] Updated `ArtifactType` enum if needed
- [ ] Replaced kind-specific Element properties
- [ ] Kept Pattern.kind as-is (usually)
- [ ] Updated `omnigraph.yaml` project name + graph URI
- [ ] Deleted `industry-intel`'s `seed.jsonl` from the new folder (will regenerate in Phase 6)
- [ ] `query lint` passes with 0 errors
