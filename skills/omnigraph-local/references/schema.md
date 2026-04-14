# Schema Authoring & Evolution

How to write and evolve `.pg` schemas in Omnigraph.

## Authoring (.pg files)

### Use `//` for comments

Not `#`. The compiler rejects `#` with a parse error that looks like:

```
parse error: expected schema_file
```

### Enums are inline, not standalone

The compiler does **not** accept top-level `enum Foo { ... }` blocks. Put the values inline on the property:

```pg
kind: enum(product, technology, framework, concept, ops) @index
```

If the same enum appears on multiple nodes, duplicate it inline — there's no shared enum type.

### Lists contain scalars only

`[String]` and `[I32]` are fine. `[Category]` (a list of enum values) is **not** supported. Use `[String]` with query-side filtering, or use a single-valued enum property if one value is enough.

### `@embed` takes a quoted string

```pg
embedding: Vector(3072) @embed("text") @index
```

Not `@embed(text)`. The source property name is a string literal.

### Edge constraints go inside a body block

`@unique(src, dst)` on an edge goes inside `{ }`, after `@card(...)`:

```pg
edge PartOfArtifact: Chunk -> InformationArtifact @card(1..1) {
    @unique(src)
}
```

### Lint after every edit

```bash
omnigraph query lint --schema ./schema.pg --query ./queries/signals.gq
```

This validates the schema **and** the queries against it. No running repo required. Wire it into a precommit hook.

## Evolution (schema plan/apply)

### Plan before apply — always

```bash
omnigraph schema plan --schema ./next.pg s3://bucket/repo --json
# inspect "supported": true|false and the step list
omnigraph schema apply --schema ./next.pg s3://bucket/repo
```

If `supported: false`, fix the source before applying. Apply is destructive — there's no undo. Plan is free; run it as often as needed.

### Apply is main-only

`omnigraph schema apply` rejects any non-`main` branches. Delete or merge feature branches first. This is deliberate: schema changes don't go through review branches. They go straight to main via `plan` + `apply`.

### Rename, don't replace

Use `@rename_from(...)` on renames so the planner emits a rename step (preserves data), not a drop+add pair (loses data):

```pg
node Account @rename_from("User") {
    full_name: String @rename_from("name")
}
```

Works on node types, edge types, and properties.

### Required properties need a backfill plan

Adding a non-nullable property to an existing node is rejected as unsupported. Pattern:

1. Add as optional: `new_prop: String?`
2. Apply
3. Backfill via `change` mutation or `load --mode merge`
4. Tighten to required in a follow-up apply: `new_prop: String`

### Keep `@key` stable

Changing the key field is effectively a replace — it invalidates every external reference to the node. Treat identity changes as deliberate, multi-step migrations, not casual field renames.

### `schema apply` blocks writes while running

No concurrent mutations during an apply. Plan for a short read-only window.

## Supported Types

- **Scalars:** `String`, `Bool`, `I32`, `I64`, `U32`, `U64`, `F32`, `F64`, `Date`, `DateTime`, `Blob`
- **Collections:** `Vector(N)` (fixed-size float vector), `[ScalarType]` (list of scalar)
- **Enums:** `enum(value1, value2, ...)` — inline only, values can contain alphanumerics, underscores, hyphens
- **Optional:** any type + `?` suffix (`String?`, `[I32]?`, `Vector(4)?`)

## Decorators (quick reference)

**Property-level:**
- `@key` — primary key (implies index; usually one per node)
- `@unique` — uniqueness constraint
- `@index` — query optimization
- `@range(min, max)` — numeric bounds
- `@embed("source_prop")` — embed from a String source into a Vector property
- `@description("...")` — metadata (no migration impact)
- `@instruction("...")` — semantic hint for LLMs/operators

**Edge-level:**
- `@card(min..max)` — edge cardinality (default: `0..*`)

**Type-level (nodes/edges/properties):**
- `@rename_from("OldName")` — migration-aware rename

**Group-level (inside body block):**
- `@unique(prop1, prop2)` — composite uniqueness (works on edges too: `@unique(src, dst)`)
- `@index(prop1, prop2)` — composite index

## Interfaces

Supported but rarely used. Declare shared property contracts and node types implement them:

```pg
interface Searchable {
    title: String @index
    embedding: Vector(3072) @embed("title")
}

node Doc implements Searchable {
    slug: String @key
    body: String
}
```

Most schemas are fine without interfaces. Reach for them only when 3+ node types need to share a property contract.

## Design Principles (brief)

- **Identity is explicit** — use `@key` on a semantic slug, not internal row IDs
- **Narrow types** — `Date` over `String` for dates, `enum` over `String` for lifecycle states
- **Edge semantics matter** — prefer `AuthoredBy` over `RelatedTo`
- **Constraints live in the schema** — `@unique`, `@range`, `@card` keep invariants out of application code
- **Schemas are reviewable** — clear names, explicit enums, obvious keys
