# Seed: two federal provisions through time

`seed.jsonl` records two provisions of United States federal law. Every word,
date and holding in it comes from one of 21 official documents, and each
`Source` row gives that document's URL, fetch time and SHA-256: the annual
editions of the United States Code from the Government Publishing Office, the
public laws as enacted, the United States Reports from the Library of Congress,
and the Law Revision Counsel's reclassification tables. All of them are works
of the United States Government and in the public domain.

`sources/build_seed.py` writes this file from those documents, which
`sources/documents.json` pins by hash, and checks each text, date and holding
against them. [README.md](README.md#rebuilding-the-seed-from-its-sources) shows
how to fetch them and rebuild.

79 nodes and 161 edges. Load it once into an empty graph with `--mode append`.

| Kind | Count | Notes |
|---|---|---|
| Laws | 8 | Five acts, a code title, the Federal Election Campaign Act, and the 2014 editorial reclassification |
| Provisions | 7 | Two sections, their subsections and paragraphs, and FECA § 301, the definitions section cited from them |
| Citations (`Designation`) | 16 | Code and act numbers, each with the interval it was in use |
| Text versions | 10 | Four for the corporate expenditure ban, six for the bankruptcy definitions |
| Changes | 8 | Each with its instruction, in-force date and the law's own words for that date |
| Judgments | 1 | *Citizens United v. FEC*, 558 U.S. 310 (2010) |
| Defined terms | 4 | |
| Coverage | 3 | What the graph records of each provision, and how |
| Sources | 21 | 11 code editions, 5 public laws, 1 court report, 2 codifier records, 2 title pages |

Text is stored without the unit's own number and with straight quotes, and
the codifier's footnote markers are removed. The record starts with the 2000
edition of the Code (current through 2 January 2001) and ends with the 2024
edition (current through 6 January 2025).

## The corporate expenditure ban

Section 316 of the Federal Election Campaign Act was added in 1976 as § 321
and renumbered § 316 in 1980. The Code printed it as 2 U.S.C. § 441b until
1 September 2014, when the Law Revision Counsel moved the campaign-finance
sections into a new Title 52; it is now 52 U.S.C. § 30118. Neither Title 2
nor Title 52 is enacted as positive law, so the Code's text is only prima facie
evidence of the law (1 U.S.C. § 204(a)) and the Act as enacted governs where
they differ. Each code `Designation` carries `positive_law: false`.

- **Subsection (a)**, the ban itself, is word for word the same in every
  edition from 2000 to 2024: one text version, open-ended.
- **Paragraph (b)(2)**, the meaning of "contribution or expenditure", has
  three versions. BCRA §§ 203 and 214 rewrote it, effective 6 November 2002.
  The 2014 reclassification changed only its cross-reference, from
  "section 431 of this title" to "section 30101 of this title". The Act itself
  says "section 301"; the Code translates. Both versions' `Cites` edges
  resolve to the same provision, FECA § 301.
- ***Citizens United*** read both texts and held "Section 441b's
  restrictions on corporate independent expenditures are therefore invalid
  and cannot be applied to Hillary" (558 U.S. at 365). The holding is on the
  section, scoped `in_part`. The Code still prints subsection (a) unchanged.

## The Subchapter V debtor

The Small Business Reorganization Act created Subchapter V of chapter 11,
including the definitions in 11 U.S.C. § 1182. Title 11 is enacted as
positive law, so its text is the law. Paragraph (1), the meaning of "debtor",
changed five times in five years:

| Version | In force | Text | Made by |
|---|---|---|---|
| `tv-usc11-1182-1-1` | 2020-02-19 to 2020-03-27 | a small business debtor | Pub. L. 116-54, effective 180 days after enactment |
| `tv-usc11-1182-1-2` | 2020-03-27 to 2022-03-27 | a person with debts up to $7,500,000 | CARES Act § 1113(a)(1), for cases commenced on or after 27 March 2020 |
| `tv-usc11-1182-1-3` | 2022-03-27 to 2022-06-21 | a small business debtor | The CARES sunset, moved from one year to two by Pub. L. 117-5 |
| `tv-usc11-1182-1-4` | 2022-06-21 to 2024-06-21 | a person with debts up to $7,500,000 | Pub. L. 117-151 § 2(d), reaching back to cases commenced on or after 27 March 2020 |
| `tv-usc11-1182-1-5` | from 2024-06-21 | a small business debtor | The sunset in Pub. L. 117-151 § 2(i) |

Versions 1, 3 and 5 have the same words, so they share one `text_sha256`. No
annual edition was current during version 3: the 2021 edition stops on
2 January 2022 and the 2022 edition prints version 4. Version 3 is recorded
from the sunset clause itself, and that change's `verification` is
`law_text`; every other change is confirmed by an official edition
(`official_version`). Paragraph (2), "debtor in possession", is unchanged
throughout.

## Expected results

What each stored read returns on a freshly loaded graph.

### Text on a date

| Read | Parameters | Rows |
|---|---|---|
| `text_on` | `11 U.S.C. § 1182(1)`, 2022-05-01 | `tv-usc11-1182-1-3`: "a small business debtor", in force 2022-03-27 to 2022-06-21, coverage 2019-08-23 to 2025-01-06 |
| `text_on` | `11 U.S.C. § 1182(1)`, 2021-01-15 | `tv-usc11-1182-1-2`, the $7,500,000 limit |
| `text_on` | `2 U.S.C. § 441b(b)(2)`, 2010-01-21 | `tv-feca-316-b-2-2`, the text *Citizens United* read |
| `text_on` | `2 U.S.C. § 441b(b)(2)`, 2020-01-01 | nothing: that citation has named nothing since 2014 |
| `text_on` | `52 U.S.C. § 30118(b)(2)` or `FECA § 316(b)(2)`, 2020-01-01 | `tv-feca-316-b-2-3` |
| `text_on` | `52 U.S.C. § 30118(a)`, 1995-06-01 | nothing: before the record starts (`coverage` says so) |
| `versions` | `11 U.S.C. § 1182(1)` | the five versions above, three distinct hashes |
| `version_sources` | `tv-usc11-1182-1-3` | Pub. L. 116-136 and Pub. L. 117-5 |

### Which law governs a past event

| Read | Parameters | Rows |
|---|---|---|
| `later_law_reaching_back` | `11 U.S.C. § 1182(1)`, 2022-05-01 | `chg-btatca-1182`: in force 2022-06-21, reaching cases from 2020-03-27 that were pending on enactment. A case filed on 1 May 2022 may be governed by version 4, not by the text in force when it was filed. |
| `later_law_reaching_back` | `11 U.S.C. § 1182(1)`, 2019-12-01 | nothing |
| `changes_to` | `52 U.S.C. § 30118(b)(2)` | BCRA § 203(a), BCRA § 214(d), the 2014 reclassification |
| `changes_to` | `11 U.S.C. § 1182(1)` | 6 rows for 5 changes: the CARES sunset appears twice, `made` by Pub. L. 116-136 and `modified` by Pub. L. 117-5 |
| `changes_between` | 2020-01-01 to 2023-01-01 | 5: the SBRA insertion (both paragraphs), the CARES substitution, the CARES sunset, the 2022 substitution |

### Citations and renumbering

| Read | Parameters | Rows |
|---|---|---|
| `citations` | `2 U.S.C. § 441b` | `FECA § 321` (1976–1980), `FECA § 316` (from 1980), `2 U.S.C. § 441b` (1976–2014), `52 U.S.C. § 30118` (from 2014) |
| `cited_as_on` | `2 U.S.C. § 441b(a)`, 2026-10-31 | `52 U.S.C. § 30118(a)`, `FECA § 316(a)` |
| `cited_as_on` | `2 U.S.C. § 441b`, 1978-01-01 | `FECA § 321`, `2 U.S.C. § 441b` |
| `citations_from` | `tv-feca-316-b-2-2` | "section 431 of this title", cited today as `52 U.S.C. § 30101` and `FECA § 301` |
| `renumberings` | | the 2014 reclassification, from `tv-feca-316-b-2-2` to `tv-feca-316-b-2-3` |

### Courts

| Read | Parameters | Rows |
|---|---|---|
| `held_invalid` | `2 U.S.C. § 441b` | *Citizens United*, `in_part`, 558 U.S. at 365, `human_reviewed` |
| `held_invalid` | `52 U.S.C. § 30118(a)` | nothing: the holding is on the section |
| `held_invalid_enclosing` | `52 U.S.C. § 30118(a)` | *Citizens United*, on `prov-feca-316` |
| `judgments_applying` | `52 U.S.C. § 30118(b)(2)` | *Citizens United*, which read `tv-feca-316-b-2-2` (in force 2002-11-06 to 2014-09-01) |
| `later_invalidations` | `558 U.S. 310` | nothing: no later judgment is recorded |
| `precedents_on_changed_text` | 2026-10-31 | *Citizens United*: it read `tv-feca-316-b-2-2`, which ended on 2014-09-01; `tv-feca-316-b-2-3` is in force |

### Defined terms

| Read | Parameters | Rows |
|---|---|---|
| `term_users` | `small business debtor` | versions 1, 3 and 5 of § 1182(1); the term is defined at 11 U.S.C. § 101(51D), outside this graph |
| `definition_reach` | `11 U.S.C. § 1182(1)`, 2026-10-31 | "debtor", used by § 1182(2) (`tv-usc11-1182-2-1`) |

### Search, sources, coverage and checks

| Read | Rows |
|---|---|
| `search_text` (`electioneering communication`) | the 2002 and 2014 texts of (b)(2) first; the pre-2002 text follows on "communications" |
| `laws` | 8 |
| `sources` | 21, every one `commercial_reuse: true` |
| `coverage` | 5 provisions: (a) and (b)(2) of § 316 and both paragraphs of § 1182 by `official_versions`, FECA § 301 by `designations_only` |
| `overlapping_versions`, `versions_without_source`, `changes_without_source`, `holdings_to_review` | nothing |

## After the add-a-case walkthrough

[README.md#adding-a-case](README.md#adding-a-case) adds *McConnell v. FEC*,
540 U.S. 93 (2003), which upheld BCRA § 203. *Citizens United* overruled that
part of it. When the walkthrough has been merged and the holding confirmed:

| Read | Parameters | Rows |
|---|---|---|
| `judgments_applying` | `52 U.S.C. § 30118(b)(2)` | *McConnell* and *Citizens United*, both reading `tv-feca-316-b-2-2` |
| `held_invalid` | `52 U.S.C. § 30118(b)(2)` | *Citizens United*, `in_part`, `human_reviewed` |
| `later_invalidations` | `540 U.S. 93` | *Citizens United* on `prov-feca-316-b-2`, the text *McConnell* applied |
| `holdings_to_review` | | nothing; while the holding was only proposed, its one row |
