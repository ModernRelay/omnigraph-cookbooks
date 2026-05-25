---
name: ontology-modeling
description: >-
  Apply disciplined judgment when designing, reviewing, or critiquing an
  ontology, schema, knowledge graph, taxonomy, or typed data model. Use this
  skill whenever the user is modeling meaning into structure: defining
  classes, relations, types, properties, identity rules, or deciding whether an
  existing model is good for a specific purpose. Triggers include schema
  design, data modeling, knowledge-graph design, taxonomy work, "is this model
  right", "how should I represent X", reviewing a .ttl/.owl/.pg/JSON
  Schema/ERD, or any decision about how to encode domain meaning. For
  Omnigraph work, use this before or alongside omnigraph-best-practices when a
  .pg change alters domain meaning, identity, relation semantics, or
  governance.
license: MIT (see LICENSE at repo root)
metadata:
  author: ModernRelay
  version: "0.1.0"
  repository: https://github.com/ModernRelay/omnigraph-starters
---

# Ontology and Semantic Model Quality

This skill is for semantic judgment: what the graph should mean, who agrees on
that meaning, and which trade-offs are acceptable for the task. Use
`omnigraph-best-practices` after these choices are ready to encode in
Omnigraph `.pg` and `.gq` files.

## The Rule That Overrides Everything

There is no good model in the abstract. There is only good for a purpose.
Never judge a model without knowing the domain, the data, the consumers, and
the task. If that context is missing, ask before judging.

## Step 0: Name the Consensus

A model is worth only as much as the consensus underneath it. Before reviewing
or authoring anything, establish:

- Whose agreement does this model encode?
- Who will consume it: humans, systems, agents, or downstream tasks?
- Do the people defining the meaning match the people using it?

A mismatch here voids downstream quality claims.

## Mode: Review

Use this when judging an existing model.

1. State the consensus scope you are assuming.
2. Walk the pitfall catalog in `references/pitfall-catalog.md`. These are
   defects, not opinions.
3. Score only the 2 to 3 quality dimensions that are load-bearing for this
   use. Use `references/quality-dimensions.md`.
4. Surface trade-offs made by accident. Trade-offs are acceptable when named.
5. Separate genuine dilemmas from pitfalls with `references/dilemmas.md`.
6. Recommend the smallest set of changes that improves the load-bearing
   dimensions, ordered by reversibility.

## Mode: Author

Use this when designing a new model.

1. Start with consensus and consumers.
2. State the task the model must serve and the 2 to 3 quality dimensions that
   matter most.
3. Choose representations by query pattern and reasoning need: class vs
   instance, relation vs reified node, attribute vs value entity.
4. Write down trade-offs before building.
5. Pre-mortem the design against `references/pitfall-catalog.md`.
6. Decide governance and evolution up front: owner, change process, validation,
   and migration expectations.

## Reversibility Heuristic

- Near-irreversible: identity criteria, core relation semantics, class vs
  instance boundaries, anything reasoning depends on. Slow down here.
- Reversible: labels, descriptions, peripheral attributes, presentation. Move
  quickly and revisit later.

## Omnigraph Handoff

When using this with Omnigraph:

- Use this skill to decide semantic intent.
- Use `omnigraph-best-practices` to encode that intent safely in `.pg` schema,
  `.gq` queries, aliases, data loads, and migrations.
- For `.pg` changes that alter identity, class boundaries, edge semantics, or
  required properties, use both skills.

## Guardrails

- The framework is not the domain. Ask context, then reason.
- Consensus is the bottleneck. Do not promise effortless interoperability.
- Judge the whole pipeline: acquisition, model quality, storage, evolution, and
  application fit.
- Avoid status debates. Make semantic distinctions only when they improve the
  task.

## Reference Files

- `references/quality-dimensions.md`: quality axes, measurement styles, and
  trade-off pairs.
- `references/pitfall-catalog.md`: semantic defect checklist.
- `references/dilemmas.md`: legitimate modeling forks and how to resolve them.
