# Schema Adaptation

Adapt an **unapplied template** freely to the new domain, then lint its queries.
Changing an already populated graph is a migration: use the live plan/apply
workflow below and respect its supported steps.

## Preserve the SPIKE structure

Start with the ten existing types: Signal, Pattern, Insight, KnowHow, Element,
Company, SourceEntity, Expert, InformationArtifact, and Chunk. Model a trial or
protocol as an Element kind before adding another type.

Keep the central analysis relationships: signals form or contradict patterns;
patterns drive or rely on other patterns; insights explain patterns; elements
and know-how supply supporting context. Preserve provenance through
SourceEntity, InformationArtifact, and Expert. The template schema is the
source for exact edge names and endpoint types.

Keep the established timestamps and `slug: String @key` on keyed node types.
Chunk is unkeyed; supply a stable top-level JSONL `id` for repeatable loads. Prefixes
such as `sig-`, `pat-`, `el-`, `co-`, and `ia-` make seed references readable.
`Pattern.kind` usually remains `challenge`, `disruption`, or `dynamic`.

## Adapt the domain

| Schema area | Typical change |
|-------------|----------------|
| `Element.kind` | Therapeutic/trial/platform for biotech; protocol/token/bridge for crypto. |
| `Signal.domain` and `Element.domain` | The same domain slices on both types; enums are declared inline. |
| `Company.type` | Ecosystem roles such as regulator, lab, investor, or exchange. |
| `SourceEntity.type` | Relevant publishing formats such as journal or governance forum. |
| `InformationArtifact.artifactType` | Papers, filings, trial registrations, proposals, and other source artifacts. |
| Optional Element properties | Replace AI-specific fields with useful domain properties such as trial phase, chain, or jurisdiction. |

Use [domain examples](domain-examples.md) as starting points. Prefer explicit
scalar types and focused enum sets. Keep existing query parameters and mutation
bodies consistent with the adapted schema; lint **every** file in `queries/`.

## Embeddings

The template has:

```pg
node Chunk {
    text: String
    chunk_index: I32
    embedding: Vector(3072) @embed("text") @index
    createdAt: DateTime
}
```

`@embed` records the source/model relationship; it does not populate the vector
on load or mutation. Chunk rows must include real 3072-dimensional vectors.
Use the offline `omnigraph embed` JSONL transformation when adding chunks, then
load its output. The query provider must use the same model and dimensions.
The initial seed can omit Chunk rows; never insert fabricated vectors merely
to satisfy the required property. A different embedding model/dimension is a
fresh-template design choice, not an automatic migration of stored vectors.

## Update the bundle

Set `metadata.name` and the `graphs` key in `cluster.yaml` to the new slug.
Update the graph policy's `applies_to` entry as well, while leaving the server
policy bound to `[cluster]`. Preserve the template's administrator management
permissions so later live updates remain authorized.

Update `default_graph` and alias `graph` values in
`omnigraph-config.example.yaml`. Audit aliases with fixed domain values when
their enums change. Preserve unrelated operator settings when installing the
new entries; tokens belong in credentials, not the example config.

```bash
for query_file in queries/*.gq; do
  omnigraph lint --schema schema.pg --query "$query_file" || exit 1
done
omnigraph cluster validate --config .
```

Lint checks schema/query compatibility. Bundle validation checks the declared
files and bindings. Neither validates all rows in `seed.jsonl`; the load does.

## Evolve a running graph

Follow the root README's
[live updates](https://github.com/ModernRelay/omnigraph-cookbooks/blob/main/README.md#live-updates).
Use served `cluster plan` and `cluster apply` with the full cluster bundle.
The server activates successful changes without restarting; do not use direct
storage apply against its held writer lock.

- Schema apply requires only `main` to remain live. Merge and delete review
  branches first; merging alone does not remove them.
- Use `@rename_from` for a supported type/property rename so identity and data
  are preserved.
- Adding nullable properties, types, or enum variants is supported. Adding a
  required property to an existing type, tightening nullable to required,
  changing keys, or narrowing enums is refused. Plan reveals the actual steps.
- Dropping a property/type removes it from the current schema, while retained
  history still references the old data. Removing an entire graph declaration
  instead purges that graph's managed storage and retained history.

For the full supported migration boundary, consult the repository's vendored
`omnigraph` skill, `references/schema.md`.
