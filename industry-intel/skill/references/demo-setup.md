# Demo Setup — AI Industry Intel

Use the `industry-intel/` cookbook in a local clone of
[omnigraph-cookbooks](https://github.com/ModernRelay/omnigraph-cookbooks).
The fixed seed illustrates SPIKE; it is not a current research feed.

Follow the root README's
[local setup](https://github.com/ModernRelay/omnigraph-cookbooks/blob/main/README.md#local-setup)
with cookbook `industry-intel` and graph `spike`. That is the single setup
sequence for apply, writer-lock handoff, server startup, readiness, login, and
loading. Merge the cookbook's named server and aliases into the operator config
without replacing unrelated entries. Use the reader identity for exploration.

## Verify the served graph

```bash
omnigraph alias patterns disruption
omnigraph alias pattern-signals pat-sovereign-ai
```

The unchanged demo returns two disruption patterns (SaaSpocalypse and Sovereign
AI), and three signals for Sovereign AI. These queries read the running graph;
`seed.md` describes the original input.

| Node | Seed count |
|------|------------|
| Pattern | 5 |
| Signal | 15 |
| Element | 24 |
| Company | 16 |
| Expert | 7 |
| SourceEntity | 16 |
| InformationArtifact | 20 |
| Insight | 4 |
| KnowHow | 2 |

The seed contains 109 nodes and 154 edges. It has no Chunk rows and therefore
requires no embedding provider.

## Continue

Explore `queries/*.gq` and the cookbook's aliases. For schema, query, or policy
updates, follow the root README's
[live update workflow](https://github.com/ModernRelay/omnigraph-cookbooks/blob/main/README.md#live-updates).
Use the `omnigraph` skill for data changes and branch review.

An overwrite load replaces only the node/edge types represented in its input;
it does not reset the whole graph or erase retained history. Run it against the
server only when replacing those rows is intended. Preserve user data when
refreshing an existing demo.
