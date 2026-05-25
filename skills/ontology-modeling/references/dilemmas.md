# Dilemmas

Legitimate forks have no single right answer. Do not flag these as errors in a
review. The job is to make the choice deliberately and record the reasoning.

## Representation Dilemmas

- Class vs instance. `Lion` can be a class of individual lions, or an instance
  of `Species`. Pick by what you need to say about it and at what level.
- Relation vs reified node. A direct edge is simpler. A node like `Marriage` or
  `Employment` lets you attach dates, sources, confidence, and status.
- Attribute vs value entity. `color = "red"` is enough when red is just a
  literal. Use a `Red` entity when the value itself needs description,
  provenance, hierarchy, or reasoning.

Resolution rule: choose by query pattern and reasoning need, not elegance.
Ask what questions the model must answer and what inferences must run.

## Expressiveness and Content Dilemmas

- Coverage vs cost. Every element adds acquisition and maintenance debt.
- Granularity. Too coarse loses distinctions. Too fine creates noise and
  maintenance burden.
- Expressiveness. More constraints and formal semantics enable reasoning, but
  raise the cost of authoring and the blast radius of mistakes.

Resolution rule: make a distinction only when it adds value. Extra semantics
are debt when a simpler representation satisfies the use.

## Evolution and Governance Dilemmas

- Model evolution. Classes, relations, and identity rules change as the world
  changes. Once data and consumers depend on them, changes get expensive.
- Model governance. Centralized control is consistent but slow. Distributed
  control is faster but can drift. Pick for the organization, not for an ideal
  org chart.

## Symbolic vs ML and Other Status Debates

Avoid framework status fights. Hand-built semantics give control and
explainability. Learned representations give coverage and adaptivity. Often
the useful answer is a combination.

The productive question is whether a feature helps build the model the use
actually needs.

## Reversibility Applied

- Cheap to undo: labels, peripheral attributes, extra views. Pick the simpler
  option now.
- Expensive to undo: identity criteria, core relation semantics, class vs
  instance boundaries. Prototype against real queries before data accretes.
