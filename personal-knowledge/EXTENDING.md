# EXTENDING — schema overlays for personal-knowledge

The cookbook ships a lean spine. For richer domain modeling, paste the relevant snippet into your `schema.pg` on a branch (workflow below). Each overlay is self-contained: its nodes and edges reference spine types but do not modify them.

The overlays here are pulled from the Life Graph reference ontology (~39 nodes / ~140 edges). The four bundled below cover the most common extension axes; for everything else, copy directly from the reference.

Verified against Omnigraph 0.4.2 on 2026-05-11: each overlay applies cleanly via `omnigraph init --schema <spine+overlay.pg>` and the spine queries continue to work. No example queries or seed are shipped per overlay — write yours to fit your data.

## Workflow (always)

```bash
# 1. Branch
omnigraph branch create --from main <overlay-slug>-overlay $REPO

# 2. Append the snippet below to schema.pg, then:
omnigraph schema diff $REPO

# 3. Review with the user, then apply to the branch:
omnigraph schema apply --branch <overlay-slug>-overlay $REPO

# 4. Once confirmed, merge:
omnigraph branch merge <overlay-slug>-overlay --into main $REPO
```

Always go through a branch. Schema changes to `main` are not reversible cleanly.

---

## Overlay 1 — Health

For tracking labs, vitals, conditions, interventions, genetic data. Useful if you've ever had a doctor share a PDF and you want to extract the data into a queryable shape.

Drop into `schema.pg` after the spine sections.

```pg
// ──────────────────────────────────────────────
// Health overlay
// ──────────────────────────────────────────────

node HealthRecord {
    slug: String @key
    name: String @index
    kind: enum(lab-report, imaging-report, clinic-letter, test-request, prescription, appointment-letter, insurance-document, genetic-report, wearable-export, self-report, other) @index
    provider: String? @index
    facility: String?
    clinician: String?
    collected_at: DateTime? @index
    received_at: DateTime?
    reported_at: DateTime? @index
    document_date: DateTime? @index
    extraction_status: enum(raw, extracted, reviewed, failed)? @index
    extraction_confidence: F32?
    notes: String?
    createdAt: DateTime
    updatedAt: DateTime
}

node Measurable {
    slug: String @key
    name: String @index
    kind: enum(lab-analyte, vital, symptom, imaging-finding, body-composition, fitness, sleep, genetic-marker, clinical-score, other) @index
    category: String? @index
    canonical_unit: String?
    aliases: [String]?
    description: String?
    createdAt: DateTime
    updatedAt: DateTime
}

node Measurement {
    slug: String @key
    measured_at: DateTime @index
    value_num: F64?
    value_text: String?
    unit: String?
    flag: enum(low, normal, high, critical, abnormal, positive, negative, equivocal, unknown)? @index
    reference_low: F64?
    reference_high: F64?
    optimal_low: F64?
    optimal_high: F64?
    specimen: enum(blood, serum, plasma, urine, stool, saliva, tissue, breath, sensor, imaging, self-report, other)? @index
    method: String?
    fasting: Bool?
    panel: String? @index
    notes: String?
    extraction_confidence: F32?
    createdAt: DateTime
    updatedAt: DateTime
}

node Condition {
    slug: String @key
    name: String @index
    category: String? @index
    description: String?
    createdAt: DateTime
    updatedAt: DateTime
}

node ConditionOccurrence {
    slug: String @key
    name: String @index
    status: enum(suspected, active, resolved, ruled-out, historical) @index
    certainty: enum(self-reported, clinician-suspected, probable, confirmed, ruled-out)? @index
    onset_at: DateTime?
    diagnosed_at: DateTime? @index
    resolved_at: DateTime?
    severity: enum(mild, moderate, severe, critical)?
    notes: String?
    createdAt: DateTime
    updatedAt: DateTime
}

node Intervention {
    slug: String @key
    name: String @index
    kind: enum(medication, supplement, diet, exercise, sleep, behavioral, procedure, diagnostic, other) @index
    status: enum(planned, active, paused, stopped, completed) @index
    dose: String?
    frequency: String?
    started_at: DateTime? @index
    stopped_at: DateTime?
    reason: String?
    notes: String?
    createdAt: DateTime
    updatedAt: DateTime
}

edge HealthRecordForPerson: HealthRecord -> Person @card(1..1)
edge HealthRecordFromArtifact: HealthRecord -> Artifact @card(1..1)
edge MeasurementForPerson: Measurement -> Person @card(1..1)
edge MeasurementOf: Measurement -> Measurable @card(1..1)
edge MeasurementInRecord: Measurement -> HealthRecord
edge OccurrenceForPerson: ConditionOccurrence -> Person @card(1..1)
edge OccurrenceOfCondition: ConditionOccurrence -> Condition @card(1..1)
edge OccurrenceFromRecord: ConditionOccurrence -> HealthRecord
edge InterventionForPerson: Intervention -> Person @card(1..1)
edge InterventionForCondition: Intervention -> Condition
edge InterventionForOccurrence: Intervention -> ConditionOccurrence
edge MeasurementAfterIntervention: Measurement -> Intervention
```

---

## Overlay 2 — Financing

For founders raising or angels investing — tracks rounds, instruments (SAFEs, notes, equity), and investor profiles.

```pg
// ──────────────────────────────────────────────
// Financing overlay
// ──────────────────────────────────────────────

node FinancingRound {
    slug: String @key
    name: String @index
    company_name: String @index
    kind: enum(pre-seed, seed, bridge, extension, other) @index
    status: enum(active, closed, canceled, historical) @index
    opened_at: Date?
    closed_at: Date?
    currency: String?
    brief: String?
    createdAt: DateTime
    updatedAt: DateTime
}

node FinancingInstrument {
    slug: String @key
    source: enum(mercury, manual, carta, pully, other) @index
    source_id: String? @unique
    kind: enum(safe, convertible-note, equity, warrant, other) @index
    status: enum(draft, owner-signed, investor-signed, signed-unpaid, paid, canceled, expired) @index
    investment_amount: F64 @index
    currency: String?
    investment_date: Date? @index
    paid_at: DateTime?
    valuation_cap: F64?
    valuation_type: enum(pre-money, post-money)?
    discount_rate: F64?
    includes_mfn: Bool?
    includes_pro_rata: Bool?
    investor_legal_name: String @index
    document_url: String?
    brief: String?
    createdAt: DateTime
    updatedAt: DateTime
}

node InvestorProfile {
    slug: String @key
    name: String @index
    investor_type: enum(individual, angel, venture-fund, syndicate, company, family-office, other) @index
    status: enum(active, historical, canceled, prospect) @index
    brief: String?
    tags: [String]?
    createdAt: DateTime
    updatedAt: DateTime
}

edge FinancingRoundForOrganization: FinancingRound -> Organization @card(1..1)
edge InstrumentInRound: FinancingInstrument -> FinancingRound
edge InstrumentForOrganization: FinancingInstrument -> Organization @card(1..1)
edge InstrumentInvestorPerson: FinancingInstrument -> Person
edge InstrumentInvestorOrganization: FinancingInstrument -> Organization
edge InvestorProfileForPerson: InvestorProfile -> Person
edge InvestorProfileForOrganization: InvestorProfile -> Organization
edge InvestorProfileInvestsInOrganization: InvestorProfile -> Organization
edge InstrumentFromArtifact: FinancingInstrument -> Artifact
```

---

## Overlay 3 — Inspiration & Interest

For curating taste — what someone likes, what's useful for a project, what a brand vibe is. Doubles as gift-memory.

```pg
// ──────────────────────────────────────────────
// Inspiration & Interest overlay
// ──────────────────────────────────────────────

node Interest {
    slug: String @key
    name: String @index
    polarity: enum(love, like, curious, dislike, avoid) @index
    category: enum(brand, food, drink, place, activity, media, fashion, sport, gift, aesthetic, travel, music, book, film, health, product, person, other) @index
    brief: String?
    notes: String?
    confidence: enum(low, medium, high)? @index
    source: enum(whatsapp, email, calendar, observation, manual, gift-history, web, other)? @index
    observed_at: DateTime? @index
    tags: [String]?
    createdAt: DateTime
    updatedAt: DateTime
}

node Inspiration {
    slug: String @key
    name: String @index
    kind: enum(brand, agency, product, campaign, website, app, space, object, outfit, photo, article, person, place, media, other) @index
    affinity: enum(love, like, curious, reject)? @index
    brief: String?
    notes: String?
    captured_at: DateTime? @index
    tags: [String]?
    createdAt: DateTime
    updatedAt: DateTime
}

edge InterestOfPerson: Interest -> Person @card(1..1)
edge InterestForPerson: Interest -> Person
edge InterestForOrganization: Interest -> Organization
edge InterestForPlace: Interest -> Place
edge InterestFromArtifact: Interest -> Artifact
edge InterestUsefulForProject: Interest -> Project
edge InspirationForPerson: Inspiration -> Person
edge InspirationForProject: Inspiration -> Project
edge InspirationForArea: Inspiration -> Area
edge InspirationForGoal: Inspiration -> Goal
edge InspirationFromArtifact: Inspiration -> Artifact
edge RelatedInspiration: Inspiration -> Inspiration {
    relation: enum(similar, contrast, evolution, component, vibe, alternative)?
}
```

---

## Overlay 4 — Frames & Personas

For sales, positioning, content strategy — typed messaging atoms.

```pg
// ──────────────────────────────────────────────
// Frames & Personas overlay
// ──────────────────────────────────────────────

node AudiencePersona {
    slug: String @key
    name: String @index
    kind: enum(individual, archetype, organization, segment) @index
    brief: String?
    pains: [String]?
    values: [String]?
    proof_points: [String]?
    objections: [String]?
    tags: [String]?
    createdAt: DateTime
    updatedAt: DateTime
}

node PositioningFrame {
    slug: String @key
    name: String @index
    status: enum(draft, active, tested, worked, failed, retired) @index
    thesis: String @index
    lead_with: String?
    emphasize: [String]?
    avoid: [String]?
    evidence: String?
    tags: [String]?
    createdAt: DateTime
    updatedAt: DateTime
}

node NarrativeFrame {
    slug: String @key
    name: String @index
    audience: enum(investor, customer, partner, candidate, internal, press, general) @index
    form: enum(one-liner, opener, thirty-sec, two-min, deep-dive, objection-answer, category, why-now, why-us, wedge, deck, memo, website, demo) @index
    status: enum(draft, testing, active, canonical, worked, failed, retired) @index
    angle: String? @index
    one_liner: String?
    body: String?
    bullets: [String]?
    objections: [String]?
    proof_points: [String]?
    avoid: [String]?
    evidence: String?
    tags: [String]?
    createdAt: DateTime
    updatedAt: DateTime
}

edge PersonaForPerson: AudiencePersona -> Person
edge PersonaForOrganization: AudiencePersona -> Organization
edge FrameForPersona: PositioningFrame -> AudiencePersona
edge FrameForPerson: PositioningFrame -> Person
edge FrameForProject: PositioningFrame -> Project
edge NarrativeForOrganization: NarrativeFrame -> Organization
edge NarrativeForProject: NarrativeFrame -> Project
edge NarrativeForPersona: NarrativeFrame -> AudiencePersona
edge NarrativeForPerson: NarrativeFrame -> Person
edge NarrativeUsesFrame: NarrativeFrame -> PositioningFrame
edge NarrativeWorkedForPerson: NarrativeFrame -> Person {
    outcome: enum(worked, partial, failed)?
    evidence: String?
    observed_at: DateTime?
}
```

---

## Heavier overlays (not bundled here)

For these, spin up a dedicated cookbook (or extend Life-Graph reference yourself):

- **RelationshipIntent** — sophisticated relationship-priority modeling.
- **HabitCompletion** — daily-level quantified-self log.
- **WritingStyle** — voice analysis nodes.
- **ExternalCode** (LOINC/SNOMED/ICD/RxNorm/HGNC/...) — clinical-grade identifiers.
- **GeneticVariant** — genetic-testing data tied to the Health overlay.
- **Feed** + **Media** — RSS/podcast/book hobby tracking.

The Life Graph reference at the user's discretion includes all of these; copying them is fine if the user has the appetite.
