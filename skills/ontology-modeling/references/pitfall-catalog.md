# Pitfall Catalog

Use this as a pre-mortem when authoring and as a checklist when reviewing.
These are defects, not judgment calls.

## Bad Descriptions

- Ignoring vagueness. Terms like senior, active, relevant, near, similar, and
  strategic admit borderline cases. Do not fake precision with arbitrary
  thresholds. Label the boundary as vague when it is vague.
- Ambiguous labels and definitions. A term with multiple plausible meanings
  needs a domain-specific definition or a disambiguating name.
- Missing or circular definitions. A new reader must be able to reconstruct
  the element's meaning without already knowing the model.

## Bad Semantics

- Bad identity. If the model lacks criteria for when two instances are the same
  thing, merges, dedupe, equality, and references break.
- Parts modeled as subclasses. An engine is part of a car, not a kind of car.
  Use a part-whole relation.
- Common superclass with incompatible identity criteria. Grouping things under
  one class when sameness rules differ produces bad reasoning.
- Vague relation declared transitive. Relations like similar to, near to, and
  soft forms of part of can produce absurd chains when treated as transitive.
- Complementary vague classes. Do not define clean partitions where the domain
  has fuzzy boundaries.
- Open-world vs closed-world confusion. Know whether absence means unknown or
  false before writing constraints and validation rules.

## Bad Specification and Knowledge Acquisition

- Wrong sources. Noisy source data must be marked, filtered, or reviewed.
- Wrong people. Domain experts are not automatically the right informants.
  Match knowledge sources to actual usage.
- Acquisition mechanism does not match accuracy needs. Manual is slower but
  often more accurate. Automatic is faster but noisier.

## Bad Quality Management

- Pretending all quality dimensions can be maximized at once.
- Measuring convenient dimensions instead of consequential ones.
- Hiding trade-offs instead of writing them down.

## Bad Application

- The model is well-formed but wrong for the task. Optimize content and
  semantics for the use in front of you, not for abstract correctness.

## Bad Strategy and Governance

- No owner, change process, or validation process.
- Treating the model as a purely technical artifact instead of a
  socio-technical commitment.
