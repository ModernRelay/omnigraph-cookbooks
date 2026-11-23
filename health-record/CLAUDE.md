# CLAUDE.md — health-record

Scoped guidance for the `health-record/` cookbook. Repo-wide conventions
live in `../CLAUDE.md`. For general OmniGraph operations use the **omnigraph**
skill; this file covers only what is specific to this cookbook.

## What This Is

One person's health record as one typed graph: the documents they received,
the results read from them, device readings, targets, hypotheses, what they
take, the vaccine doses they were given and what is due next. Latest, out of
range, off target, overdue and incomplete are derived by stored queries on
every read, never stored. Schema, seed, queries and policies; no application
code and no connectors. The seed is an invented person, "Noa Brandt"; every
name, date, value, lot number and product is made up.

The record keeps and surfaces facts. It does not diagnose.

## Key Files

- `schema.pg` — 16 node types, 39 edge types.
- `queries/record.gq` — 47 stored reads.
- `queries/mutations.gq` — 52 stored writes; updates re-check their state.
- `seed.jsonl` / `seed.md` — reference seed. Keep them in sync; `seed.md`
  lists what each read must return on the fresh seed.
- `policies/graph.policy.yaml` — reader, writer, admin and `act-agent` roles.

## Rules

- Graph id `health`. Stored queries and parameters:
  `omnigraph queries list --target local --graph health`.
- Do not add stored status fields for anything a query derives: no "latest",
  "off target", "overdue" or "series complete" flags. Extend the query.
- A record is written once. Each kind of record has one owner edge left
  unkeyed (`MeasurementFor`, `RecordFor`, `ImmunizationFor`, `NotificationFor`
  and the like), so a write on a slug that exists adds a second edge, breaks
  its `@card(1..1)` and is refused with nothing changed. Do not add a `@key`
  to those edges. Catalogue nodes (`Person`, `Organization`, `Measurable`,
  `Condition`, `ExternalCode`) are replaced by an insert on their slug.
- Never overwrite a reported value. A correction goes in with
  `correct_result`, which adds a result with status `amended` that supersedes
  the old one. A result filed by mistake is voided with `void_result`.
- A current result is one not entered in error and not superseded by a
  standing correction, directly or through a chain of up to eight. A
  correction that was itself voided hides nothing. Every read of results, and
  every read of a hypothesis's evidence, applies that rule; change them
  together.
- A result at a detection limit has a `comparator`. `out_of_range`,
  `off_target` and `targets` flag it only where the limit settles it: `lt` at
  or under the floor, `gt` at or over the ceiling. Keep that rule in all
  three; `detection_limit_results` lists the ones it leaves open.
- Copy a result as the document printed it: value, unit, reference range and
  flag, with the whole printed line in `source_line`. `canonical_value` is the
  value in the marker's `canonical_unit`. Set it only when the units match or
  the conversion is certain; `off_target` and `targets` compare it, so a
  result without one cannot be judged.
- Reference ranges and flags are the source's own. `out_of_range` compares a
  result with the range printed beside it; `off_target` compares it with the
  person's `Target`. They answer different questions; keep both.
- One `Immunization` per dose. A combined vaccine is one node with one
  `ProtectsAgainst` link per disease, each with its own `dose_number`. A
  booster outside a fixed series has no `series_doses`.
- A `Recommendation` records what an authority said is due. Do not compute
  one from a schedule. Whether it is met is derived: it is still due while
  its status is `open` and no result that stands and no given dose fulfils
  it. `fulfil_with_result` and `fulfil_with_dose` only add the link; do not
  set `done` for a recommendation that a result or dose met.
- An `Intervention` holds what does not change: its markers, its hypothesis
  and its dates. Each dose and frequency is an `InterventionEpisode`, and the
  current dose is the latest episode's. Do not put a dose on the
  intervention or start a second intervention for a dose change.
- A `Hypothesis` status is a person's or a clinician's verdict. An agent
  passes `review_status` `ai_generated` and never runs `decide_hypothesis`.
  An agent records a `ConditionOccurrence` only when a document or the person
  states it.
- `act-agent` writes only on unprotected branches and cannot merge or delete
  a branch. The shared checker asserts this; do not widen the agent rules.
- A wearable contributes one summary per marker per day or night, with
  `period_start` and a `statistic`. Do not load raw samples.
- Keep the seed fictional: invented people, organizations, products,
  manufacturers and lot numbers. Codes come from public systems and were
  checked against them (see `seed.md`); check any code you add the same way.
  Do not add SNOMED CT content.
- After a schema, query or seed change, re-run the reads against a fresh seed
  and update `seed.md`, then run `../scripts/check-cookbooks.py`.

## Running it

Use the shared [local setup](../docs/local-setup.md) with folder
`health-record` and graph `health`, and load `seed.jsonl`. Its four targets
are the roles used below: `local` (admin), `local-writer` for the person whose
record it is, `local-reader`, and `local-agent` for an AI agent.

The answers the README promises, as commands. `seed.md` lists what each
returns on the fresh seed:

```bash
omnigraph query off_target --target local-reader --graph health
omnigraph query intervention_effect --target local-reader --graph health --params '{"intervention":"int-rosuvastatin"}'
omnigraph query incomplete_series --target local-reader --graph health
omnigraph query overdue_recommendations --target local-reader --graph health
omnigraph query contested_hypotheses --target local-reader --graph health
```

Merge the `aliases:` of [`omnigraph-config.example.yaml`](omnigraph-config.example.yaml)
into `$OMNIGRAPH_HOME/config.yaml` for a short name per read, such as
`omnigraph alias off-target` or
`omnigraph alias effect --params '{"intervention":"int-rosuvastatin"}'`.

## Derived reads

Every status is a stored read, never a stored field:

| Question | Stored query |
|---|---|
| Where does each marker stand? | `latest_results`, `marker_history` |
| What is outside the lab's own range? | `out_of_range` |
| What is outside my target? | `off_target`, `targets` |
| What still needs a person's check? | `records_awaiting_review`, `hypotheses_awaiting_review`, `preliminary_results` |
| What cannot be judged yet? | `unconverted_results`, `detection_limit_results` |
| What did a source correct? | `corrected_results` |
| What is due, what is late, and what was met? | `open_recommendations`, `overdue_recommendations`, `met_by_result`, `met_by_dose` |
| What has no retest planned? | `targets_without_retest`, `interventions_without_followup` |
| Did a change work, and at which dose? | `intervention_effect`, `dose_history`, `active_interventions` |
| Which explanations are in doubt? | `contested_hypotheses`, `hypotheses_without_evidence`, `hypothesis_support`, `hypothesis_contradiction` |
| Where do I stand on each vaccine? | `doses_by_disease`, `disease_doses`, `incomplete_series`, `immunization_history` |
| Which doses rest on memory, or were skipped? | `undocumented_doses`, `doses_not_given` |
| Was I given a recalled lot? | `doses_by_lot` |
| What reactions have I had? | `reactions`, `dose_reactions`, `intervention_reactions` |
| Who has been told what? | `notification`, `unacknowledged_notifications`, `overdue_not_notified` |

## Workflows

The person runs these as `local-writer`; an agent runs them as `local-agent`
on a branch. Every read also works as `local-reader`.

### Report intake, on a branch

An agent files the document, reads each result as printed and leaves the
branch for review. It cannot write `main`:

```bash
omnigraph access --target local-agent --graph health --branch main
omnigraph branch create intake-lab-2026-11 --target local-agent --graph health
omnigraph mutate file_record --target local-agent --graph health --branch intake-lab-2026-11 --params '{
  "slug":"rec-lab-2026-11","title":"Northbank blood panel, November 2026","kind":"lab_report",
  "document_date":"2026-11-17","person":"per-noa"}'
omnigraph blob put node HealthRecord rec-lab-2026-11 file --file panel-2026-11.pdf \
  --target local-agent --graph health --branch intake-lab-2026-11
omnigraph mutate record_result --target local-agent --graph health --branch intake-lab-2026-11 --params '{
  "slug":"m-2026-11-tsh","marker":"mk-tsh","person":"per-noa","record":"rec-lab-2026-11",
  "measured_at":"2026-11-16T08:10:00.000Z","value":2.4,"unit":"mIU/L","canonical_value":2.4,
  "reference_low":0.4,"reference_high":4.0,"flag":"normal","status":"final",
  "source_name":"TSH","source_line":"TSH 2.4 mIU/L (0.4-4)"}'
omnigraph mutate mark_extracted --target local-agent --graph health --branch intake-lab-2026-11 --params '{"slug":"rec-lab-2026-11"}'
```

Search before adding a marker (`search_markers`): the same analyte is printed
under several names, and those belong in `aliases`. A result printed in
another unit goes in without `canonical_value`; it then shows in
`unconverted_results`.

The person reviews the branch against the file and merges it:

```bash
omnigraph query record_results --target local-writer --graph health --branch intake-lab-2026-11 --params '{"record":"rec-lab-2026-11"}'
omnigraph blob get node HealthRecord rec-lab-2026-11 file --out panel-2026-11.pdf \
  --target local-writer --graph health --branch intake-lab-2026-11
omnigraph branch diff intake-lab-2026-11 --target local-writer --graph health
omnigraph branch merge intake-lab-2026-11 --into main --dry-run --target local-writer --graph health
omnigraph branch merge intake-lab-2026-11 --into main --target local-writer --graph health
omnigraph mutate mark_reviewed --target local-writer --graph health --params '{"slug":"rec-lab-2026-11"}'
```

`record_results` puts each value beside its `source_line`, which is what makes
the check quick. `mark_reviewed` is the person's step. Before merging, read
the branch's commits for steps that are a person's: `mark_reviewed`,
`decide_hypothesis`, `acknowledge_notification`.

### Closing what a result or a dose meets

```bash
omnigraph mutate fulfil_with_result --target local-writer --graph health --params '{"slug":"rcm-tsh-2026","result":"m-2026-11-tsh"}'
```

`fulfil_with_result` and `fulfil_with_dose` link what met the recommendation.
It stops being due while that result or dose stands, and is due again if it
is later voided. Where the recommendation repeats (`repeats_every_days`),
raise the next one with `recommend_retest`. `close_recommendation` is for a
person closing one as declined, superseded, or done with nothing on record.

### Corrections and units

```bash
omnigraph mutate correct_result --target local-agent --graph health --branch intake-amended --params '{
  "slug":"m-p2-ferritin-corrected-2","replaces":"m-p2-ferritin-corrected","marker":"mk-ferritin","person":"per-noa",
  "record":"rec-lab-2025-07-amended","measured_at":"2025-07-21T08:10:00.000Z","value":35,"unit":"ug/L",
  "canonical_value":35,"reference_low":30,"reference_high":300,"flag":"normal",
  "source_line":"Ferritin (corrected) 35 ug/L (30-300)"}'
omnigraph query unconverted_results --target local-reader --graph health
omnigraph mutate set_canonical_value --target local-writer --graph health --params '{"slug":"m-p3-glucose","canonical_value":5.1}'
```

A conversion depends on the analyte: glucose in mg/dL divides by 18.02 to
give mmol/L, and cholesterol by 38.67. The graph does not convert; the agent
states the factor it used in the commit it proposes.

### Readings from a device

```bash
omnigraph mutate record_reading --target local-agent --graph health --branch sync-2026-11 --params '{
  "slug":"m-night-2026-11-03-rhr","marker":"mk-rhr","person":"per-noa",
  "measured_at":"2026-11-03T06:30:00.000Z","period_start":"2026-11-02T22:30:00.000Z",
  "statistic":"mean","value":54,"unit":"/min","canonical_value":54,"device":"Tessel Band 2"}'
```

### Vaccinations

One dose, the diseases it counts towards, and the document that shows it:

```bash
omnigraph mutate record_dose --target local-agent --graph health --branch intake-vaccines --params '{
  "slug":"imm-hepb-3","vaccine":"Hepatitis B","lot_number":"B9001","administered_on":"2026-11-20",
  "date_precision":"day","site":"left_arm","route":"intramuscular","origin":"provider_record",
  "person":"per-noa","disease":"cond-hepatitis-b","dose_number":3,"series_doses":3}'
omnigraph mutate link_dose_record --target local-agent --graph health --branch intake-vaccines --params '{"dose":"imm-hepb-3","record":"rec-practice-vacc"}'
omnigraph query incomplete_series --target local-reader --graph health --branch intake-vaccines
omnigraph query doses_by_disease --target local-reader --graph health
omnigraph query disease_doses --target local-reader --graph health --params '{"disease":"cond-tetanus"}'
```

For a combined vaccine, run `add_dose_disease` once per further disease in
the same change, each with its own dose number. Use `origin` `recall` for a
dose the person remembers and no document shows, with the `date_precision`
that is honest. A dose that was due and not given goes in with
`record_dose_not_given`. What is due next goes in with `recommend_dose`, with
the authority that set the dates.

### Hypotheses and evidence

```bash
omnigraph mutate raise_hypothesis --target local-agent --graph health --branch evidence-2026-11 --params '{
  "slug":"hyp-tg-alcohol","title":"Triglycerides rose with more alcohol","thesis":"The July 2026 rise in triglycerides follows more drinking over the summer.",
  "person":"per-noa","marker":"mk-tg","review_status":"ai_generated","raised_on":"2026-11-20"}'
omnigraph mutate link_support --target local-agent --graph health --branch evidence-2026-11 --params '{"hypothesis":"hyp-tg-alcohol","result":"m-p4-tg"}'
omnigraph query contested_hypotheses --target local-reader --graph health
omnigraph mutate decide_hypothesis --target local-writer --graph health --params '{"slug":"hyp-apob-diet","status":"rejected"}'
```

`decide_hypothesis` is the person's or the clinician's step.

### A change of dose

```bash
omnigraph mutate change_dose --target local-writer --graph health --params '{
  "episode":"ep-rosuvastatin-2","intervention":"int-rosuvastatin","dose":"10 mg","frequency":"daily",
  "changed_at":"2026-11-20T07:00:00.000Z","reason":"LDL cholesterol still above target."}'
omnigraph query dose_history --target local-reader --graph health
omnigraph query active_interventions --target local-reader --graph health
```

The intervention keeps its markers, so `intervention_effect` and
`interventions_without_followup` go on working across the change. A new
intervention goes in with `start_intervention`, which writes its first dose
period, and `add_intervention_marker` for each further marker.

### Follow-up check

```bash
omnigraph query interventions_without_followup --target local-reader --graph health
omnigraph query targets_without_retest --target local-reader --graph health
omnigraph mutate recommend_retest --target local-agent --graph health --branch followup-2026-11 --params '{
  "slug":"rcm-tg-2026-11","title":"Triglycerides three months after starting omega-3","authority":"Proposed by the agent, for Dr Ilse Vermeer to confirm",
  "due_at":"2026-11-30T00:00:00.000Z","person":"per-noa","marker":"mk-tg"}'
```

An agent's proposed retest names itself as the authority until a clinician
confirms it.

### Reminders

A prompt goes out through the agent's own tools. The record notes it, so it is
not sent twice:

```bash
omnigraph query overdue_not_notified --target local-agent --graph health
omnigraph query notification --target local-agent --graph health --params '{"slug":"ntf-overdue-rcm-flu-2026"}'
omnigraph mutate raise_notification --target local-agent --graph health --branch reminders-2026-11 --params '{
  "slug":"ntf-overdue-rcm-flu-2026","title":"Influenza dose is overdue","kind":"dose_due",
  "person":"per-noa","recommendation":"rcm-flu-2026"}'
omnigraph mutate mark_sent --target local-agent --graph health --branch reminders-2026-11 --params '{"slug":"ntf-overdue-rcm-flu-2026","channel":"email"}'
omnigraph mutate acknowledge_notification --target local-writer --graph health --params '{"slug":"ntf-overdue-rcm-tsh-2026"}'
```

Build the slug from the kind and the thing it is about. Raising a slug that
exists is refused, whatever its status, so a prompt the person acknowledged
or dismissed is not raised again; `overdue_not_notified` counts any
notification about a recommendation as told. The notification reaches `main`
when the person merges the branch; until then `overdue_not_notified` on
`main` still lists the item. An agent that sends before the merge keeps to
one reminders branch and reads that branch.

### Before a visit

```bash
omnigraph query upcoming_visits --target local-reader --graph health
omnigraph query off_target --target local-reader --graph health
omnigraph query overdue_recommendations --target local-reader --graph health
omnigraph query contested_hypotheses --target local-reader --graph health
omnigraph query active_interventions --target local-reader --graph health
```

The agent drafts the questions from these; the person takes them along.
After the visit, record what the clinician saw:

```bash
omnigraph commit list --target local-writer --graph health --json        # the newest commit is first
omnigraph mutate complete_visit --target local-writer --graph health --params \
  '{"slug":"vis-2027-01-25","summary":"...","commit":"<COMMIT_ID>"}'
omnigraph query off_target --target local-reader --graph health --snapshot <COMMIT_ID>
```

### Agents over MCP

`omnigraph mcp` relays an agent host's MCP over stdio to the server through a
registered target, so the token never enters the agent's configuration:

```json
{"command": "omnigraph", "args": ["mcp", "--target", "local-agent", "--graph", "health"],
 "env": {"OMNIGRAPH_HOME": "/Users/you/.omnigraph-cookbooks", "OG_LOCAL_AGENT_TOKEN": "local-agent-token"}}
```

Each stored read is a call to the `query` tool. Add `--write` to the bridge
for the write tools; the graph policy still refuses `act-agent` on `main`.

## Extending

- Add a `Device` node if several devices measure the same marker and you want
  to compare them; today the device is a string on the result.
- Add an `Encounter`-style link from a result to the visit it was taken at.
- Add your own markers with `add_marker`, and a code for each with
  `add_marker_code`.
- For a household, add each person with `add_person`. Every read returns the
  person, so results stay apart in the answers. See the limit below.

Change the schema with `cluster plan` and `cluster apply` against the running
server, as in [live updates](../docs/local-setup.md#live-updates).

## What it does not do

- It does not diagnose, interpret a result or give medical advice. Ranges and
  flags are the source's; targets and verdicts are a person's.
- No connectors and no automatic sync. Documents arrive as files, and an
  agent or a script writes what it reads through the stored mutations.
- It does not convert units. A result without `canonical_value` is left out
  of `off_target`.
- It does not compute vaccination schedules or say which dose is due. It
  stores recommendations with the authority that made them. `incomplete_series`
  only compares the highest dose number with the series length recorded.
- It does not check that a dose is valid: the minimum interval between doses,
  the age at the dose or an expired lot.
- It holds one summary a day per marker from a wearable, not raw samples.
- It has no log of each tablet taken. An `Intervention` says what is taken and
  since when.
- The policy cannot keep one person's data from a reader who may read the
  graph. Give each person their own graph for that.
- The policy cannot say which stored query an agent runs on its branch. Every
  commit records its actor; the review before a merge is the check.
- A notification is one node with its latest status. It does not keep each
  send attempt, and a dismissed one cannot be raised again under the same
  slug: a reminder that should repeat needs a slug with its date in it.
- The written-once rule covers records, not the catalogue: `add_person`,
  `add_organization`, `add_marker` and `add_condition` replace an existing
  slug.
- Supersession is followed through at most eight corrections of one result.
- Files are stored as the graph stores everything else. The cookbook adds no
  encryption of its own: protect the disk or the bucket.
- Reads that compare a date with today (`overdue_recommendations`,
  `overdue_not_notified`, `upcoming_visits`) change as time passes.
- The seed carries no SNOMED CT or ICD codes, and not every marker has a
  LOINC code.
