# Quality Dimensions and Trade-offs

Pick quality dimensions deliberately. Do not grade all dimensions equally.

## Measurement Styles

Application-centered quality asks whether the model improves a real task:
search, retrieval, question answering, recommendations, analysis, or agent
workflows.

Application-neutral quality asks whether the model is accurate and coherent
against the domain and data independent of one app.

Practical default: use both. Neutral quality gives the durable baseline.
Application-centered quality is the truth test for the actual use.

## The Eight Dimensions

| Dimension | Definition | Watch for |
|---|---|---|
| Semantic accuracy | Assertions are accepted as true | Bad extraction, vague predicates, wrong source data, bad modeling elements |
| Completeness | Required elements are present | Expensive acquisition, fast-changing domains |
| Consistency | Free of logical or semantic contradiction | Conflicting assertions, constraints that fight each other |
| Conciseness | No redundant or duplicate elements | Synonyms, duplicates, rushed completeness |
| Timeliness | Current with the domain | Stale facts, no update cadence |
| Trustworthiness | Perceived confidence in the model | Unknown provenance, uncertain sources, opaque curation |
| Understandability | Humans can read and use it | Cryptic naming, over-compression, missing docs |
| Relevancy | Right content for this task | Optimizing for the wrong consumer or application |

## Measuring Accuracy

Sample assertions and have multiple judges mark them true or false. Use domain
experts, users, or trained reviewers depending on the task. Report agreement,
especially when terms are vague.

Augment human checks with automatic checks: outliers, low-connectivity
elements, duplicate detection, and consistency checks against existing
constraints.

## Trade-off Pairs

You cannot maximize all dimensions at once. The failure is making the trade-off
silently.

- Accuracy vs completeness. Adding everything can increase coverage while
  lowering accuracy. Decide which wins and by how much.
- Conciseness vs completeness. Rushing completeness often leaves synonyms and
  duplicates unresolved.
- Conciseness vs understandability. A compact model can be harder for humans
  to use.
- Relevancy for consumer A vs relevancy for consumer B. A model optimized for
  one task can degrade another.

Tie each trade-off to the risk it carries.
