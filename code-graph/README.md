# code-graph — a versioned graph of a repository's symbols and references

An Omnigraph cookbook that turns a repository into a typed graph of its
definitions and the references between them, one graph state per git
revision. It is generated from a [SCIP](https://github.com/sourcegraph/scip)
index, so every reference is resolved by the compiler rather than by matching
names, and each pull request is reviewed as a `branch diff` of the call graph.

> For operating Omnigraph — schema authoring, queries, loading, branches,
> cluster ops, the CLI — use the **omnigraph** skill. This README covers only
> what is specific to code-graph.

The seed is real code: the router of [hono](https://github.com/honojs/hono)
(MIT), at the parent of
[PR #5267](https://github.com/honojs/hono/pull/5267) and at the PR itself. See
[`seed.md`](seed.md) for what it holds and what each read returns.

## What it answers

- *Who calls this function, and how many times?* `callers`
- *What breaks if I change it?* `impact`, everything within three references
- *Which classes implement this interface method?* `implementers`
- *What does everything else depend on?* `most_referenced`
- *What did this pull request change in the call graph?* `branch diff` of the
  PR's branch: new and changed functions, new and removed references
- *Who called it at the last release?* any read with `--snapshot`

Code search answers "where is this text". A code graph answers "what depends
on this", and Omnigraph adds the history: every revision is a commit, and
every pull request is a branch you can diff, query and merge.

## The model

| Type | What it is |
|---|---|
| `Symbol` | A named definition: a module (one file), class, interface, type, enum, function, method, constant, variable or member. Locals and parameters are left out. |
| `Location` | Where a symbol's definition sits: first and last line. |
| `Revision` | The commit this graph state was indexed from, and the indexer that read it. |
| `References` | Code inside the source's definition names the target. `call` says whether one of those references is a call; `sites` counts them. |
| `MemberOf` | A top-level symbol in its module, a member in its class or interface. |
| `Implements` | A class member implementing an interface member. |
| `DefinedAt` | A symbol's location. |

The decisions that matter:

1. **Identity is the SCIP symbol without its package version.** A symbol's key
   is its descriptor path, such as ``src/router/`utils.ts`/createNullObject.``
   for a constant or ``src/router/reg-exp-router/`router.ts`/RegExpRouter#add().``
   for a method. It survives every edit that keeps the name and file, so the
   same function has the same key in every revision. SCIP symbols also carry
   the package version (`npm hono 4.13.3`); keeping it would rekey every node
   at each release. For the same reason the key leaves out the `typeLiteralN`
   containers scip-typescript numbers anonymous type literals with: one new
   type literal near the top of a file would otherwise rename every member
   below it.
2. **Line numbers live on `Location`, not on `Symbol`.** A line moves whenever
   code above it changes: in PR #5267, 58 definitions only moved. Kept on
   `Symbol`, those moves would bury the five functions that changed. Each
   callable instead carries `digest`, a hash of its definition text, so a
   `Symbol` update in a diff means its code or its declared type changed,
   which `cg diff` tells apart, and a move is a `Location` update you can
   filter out by type.
3. **One `Symbol` type, with `kind` as a closed vocabulary.** A multi-hop
   traversal needs the same node type at both ends, so a single type is what
   lets `impact` follow `references{1,3}` through functions, methods and
   classes alike.
4. **References, not only calls.** SCIP records that a definition's code names
   another symbol; it does not say how. An edge therefore covers calls, type
   uses, imports and value uses, which is what "what breaks if I change this"
   needs. `call` marks the edges with at least one call site.
5. **Provenance is the commit.** Each load is one graph commit holding one
   `Revision`, so every fact traces to the git SHA and indexer version that
   produced it, and an old state stays readable.

## Quick start

Follow the shared [local setup](../README.md#local-setup) with cookbook
`code-graph` and graph ID `code`. It loads `seed.jsonl`, the base revision, onto
`main`. Merge this cookbook's `omnigraph-config.example.yaml` into your
operator config, then explore:

```bash
omnigraph alias revision
omnigraph alias symbol --params '{"name":"add"}'
omnigraph alias implementers --params '{"symbol":"src/`router.ts`/Router#add()."}'
omnigraph alias hubs
omnigraph alias impact --params '{"symbol":"src/`router.ts`/Router#add()."}'
```

`symbols_named` (alias `symbol`) is where to start: it returns each match's key
for the other reads. Keys contain backticks, so quote them in single quotes
in a shell.

## Index a pull request

`examples/pr-5267.jsonl` is the PR's revision. In practice CI writes such a file
for each pull request; here the agent role plays the indexer. `act-agent` may
open a branch and write on it but not on `main`, so a person merges.

```bash
COOKBOOK=$PWD/code-graph
omnigraph load --target local-agent --graph code --data "$COOKBOOK/examples/pr-5267.jsonl" \
  --from main --branch pr-5267 --mode overwrite --yes --json
omnigraph branch diff pr-5267 --target local-reader --graph code --json
```

Load every revision with `--mode overwrite`. It replaces each type the file
contains, so a symbol or reference the PR deleted disappears from the branch;
`merge` would keep it. The converter writes every type into every file, and
refuses to build the cookbook's files otherwise, because a type missing from an
`overwrite` file keeps its old rows.

The diff for PR #5267 has 88 changes:

| Change | Count | Meaning |
|---|---|---|
| `Symbol` insert | 2 | the new `src/router/utils.ts` and its `createNullObject` |
| `Symbol` update | 5 | the methods whose code changed: `RegExpRouter`'s constructor, `add`, `buildAllMatchers` and `#buildMatcher`, and trie-router `Node#pushHandlerSets` |
| `References` insert | 16 | code that now names `createNullObject` |
| `MemberOf`, `DefinedAt`, `Location` insert | 1, 2, 2 | the new symbols' structure |
| `Location` update | 58 | definitions that only moved |
| `Revision` delete and insert | 1 each | the indexed commit |

Query the branch before merging, then merge as a person and retire the branch:

```bash
omnigraph alias callers --params '{"symbol":"src/router/`utils.ts`/createNullObject."}'   # main: none yet
omnigraph query callers --target local-reader --graph code --branch pr-5267 \
  --params '{"symbol":"src/router/`utils.ts`/createNullObject."}'                            # 12 definitions
omnigraph branch merge pr-5267 --into main --target local-writer --graph code --json
omnigraph branch delete pr-5267 --target local-writer --graph code --yes --json
```

The commit `main` had before the merge stays readable: pass its
`graph_commit_id` from `omnigraph commit list` to any read as `--snapshot`.

## The cg client

`client/cg` wraps these steps, and needs only Python 3 and the `omnigraph`
CLI. It reads through the stored queries and writes only by loading a
revision with `--mode overwrite`. It takes its target from `CG_TARGET` or
`--target` (a server target name or a local graph path) and the graph from
`CG_GRAPH` (default `code`); a server target owns the token.

| Command | What it does |
|---|---|
| `cg find NAME` | the keys of the symbols with that name |
| `cg callers SYMBOL` | also `callees`, `impact`, `implementers` and `members`; SYMBOL is a key or a name that matches one symbol, `--path` narrows a name, `--branch` reads a branch |
| `cg hubs`, `cg unreferenced`, `cg revision` | the most referenced symbols, unreferenced callables, the indexed commit |
| `cg load FILE --branch B` | load a revision file, creating `B` from `--base` (default `main`) when it does not exist |
| `cg index [CHECKOUT] --branch B` | index a TypeScript checkout, convert it and load it, in one step |
| `cg diff B` | the branch diff as a review: symbols added, removed and changed, references added and removed per caller, definitions that only moved; `--markdown` for a pull request comment |

Add `--json` to any command for machine output. A refused write exits 1 and
changed nothing; an ambiguous name exits 2 and lists the candidates; a write
whose outcome is unknown exits 3, so check the branch before loading again.

```bash
export CG_TARGET=local-agent
code-graph/client/cg load code-graph/examples/pr-5267.jsonl --branch pr-5267
CG_TARGET=local-reader code-graph/client/cg diff pr-5267
```

```text
pr-5267 against main, revision a10592f3..4b44abe1: 2 symbols added, 0 removed, 5 changed; 16 references added, 0 removed, 0 changed; 53 definitions only moved.

Added:
  src/router/utils.ts (module)
  src/router/utils.ts:createNullObject (constant)

Changed:
  src/router/reg-exp-router/router.ts:RegExpRouter.#buildMatcher() (method): code changed
  ...
References added:
  src/router/reg-exp-router/router.ts:RegExpRouter.add() now calls src/router/utils.ts:createNullObject
  ...
```

The five methods that also moved count as changed, so 53 of the 58 moves
remain. In CI, one step per pull request indexes the head and posts the review:

```bash
export CG_TARGET=code-indexer CG_GRAPH=code          # an operator target for act-agent's token
code-graph/client/cg index . --branch "pr-$PR_NUMBER" --project tsconfig.json
code-graph/client/cg diff "pr-$PR_NUMBER" --markdown > review.md
gh pr comment "$PR_NUMBER" --body-file review.md
```

`cg index` runs scip-typescript from `CG_INDEXER`, the locked install in
`sources/indexer/node_modules` after `npm ci` there, or your `PATH`, and refuses
a checkout with uncommitted changes unless you pass `--allow-dirty`. The
client's tests run offline against captured diffs:
`python3 -m unittest discover -s code-graph/client/tests`.

## Index your own repository

The converter reads any TypeScript SCIP index. Index the repository with
[scip-typescript](https://github.com/sourcegraph/scip-typescript) and convert
the index; `--slice` keeps only the paths you name.

```bash
npx @sourcegraph/scip-typescript@0.6.2 index --output index.scip     # in your repository
python3 code-graph/sources/build_seed.py --index index.scip --checkout . \
  --revision "$(git rev-parse HEAD)" --repository https://example.com/repo.git --out graph.jsonl
```

Load the first revision onto `main` and each later one with `--mode overwrite`.
`append` and `merge` stage at most 8,192 rows per type in one load; `overwrite`
does not have that limit, and a 10,000-symbol graph loaded in one commit. A
file larger than about 32 MiB needs a different transport; see the engine's
[load limits](https://github.com/ModernRelay/omnigraph/blob/v0.14.0/docs/user/mutations/index.md#limits-and-conflicts).

SCIP indexers exist for Java, Kotlin, Scala, Rust, C, C++, Ruby, Python and C#.
The converter relies on the enclosing ranges an indexer emits to find each
reference's caller, and on scip-typescript's symbol kinds; it has been checked
only against scip-typescript.

## Rebuilding the seed

The seed is generated, never edited. `sources/source.json` pins the repository,
both commits and the slice; `sources/indexer/package-lock.json` pins the indexer
and the TypeScript compiler it runs.

```bash
python3 code-graph/sources/fetch.py            # clone, check out both commits, index them
python3 code-graph/sources/build_seed.py --check   # compare a fresh build with the committed files
python3 code-graph/sources/build_seed.py           # write seed.jsonl and examples/pr-5267.jsonl
```

`fetch.py` needs git, and Node.js 22.23.4 or later with npm; it refuses a
checkout that is not at its pinned commit and an indexer that is not the
pinned version. `build_seed.py` uses only the Python standard library. Both
write under `sources/work/`, which git ignores. CI does not run them; it
qualifies the committed files.

## Benchmarks

Measured on hono by the scripts in [`bench/`](bench/README.md), which has the
methods, the adjudication of every miss and the limits. They run by hand, not
in CI.

**Pull request diffs.** The 40 most recent hono pull requests before
2026-11-01 that change `src/`, each loaded as its base and merge commit and
reviewed with `cg diff`. Scored against the difference of the converted files
(mechanics) and against two reference graphs built with the TypeScript
compiler API (accuracy):

| | Exact pull requests | Added | Removed | Changed | References added | References removed |
|---|---|---|---|---|---|---|
| Mechanics | 40 of 40 | 19 of 19 | 9 of 9 | 46 of 46 | 90 of 90 | 37 of 37 |
| Accuracy, precision | 36 of 40 | 1.000 | 0.667 | 0.935 | 1.000 | 0.865 |
| Accuracy, recall | | 1.000 | 1.000 | 0.956 | 1.000 | 0.970 |

**Execution recall against other code-graph tools.** hono's test suite, run
on an instrumented copy, made 906 distinct calls between definitions. Recall
is the share of them each graph contains:

| Graph | All 906 | Functions and methods (759) | Class-member calls (194) |
|---|---|---|---|
| Omnigraph, every reference (what `callers` returns) | 0.891 | 0.876 | 0.768 |
| Omnigraph, call edges only | 0.733 | 0.810 | 0.582 |
| codegraph 1.6.2 | 0.679 | 0.748 | 0.474 |
| Graphify 0.9.102 | 0.677 | 0.747 | 0.356 |
| GitNexus 1.6.12 | 0.642 | 0.705 | 0.351 |
| codebase-memory-mcp 0.12.1 | 0.626 | 0.685 | 0.206 |
| code-review-graph 2.3.9 | 0.602 | 0.718 | 0.397 |

Most of Omnigraph's lead comes from recording references, not only calls: a
getter runs when a property is read, and a function passed as a value runs
when the code it was passed to calls it. The rest is resolution. On calls to
top-level functions and uniquely named ones, the name-matching tools come
within a point of Omnigraph's call edges; they fall behind on method calls
and on names several definitions share, which need the receiver's type. The
benchmark measures recall only, on one repository.

**Agent cost.** Claude Code with Sonnet 5.5 answered eight code-structure
questions about hono three times in each of seven arms: no code graph,
Omnigraph through `cg`, and the five tools above, each set up by its own Claude
Code installer. Medians per session, and the cost paired with no code graph
question by question:

| Arm | Exact answers | Cost | Wall time | Output tokens | Cost against no graph |
|---|---|---|---|---|---|
| No code graph | 24 of 24 | $0.100 | 16.1 s | 1,926 | |
| Omnigraph | 21 of 24 | $0.059 | 11.7 s | 1,018 | 0.77×, lower on 6 of 8 |
| codegraph | 24 of 24 | $0.094 | 17.6 s | 1,766 | 1.01× |
| Graphify | 21 of 24 | $0.100 | 16.0 s | 1,866 | 1.01× |
| GitNexus | 22 of 24 | $0.102 | 14.3 s | 1,368 | 0.97× |
| codebase-memory-mcp | 24 of 24 | $0.114 | 18.1 s | 2,016 | 1.14× |
| code-review-graph | 24 of 24 | $0.107 | 20.1 s | 1,931 | 1.33× |

Omnigraph's agents used their graph for half their tool calls, the others'
for at most 17%, and a `cg` read adds less to the context than the lines a
search returns. The gain is largest on names several definitions share: the
callers of `HonoRequest.header` cost $0.042 and 14.6 s with Omnigraph, against
$0.161 and 34.2 s without a graph. Its three inexact answers are one
question, a call made through a table of functions, which the compiler's
references do not record and the agents that read the code found. Indexing
hono takes Omnigraph 2.0 s, the tools 2.0 to 21.3 s.

## Limits

- **`call` is a text check.** A reference counts as a call when the next
  characters are `(`, a backtick, `?.(` or `<`. The indexer does not mark
  call sites.
- **Some code belongs to an outer definition.** scip-typescript gives class
  fields and nested anonymous functions no range of their own, so a reference
  in a field initializer belongs to the class, and one in a callback to the
  function around it. For the same reason a class field holding an arrow
  function has no `digest`, so a change to its code shows up only through
  its references and `signature`.
- **Members of union types are not indexed.** scip-typescript gives no symbol
  to a property of an object type inside a union, so turning a type into a
  union looks like removing its properties.
- **Callable constants come from their initializer or their type.**
  scip-typescript gives a constant or variable a range exactly when its
  initializer is a function, so one with a range is callable whatever its
  declared type, as in `const getCookie: GetCookie = (c) => {...}`. A property,
  or a constant holding another function (`const verify = Jwt.verify`), counts
  as callable when its type in the indexer's hover text is a function type. A
  function wrapped in a type assertion, `const C: FC = ((props) => {...}) as
  FC`, gets no range, so it is not callable, has no `digest`, and its code
  belongs to the module; hono has three of these among 413 function constants.
- **No export information.** `unreferenced_callables` lists entry points and
  public API next to unused code. In the seed, most of its rows are the
  routers' own `add` and `match` methods: callers reach them through the
  `Router` interface, so combine it with `implementers`.
- **The seed's slice cuts edges.** References into the router from code
  outside the slice are left out. `RegExpRouter`'s constructor looks
  unreferenced in the seed only because its caller, `Hono`'s constructor in
  `src/hono.ts`, is outside it; `new RegExpRouter()` names the constructor.

## Files

- `schema.pg` — the executable schema.
- `queries/code.gq` — the stored reads.
- `seed.jsonl` / `seed.md` — the base revision of the seed, and what it holds.
- `examples/pr-5267.jsonl` — the PR revision, for [indexing a pull request](#index-a-pull-request).
- `client/` — the [cg client](#the-cg-client) and its tests, with captured
  branch diffs as fixtures.
- `sources/` — `source.json` pins, `fetch.py`, `build_seed.py`, the SCIP reader
  `scip_index.py`, the converter's tests in `tests/`, and the locked indexer.
- `cluster.yaml`, `policies/` — the deployment: graph `code`, roles, the
  branch-only indexer.
- `bench/` — the [benchmarks](#benchmarks): scripts, the pinned sample and results.
- `omnigraph-config.example.yaml` — read aliases; merge into
  `$OMNIGRAPH_HOME/config.yaml`.
