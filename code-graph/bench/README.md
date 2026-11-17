# code-graph benchmarks

Two benchmarks for the claims this cookbook makes, both on
[hono](https://github.com/honojs/hono), TypeScript, MIT. They are run by hand,
not in CI, and write everything they fetch or build under `work/`, which git
ignores.

| Benchmark | Claim | Ground truth |
|---|---|---|
| [PR diff](#pr-diff) | A pull request's branch diff is exactly what it changed | Two reference graphs built with the TypeScript compiler API, at the base and the merge commit |
| [Execution recall](#execution-recall) | The graph contains the calls the code really makes | Calls recorded while hono's own test suite runs |

The cookbook resolves references through scip-typescript, which runs the
TypeScript compiler. A compiler-built reference therefore cannot test the
cookbook's resolution, only its conversion and diffs: the PR-diff benchmark
uses one for that. The execution-recall benchmark's truth comes from running
code, not from the compiler, so it can compare the cookbook with other tools.

## Requirements

git, Python 3, Node.js 22.23.4 or later, bun (hono's tests), the locked
indexer (`npm ci` in `code-graph/sources/indexer`) and the 0.14.0 `omnigraph`
CLI. Every `omnigraph` call runs with its own `OMNIGRAPH_HOME` under `work/`.

## PR diff

```bash
OMNIGRAPH_BIN=/path/to/omnigraph python3 code-graph/bench/pr_diff.py
```

The sample, pinned in `pr-sample.json`, is the 40 most recent first-parent
commits on hono's `main` before 2026-11-01 that change a non-test `.ts` file
under `src/`. hono squash-merges, so each is one pull request. For each, both
commits are indexed and converted, loaded with `cg load` (the base onto
`main`, the merge commit onto a branch with `--mode overwrite`) and reviewed
with `cg diff`. The review is scored twice:

- **Mechanics**, against the set difference of the two converted files. This
  tests overwrite loads and `branch diff`.
- **Accuracy**, against the difference of two reference graphs from
  `reference.mjs`, over the definitions both the reference and the cookbook
  model. A changed symbol is one whose code digest moved.

Results, `results/pr_diff.json`:

| | Exact pull requests | Added | Removed | Changed | References added | References removed |
|---|---|---|---|---|---|---|
| Mechanics | 40 of 40 | 19 of 19 | 9 of 9 | 46 of 46 | 90 of 90 | 37 of 37 |
| Accuracy, precision | 36 of 40 | 1.000 | 0.667 | 0.935 | 1.000 | 0.865 |
| Accuracy, recall | | 1.000 | 1.000 | 0.956 | 1.000 | 0.970 |

The four inexact pull requests, checked against their source diffs:

- **`8a103aa5`**: three updates the reference does not count are real
  changes. A constant's value changed, such as `ONLY_WILDCARD_REG_EXP_STR`
  from `".*"` to `"[^]*"`, and a field's type changed; the cookbook reports
  them through `signature`. The reference tracks code changes of callables only.
- **`17ad0e21`**, **`e9c01079`**: `Context.header` and `Factory.createApp` are
  class fields holding arrow functions. scip-typescript gives fields no range,
  so the cookbook has no digest for them and misses changes to their code.
- **`e9c01079`**: `HonoOptions` became a union of two object types, and
  scip-typescript stopped indexing their properties, so the diff reports
  `getPath`, `router` and `strict` removed with five references.
- **`6cadf753`**: one removed reference the cookbook still has; unexplained.

The first run of this benchmark found that keys carried scip-typescript's
positional `typeLiteralN` numbering, so one new type literal renamed every
member below it. The converter now leaves those containers out of keys.
Execution recall then found 46 function constants the converter did not count
as callable, such as `const getCookie: GetCookie = (c) => {...}`, so calls to
them had `call: false` and changes to their code went unseen; none of the 40
sampled pull requests changed one. The converter now takes callability from
the indexer's range. Cached conversions and references are keyed by a digest
of the code that made them.

## Execution recall

```bash
node code-graph/bench/instrument.mjs CHECKOUT work/traced     # then install hono's dependencies with bun
CG_TRACE_DIR=work/trace work/traced/node_modules/.bin/vitest --run --project main --coverage.enabled=false --pool forks
python3 code-graph/bench/recall.py work/trace COOKBOOK.jsonl REFERENCE.json [TOOL.json ...]
```

`instrument.mjs` copies the base revision of the cookbook's seed, `a10592f3`,
and wraps every function under `src/` so that a call into a definition records
`caller -> callee`. The caller is the definition that owns the code making the
call, by the same rules as the static graphs: a callback written in F is F's
code wherever it runs. Test code runs as `<outside>` and is never a caller.
The owner travels through awaits in an `AsyncLocalStorage`. The instrumented
suite runs 3,956 tests like the untouched copy; one test differs. The tests
executed 906 distinct calls between hono's definitions.

Recall is the share of executed calls a graph contains. An edge the tests
never ran is not wrong, so this measures recall only. Every graph is mapped
into one identity space, `path:Container.member`; a tool's local helper
functions map to the definition that holds them, as the traces do. The tools
ran at their defaults, each on its own copy of the checkout with a scratch
home, telemetry off and no model keys: codegraph 1.6.2 (calls and instantiations),
codebase-memory-mcp 0.12.1, GitNexus 1.6.12, Graphify 0.9.102 (calls,
AST only) and code-review-graph 2.3.9.

Results, `results/recall.json`:

| Graph | All 906 | Functions and methods (759) | Constructors (54) | Getters and setters (93) |
|---|---|---|---|---|
| Compiler reference | 0.892 | 0.880 | 0.907 | 0.978 |
| Cookbook, every reference | 0.891 | 0.876 | 0.907 | 1.000 |
| Cookbook, every reference with `Implements` | 0.930 | | | |
| Cookbook, call edges only | 0.733 | 0.810 | 0.907 | 0 |
| codegraph | 0.679 | 0.748 | 0.870 | 0 |
| Graphify | 0.677 | 0.747 | 0.852 | 0 |
| GitNexus | 0.642 | 0.705 | 0.870 | 0 |
| codebase-memory-mcp | 0.626 | 0.685 | 0.870 | 0 |
| code-review-graph | 0.602 | 0.718 | 0 | 0 |

"Every reference" is the cookbook as its reads answer: `callers`, `callees`
and `impact` follow every `References` edge and report `call` as a column, not
a filter. "Call edges only" keeps the edges whose `call` is true. "With
`Implements`" adds a second read, `implementers`: a call through an interface
member also reaches the implementations the graph records.

The tools record calls, so the like-for-like column is functions and
methods, where the cookbook's call edges find 0.810 and its references 0.876.
Getter calls are property reads: only a graph of references contains them. A
graph of every reference also holds more edges than a call graph, and this
benchmark does not count the edges the tests never ran.

### Where the difference comes from

Two things separate the cookbook from the tools, and they are of different
kinds. The first is what is recorded. The cookbook's references contain 807
executed calls and its call edges 664; the 143 between them are 93 getter
calls, which run when a property is read, and 50 calls to functions the code
passes as values. That is most of the gap between 0.891 and the tools' best,
0.679, and it is a choice of what to record more than better extraction.

The second is resolution. The tools find definitions by name, the cookbook
through the type checker. Recall on calls to functions and methods, from
`functions_by_call_shape` in `results/recall.json`:

| Callee | Executed | Cookbook calls | codegraph | Graphify | GitNexus | codebase-memory-mcp | code-review-graph |
|---|---|---|---|---|---|---|---|
| Top-level function | 565 | 0.888 | 0.842 | 0.881 | 0.827 | 0.850 | 0.828 |
| Class member | 194 | 0.582 | 0.474 | 0.356 | 0.351 | 0.206 | 0.397 |
| Name defined once | 504 | 0.929 | 0.865 | 0.919 | 0.849 | 0.863 | 0.855 |
| Name defined 4 or more times | 125 | 0.496 | 0.424 | 0.288 | 0.288 | 0.192 | 0.264 |

Where a name identifies its definition, the tools come close: Graphify is
within a point of the cookbook. The gap opens where it does not: a method
call such as `c.req.header()` resolves to `HonoRequest.header` only if the
type of `c.req` is known, and hono defines `header` in several places. Of
the calls to a shared class-member name each tool missed, it recorded 14 to
26 as the caller calling another definition of that name.

The tools find 26 executed calls the cookbook lacks, 16 of them codegraph's.
Most are calls dispatched to an override, which matching by name catches by
linking every method of that name.

The compiler reference misses 98 executed calls, about one in nine. 47 are
function values called indirectly: a function passed as an argument, stored
in a property or returned, then called by code that never names it. 44 are
calls dispatched to an override, such as `this.getHeaders()` in an abstract
class running a subclass's method; the cookbook's `Implements` edges recover
most of these. The other seven reach constructors and getters.

## Limits

- One repository in one language. The ranking may differ elsewhere.
- The reference shares the TypeScript compiler with scip-typescript, so the
  PR-diff accuracy measures conversion and modeling, not resolution.
- Execution recall covers only what hono's tests run, and the tracer skips
  two generators.
- Tools are mapped by file, name and line into the reference's identities; a
  tool's own node that the reference does not model counts as not found.
