---
name: omnigraph-intel-bootstrap
description: Bootstrap a SPIKE industry intelligence graph with the AI industry demo or a custom domain. Use for initial domain/source elicitation, schema adaptation, researched seed data, and cookbook setup; use the omnigraph skill for routine graph operations.
license: MIT (see LICENSE at repo root)
metadata:
  author: ModernRelay
  version: "0.6.0"
  repository: https://github.com/ModernRelay/omnigraph-cookbooks
---

# SPIKE Cookbook Bootstrap

Create a populated, queryable intelligence graph. Use the existing AI industry
**demo**, or adapt it to a **custom domain**. Follow the user's stated choice;
ask only when it is unclear.

## Start with the environment

Locate or clone `ModernRelay/omnigraph-cookbooks`, then read its root README and
the selected cookbook's guidance. Check `omnigraph version`; these instructions
target CLI and server 0.13. Use matching release binaries. The filesystem
setup needs no object store or Docker. Existing data follows
the repository's [upgrade procedure][upgrading], never an automatic reset.

The root README owns [local setup][local-setup]: initial apply, exact writer-lock
handoff, server identities, readiness, login, and seed loading. Read and follow
that sequence. A filesystem deployment needs no storage credentials; the server
still uses bearer identities for policy and live configuration management. Pick
a free port if another server is running; do not stop an unrelated process.

## Demo

Use `industry-intel/` unchanged. See [demo setup](references/demo-setup.md) for
verification queries. Its seed is a fixed example dataset, not a current market
report. Report the loaded counts and query results, then hand off to the
`omnigraph` skill for everyday operations.

## Custom domain

### 1. Define the scope and sources

Collect the domain, geographic scope, project slug, actors, time horizon,
update cadence, and intended consumer. Reuse answers already given. The
[elicitation guide](references/custom-domain.md) supplies prompts and source
categories; [domain examples](references/domain-examples.md) offer starting
points when the user wants defaults.

Record the scope and sources in `<slug>/setup-notes.md`. Resolve missing decisions
that would materially change the schema or research. A cadence preference does
not itself authorize scheduling an automation.

### 2. Adapt the template

Create a new cookbook directory. Copy only declarative files from
`industry-intel/`: `schema.pg`, `queries/`, `cluster.yaml`, `policies/`, and
`omnigraph-config.example.yaml`. Do not copy local graph roots, ledgers,
credentials, or runtime state. Write the new cookbook's README and guidance for
its domain instead of carrying over the demo's counts and examples.

Follow [schema adaptation](references/schema-adaptation.md). Keep the SPIKE
analytical relationships; adapt domain enums, actor classifications, and
Element properties. Update the graph id everywhere it is referenced:
`graphs`, graph-policy `applies_to`, operator `default_graph`, and aliases.
Keep the cluster policy's `applies_to: [cluster]` binding.

Lint every query file against the adapted schema, then validate the bundle:

```bash
for query_file in queries/*.gq; do
  omnigraph lint --schema schema.pg --query "$query_file" || exit 1
done
omnigraph cluster validate --config .
```

### 3. Research and produce the seed

Follow [research](references/research.md): gather dated sources, identify
signals, group supported patterns, and connect actors and provenance. Keep
observed facts distinct from analytical insights. Never invent dates or URLs.

Write `seed.md` for review, then produce `seed.jsonl` from the agreed content.
Supply every required property, deduplicate node keys and constrained edges,
and validate references. `Chunk.embedding` is required: generate real vectors
with the offline `omnigraph embed` pipeline before loading chunks. Declaring
`@embed` or a server provider does not generate vectors on load or mutation.
An initial seed may omit Chunk entirely, as the demo does.

### 4. Serve and verify

Follow [local setup][local-setup] with the new directory and graph id. Query the
running graph to verify patterns, signals, and at least one traversal. Merge
only the relevant named-server and alias entries into the user's operator
configuration; preserve unrelated settings and keep credentials separate.

Report the cookbook location, loaded counts, server/graph target, and a working
query. Keep exact write receipts. After a lost or timed-out response, establish
the outcome before replaying; for an accepted deployment, observe its original
deployment ID.

## Later changes

Use [live updates][live-updates]: edit the declared schema, queries or policies,
then `cluster plan --server …` and `cluster apply --server …`. Successful served
apply activates the changes without restarting. Do not write the same cluster
directly while its server owns the writer lock.

Schema changes require `main` to be the only live branch. Supported renames use
`@rename_from`; enum widening and nullable property additions are supported,
but arbitrary type/key changes and nullable-to-required tightening are not.
Plan before apply. Removing a graph from `cluster.yaml` permanently deletes its
managed storage and retained history; it is not a way to pause serving.

Use the repository's vendored `omnigraph` skill for command details, bulk data
review, embedding preparation, and uncertain write outcomes.

[local-setup]: https://github.com/ModernRelay/omnigraph-cookbooks/blob/main/README.md#local-setup
[live-updates]: https://github.com/ModernRelay/omnigraph-cookbooks/blob/main/README.md#live-updates
[upgrading]: https://github.com/ModernRelay/omnigraph-cookbooks/blob/main/README.md#upgrading
