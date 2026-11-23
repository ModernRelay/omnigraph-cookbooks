# Seed: Noa Brandt

`seed.jsonl` describes **Noa Brandt**, an invented person born in 1988, over
two years of looking after their health. Every name, date, value, lot number
and product is made up. The seed is shaped so that each stored read has
something to find; the expected results below are what the stored queries
return on a freshly loaded graph.

266 nodes and 551 edges. Load it once into an empty graph with
`--mode append`.

## The record

| Kind | Count | Notes |
|---|---|---|
| People | 3 | Noa and two clinicians |
| Organizations | 4 | A laboratory, a practice, a travel clinic and an imaging clinic |
| Visits | 5 | Four completed, one planned for January 2027 |
| Documents | 12 | Five lab reports (one an amended report), a body composition scan, two clinic letters and four vaccination records |
| Markers | 26 | 17 lab analytes, 3 vitals, 2 body composition figures, 3 nightly figures and a tiredness score |
| Results | 122 | 61 read from lab reports, 3 from the scan, 16 readings and scores, 42 nightly summaries from a wrist tracker |
| Codes | 20 | 14 LOINC codes for markers and 6 CVX codes for vaccines |
| Targets | 5 | Four active, one retired |
| Hypotheses | 5 | Three reviewed by a person, two proposed by an agent |
| Conditions | 17 | 12 diseases vaccines protect against, 2 diagnoses, 3 kinds of reaction |
| Cases and reactions | 5 | Raised cholesterol, a resolved vitamin D deficiency and three reactions |
| Interventions | 5 | Diet, vitamin D3, iron, rosuvastatin and omega-3 |
| Dose periods | 7 | One each, and a second for vitamin D3 and for iron |
| Vaccine doses | 19 | 18 given and 1 not given |
| Recommendations | 8 | Three overdue, one due in 2034, three met by a result or a dose, one closed by hand |
| Notifications | 3 | One sent, two acknowledged |

The story runs from a check-up in January 2025. ApoB and LDL cholesterol were
raised, and vitamin D and ferritin were low. Noa changed diet and started
vitamin D and iron. A year later ApoB was still above target, so rosuvastatin
was started in February 2026 and the LDL target was tightened. The July 2026
panel shows ApoB at target and LDL cholesterol not yet.

Five things are placed in the results on purpose:

- **A correction.** The July 2025 ferritin was reported as 43 and corrected
  to 34 in an amended report. Both results are in the seed; only the
  correction counts as current.
- **A value in another unit.** The January 2026 glucose was printed as
  92 mg/dL. It has no canonical value, so it cannot be judged against a
  target until someone converts it.
- **A result entered in error.** A weight of 731 kg typed at the January 2026
  visit is marked `entered_in_error` and is left out of every read.
- **A preliminary result.** The July 2026 Lp(a) has not been made final.
- **A result at a detection limit.** The July 2026 hs-CRP was printed as
  "<0.3 mg/L": comparator `lt`, value 0.3. It is under the lab's ceiling of
  3.0 whatever the true value, so it is not out of range.

Recommendations show what "met" means. Three have a result or a dose linked
as fulfilling them and keep the status `open`: they are no longer due because
that evidence stands, and would be due again if it were voided. One, a dental
check-up with no document on record, was closed by hand as `done`.

The vaccination history shows what a per-disease dose number is for. The 2024
Tdap-IPV booster is the sixth dose against tetanus, diphtheria and polio and
the fifth against pertussis, because the 2004 booster had no pertussis part.
Hepatitis B stopped after two of three doses. The second MMR dose is
remembered, with only its year, and no document shows it.

Two interventions changed dose. Vitamin D3 went from 1000 IU to 2000 IU, and
iron from daily to every other day after constipation. Each is one
intervention with two dose periods.

## Codes

The LOINC codes were checked against the LOINC search service and the CVX
codes against the CDC's CVX table when the seed was written. Check a code
again before you rely on it. Twelve markers carry no code. The seed has no
SNOMED CT or ICD codes.

This material contains content from LOINC (http://loinc.org). LOINC is
copyright Regenstrief Institute, Inc. and the Logical Observation Identifiers
Names and Codes (LOINC) Committee and is available at no cost under the
license at http://loinc.org/license.

## Expected results

Reads that compare a date with today change as time passes:
`overdue_recommendations` and `overdue_not_notified` gain the tetanus booster
in 2034, and `upcoming_visits` is empty after 25 January 2027.

### Results

| Stored read | With | Rows | Returns |
|---|---|---|---|
| `latest_results` |  | 26 | One row per marker |
| `out_of_range` |  | 2 | Triglycerides 1.9 mmol/L (lab limit 1.7) and anti-HBs 6 IU/L (lab minimum 10) |
| `off_target` |  | 2 | LDL cholesterol 2.1 against 1.8 or less; vitamin D 71 against 75 to 125 |
| `targets` |  | 4 | ApoB, LDL cholesterol, systolic blood pressure and vitamin D; two are off target |
| `marker_history` | `mk-apob` | 4 | ApoB 1.15, 1.08, 1.02, 0.72 g/L |
| `record_results` | `rec-lab-2026-07` | 14 | The fourteen results of the July 2026 panel, each with its printed line |
| `records_awaiting_review` |  | 2 | The July 2026 panel (extracted) and the August 2026 letter (raw) |
| `unconverted_results` |  | 1 | January 2026 glucose, printed as 92 mg/dL |
| `corrected_results` |  | 1 | July 2025 ferritin, corrected from 43 to 34 |
| `preliminary_results` |  | 1 | July 2026 Lp(a), 41 nmol/L |
| `detection_limit_results` |  | 1 | July 2026 hs-CRP, printed as <0.3 mg/L |

### Markers and codes

| Stored read | With | Rows | Returns |
|---|---|---|---|
| `markers` |  | 26 |  |
| `marker_codes` |  | 14 | LOINC codes for 14 markers |
| `search_markers` | `cholesterol` | 3 | LDL, HDL and total cholesterol |
| `unmeasured_markers` |  | 0 | Every marker has a result |

### What is due

| Stored read | With | Rows | Returns |
|---|---|---|---|
| `open_recommendations` |  | 4 | The three overdue ones and the 2034 tetanus booster |
| `overdue_recommendations` |  | 3 | Hepatitis B third dose (2023-11-08), TSH retest (2026-07-31), influenza 2026 (2026-10-31) |
| `targets_without_retest` |  | 4 | ApoB, LDL cholesterol, systolic blood pressure and vitamin D: no retest is still due for any of them |
| `overdue_not_notified` |  | 1 | The influenza dose; the other two overdue items already have a notification |
| `met_by_result` |  | 2 | The 2025 TSH repeat, met late by the January 2026 result, and the lipid panel, met by July 2026 |
| `met_by_dose` |  | 1 | The second hepatitis A dose |

### Immunizations

| Stored read | With | Rows | Returns |
|---|---|---|---|
| `immunization_history` |  | 19 | Nineteen entries from 1988 to 2026 |
| `doses_by_disease` |  | 12 | Twelve diseases; tetanus has six doses, pertussis five |
| `incomplete_series` |  | 1 | Hepatitis B, two of three doses |
| `undocumented_doses` |  | 1 | The second MMR dose, known from recall only |
| `doses_not_given` |  | 1 | Influenza 2026, deferred because of a fever |
| `doses_by_lot` | `B7745` | 2 | Both hepatitis B doses came from lot B7745 |
| `disease_doses` | `cond-tetanus` | 6 | Four childhood doses, the 2004 booster and the 2024 Tdap-IPV as dose six |
| `reactions` |  | 3 | Fever, a sore arm and constipation, all resolved |
| `dose_reactions` |  | 2 | Fever after the second COVID-19 dose; a sore arm after Tdap-IPV |
| `intervention_reactions` |  | 1 | Constipation on iron |

### Hypotheses

| Stored read | With | Rows | Returns |
|---|---|---|---|
| `hypotheses` |  | 5 |  |
| `hypothesis_support` | `hyp-apob-inherited` | 2 | January and July 2026 ApoB |
| `hypothesis_contradiction` | `hyp-fatigue-iron` | 2 | January 2026 ferritin and tiredness score |
| `contested_hypotheses` |  | 3 | The diet hypothesis (one result against it) and the iron hypothesis (two) |
| `hypotheses_without_evidence` |  | 1 | The late-training hypothesis an agent proposed |
| `hypotheses_awaiting_review` |  | 2 | Two an agent proposed |

### Interventions

| Stored read | With | Rows | Returns |
|---|---|---|---|
| `active_interventions` |  | 6 | Four interventions at their current dose; diet and rosuvastatin each target two markers |
| `intervention_effect` | `int-rosuvastatin` | 8 | ApoB and LDL cholesterol: three results before the start, one after |
| `interventions_without_followup` |  | 1 | Omega-3: no triglyceride result since it started |
| `dose_history` |  | 7 | Seven dose periods: vitamin D3 from 1000 IU to 2000 IU, iron from daily to every other day |
| `active_conditions` |  | 1 | Raised cholesterol, confirmed |

### Visits

| Stored read | With | Rows | Returns |
|---|---|---|---|
| `visits` |  | 5 | Four completed, one planned |
| `upcoming_visits` |  | 1 | The January 2027 check-up, until that date passes |
| `visit_records` | `vis-2026-01-26` | 2 | The January 2026 panel and letter |

### Notifications

| Stored read | With | Rows | Returns |
|---|---|---|---|
| `notification` | `ntf-overdue-rcm-tsh-2026` | 1 |  |
| `unacknowledged_notifications` |  | 1 | The TSH reminder, sent and not acknowledged |
