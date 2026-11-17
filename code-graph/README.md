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
   `Symbol` update in a diff means the code changed, and a move is a
   `Location` update you can filter out by type.
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

## Limits

- **`call` is a text check.** A reference counts as a call when the next
  characters are `(`, a backtick, `?.(` or `<`. The indexer does not mark
  call sites.
- **Some code belongs to an outer definition.** scip-typescript gives class
  fields and nested anonymous functions no range of their own, so a reference
  in a field initializer belongs to the class, and one in a callback to the
  function around it.
- **Callable constants come from the hover text.** A constant, variable or
  property counts as callable when its type in the indexer's hover text is a
  function type.
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
  `scip_index.py`, and the locked indexer.
- `cluster.yaml`, `policies/` — the deployment: graph `code`, roles, the
  branch-only indexer.
- `omnigraph-config.example.yaml` — read aliases; merge into
  `$OMNIGRAPH_HOME/config.yaml`.
