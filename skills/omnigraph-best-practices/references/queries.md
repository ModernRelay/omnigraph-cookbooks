# Query Authoring & Linting

Writing `.gq` query files in Omnigraph.

## File Organization

- One `.gq` file per primary node type (`signals.gq`, `patterns.gq`, `elements.gq`)
- One `mutations.gq` file for all insert/update/delete queries
- Put query files in `queries/` and reference via `query.roots: [queries, .]` in `omnigraph.yaml`

## Linting

```bash
omnigraph query lint --schema ./schema.pg --query ./queries/signals.gq
```

Or (lint against a live repo):

```bash
omnigraph query lint --query ./queries/signals.gq s3://bucket/repo
```

Lint returns:
- `"status": "ok"` — all queries passed
- `"errors": N` — count of type errors (exit 1 when nonzero)
- `"warnings": N` — count of drift warnings

Run lint after every `.gq` or `.pg` edit. Wire into precommit.

## Parameterization

### Always declare typed parameters

```gq
query get_signal($slug: String) {
    match { $s: Signal { slug: $slug } }
    return { $s.slug, $s.name }
}
```

Never string-interpolate values into query bodies. Pass them via `--params`:

```bash
omnigraph read --query signals.gq --name get_signal --params '{"slug":"sig-foo"}'
```

The compiler typechecks parameter values against declared types.

## Query Structure

### Match → Return → Order → Limit

```gq
query recent_signals() {
    match {
        $s: Signal
    }
    return { $s.slug, $s.name, $s.stagingTimestamp }
    order { $s.stagingTimestamp desc }
    limit 50
}
```

### Edge traversal (lowerCamelCase)

Schema edges are PascalCase; traversal uses lowerCamelCase:

```gq
match {
    $s: Signal { slug: $slug }
    $s formsPattern $p         // edge FormsPattern: Signal -> Pattern
}
```

### Multi-hop

Chain traversal clauses:

```gq
query friends_of_friends($name: String) {
    match {
        $p: Person { name: $name }
        $p knows $mid
        $mid knows $fof
    }
    return { $fof.name }
}
```

### Reverse traversal

Flip the subject/object:

```gq
query employees_of($company: String) {
    match {
        $c: Company { name: $company }
        $p worksAt $c
    }
    return { $p.name }
}
```

### Negation

```gq
query orphan_signals() {
    match {
        $s: Signal
        not { $s formsPattern $_ }
    }
    return { $s.slug }
}
```

## Search Functions

### Text search

```gq
match {
    $d: Doc
    search($d.title, $q)       // full-text on @index'd String
}
```

```gq
match {
    $d: Doc
    fuzzy($d.title, $q, 2)     // fuzzy match, max 2 edits
}
```

```gq
match {
    $d: Doc
    match_text($d.body, $q)    // phrase match
}
```

### Vector/ranking (require `limit`)

```gq
query vector_search($q: Vector(3072)) {
    match { $d: Doc }
    return { $d.slug, $d.title }
    order { nearest($d.embedding, $q) }
    limit 10
}
```

`nearest`, `bm25`, and `rrf` are ranking operators, not filters. Every query using them **must** end with `limit N` — omitting it is a compile error.

### Hybrid (reciprocal rank fusion)

```gq
query hybrid_search($vq: Vector(3072), $tq: String) {
    match { $d: Doc }
    return { $d.slug, $d.title }
    order { rrf(nearest($d.embedding, $vq), bm25($d.title, $tq)) }
    limit 10
}
```

## Aggregations

```gq
query friend_counts() {
    match {
        $p: Person
        $p knows $f
    }
    return {
        $p.name
        count($f) as friends
    }
    order { friends desc }
    limit 20
}
```

Supported: `count`, `sum`, `avg`, `min`, `max`. Grouping is implicit on non-aggregated return fields.

## Filter Operators

`=`, `!=`, `>`, `<`, `>=`, `<=`, `contains`

```gq
match {
    $p: Person
    $p.age > 30
    $p.name contains "Al"
}
```

## Mutations

> **No top-level `mutation { ... }` wrapper.** Agents trained on GraphQL reflexively write `mutation { insert T { ... } }` — that fails the parser at character 1 with `parse error: expected query_file`. Every executable block in a `.gq` file is a named `query`; the body's verb (`insert` / `update` / `delete`) determines whether it's a write. Dispatch via `omnigraph change` (not `read`).

### Insert

```gq
query add_signal($slug: String, $name: String, $brief: String,
                 $stagingTimestamp: DateTime, $createdAt: DateTime, $updatedAt: DateTime) {
    insert Signal {
        slug: $slug,
        name: $name,
        brief: $brief,
        stagingTimestamp: $stagingTimestamp,
        createdAt: $createdAt,
        updatedAt: $updatedAt
    }
}
```

**Every non-nullable property must be provided.** Lint catches missing ones as:

```
error: T12: insert for 'Signal' must provide non-nullable property 'brief'
```

### Insert edge

```gq
query link_signal_forms_pattern($signal: String, $pattern: String) {
    insert FormsPattern { from: $signal, to: $pattern }
}
```

Edge `data` block is `{}` if the edge has no properties — just specify `from` and `to` slugs.

### Update

```gq
query retitle_signal($slug: String, $new_title: String) {
    update Signal set { name: $new_title } where slug = $slug
}
```

### Delete

```gq
query remove_signal($slug: String) {
    delete Signal where slug = $slug
}
```

### Multi-statement

```gq
query add_and_link($slug: String, $pattern: String, $createdAt: DateTime, $updatedAt: DateTime) {
    insert Signal { slug: $slug, name: $slug, brief: $slug,
                    stagingTimestamp: $createdAt, createdAt: $createdAt, updatedAt: $updatedAt }
    insert FormsPattern { from: $slug, to: $pattern }
}
```

There's no `upsert` keyword at the query level — use `load --mode merge` for bulk upsert.

### Date and DateTime values

Date format is asymmetric between `change` (parameter values) and `ingest` / `load` (JSONL):

| Path | Date | DateTime |
|---|---|---|
| `change --params` | ISO string `"2026-04-29"` | ISO string `"2026-04-29T10:00:00Z"` |
| `ingest` / `load` JSONL | Integer days since epoch `20572` | ISO string `"2026-04-29T10:00:00Z"` |

Compute integer days form for a given date `d`:

```python
(d - datetime.date(1970, 1, 1)).days   # d is the date you're loading, not today()
```

This asymmetry is one of the most common silent type errors when bulk-loading data prepared for one path through the other.

## Naming Convention

`verb_object`:
- `get_signal`, `recent_signals`, `search_signals`
- `signal_patterns`, `signal_elements` (traversal queries)
- `add_signal`, `link_signal_forms_pattern` (mutations)

## Aliases Over Raw Queries

For anything an agent or script will call repeatedly, define an alias in `omnigraph.yaml`. See `references/aliases.md`.
