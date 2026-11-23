# CLAUDE.md — code-graph

Scoped guidance for the `code-graph/` cookbook. Repo-wide conventions live in
`../CLAUDE.md`. For general Omnigraph operations — schema authoring, queries,
loading, branches, cluster commands, the CLI — use the **omnigraph** skill;
this file covers only what is specific to code-graph.

## What this is

A graph of one repository's definitions (`Symbol`) and the references between
them, one graph state per git revision, generated from a SCIP index. `main` is
the indexed default branch; each pull request is a branch holding its
revision, reviewed with `branch diff` and merged by a person. The one record
written by hand is `ReviewComment`, which notes that the call-graph review of
a revision was posted. The seed is real: hono's router at the parent of PR
#5267 (`seed.jsonl`) and at the PR (`examples/pr-5267.jsonl`). `seed.md` lists
what each read returns.

## Key files

- `schema.pg` — the executable schema. `Symbol` keys are SCIP descriptors
  without scheme, package or version.
- `queries/code.gq` — the stored reads; `queries/mutations.gq` — the one stored
  write, `record_review_comment`.
- `seed.jsonl`, `examples/pr-5267.jsonl` — generated; never edit them.
- `sources/` — `source.json` pins the repository, commits, slice and indexer;
  `fetch.py` checks out and indexes; `build_seed.py` converts; `scip_index.py`
  reads SCIP with the standard library; `indexer/` locks scip-typescript and
  the TypeScript parser `indexer/extents.mjs` reads definition ranges with.
  `tests/` holds the converter's rules for keys, callability, columns and
  reference owners; run them with
  `python3 -m unittest discover -s code-graph/sources/tests` after `npm ci` in
  `indexer/`. CI runs them.
- `client/cg` — the client: `cg_cli.py` holds the code, `tests/` its offline
  tests with captured branch diffs. It writes only through `cg load` and
  `cg index`, both `--mode overwrite`. Run the tests with
  `python3 -m unittest discover -s code-graph/client/tests`; the checker's
  code-graph journey also drives it against a served graph.
- `cluster.yaml` (graph `code`), `policies/`, `omnigraph-config.example.yaml`.

## Running it

Follow the shared [local setup](../docs/local-setup.md) with folder
`code-graph` and Graph ID `code`. It loads `seed.jsonl`, the base revision, onto
`main`. Merge this cookbook's `omnigraph-config.example.yaml` into your
operator config for the read aliases.

`symbols_named` (alias `symbol`) is where to start: it returns each match's key
for the other reads. Keys contain backticks, so quote them in single quotes in
a shell.

## Questions and their commands

The README's questions, with the parameters `site.json` gives them:

| Question | Command |
|---|---|
| Who calls this function? | ``omnigraph alias callers --params '{"symbol":"src/router/reg-exp-router/`matcher.ts`/match()."}'`` |
| What breaks if I change it? | ``omnigraph alias impact --params '{"symbol":"src/`router.ts`/Router#add()."}'`` |
| Which classes implement this interface method? | ``omnigraph alias implementers --params '{"symbol":"src/`router.ts`/Router#add()."}'`` |
| What does everything else depend on? | `omnigraph alias hubs` |

Without the aliases, name the stored read and its target:

```bash
omnigraph query callers --target local-reader --graph code \
  --params '{"symbol":"src/router/reg-exp-router/`matcher.ts`/match()."}' --json
omnigraph query revision --target local-reader --graph code --json
```

Add `--branch <b>` to read a pull request's branch, or `--snapshot <graph
commit id>` (from `omnigraph commit list`) to read an earlier state.

## Workflows, step by step

### Pull request indexing and the review comment

`examples/pr-5267.jsonl` is the PR's revision. In practice CI writes such a
file for each push to a pull request; here the agent role plays the indexer.
`act-agent` may open a branch and write on it but not on `main`, so a person
merges.

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
`overwrite` file keeps its old rows. `ReviewComment` is never in a revision
file, so the reviews recorded on a branch survive each new push.

The diff for PR #5267 has 90 changes:

| Change | Count | Meaning |
|---|---|---|
| `Symbol` insert | 2 | the new `src/router/utils.ts` and its `createNullObject` |
| `Symbol` update | 5 | the methods whose code changed: `RegExpRouter`'s constructor, `add`, `buildAllMatchers` and `#buildMatcher`, and trie-router `Node#pushHandlerSets` |
| `References` insert | 18 | code that now names `createNullObject` (14) or imports its module (4) |
| `MemberOf`, `DefinedAt`, `Location` insert | 1, 2, 2 | the new symbols' structure |
| `Location` update | 58 | definitions that moved; 53 of them only moved |
| `Revision` delete and insert | 1 each | the indexed commit |

In CI, one step per push indexes the head, posts the review once per commit and
records it on the branch:

```bash
export CG_TARGET=code-indexer CG_GRAPH=code          # an operator target for act-agent's token
SHA=$(git rev-parse HEAD)
code-graph/client/cg index . --branch "pr-$PR_NUMBER" --project tsconfig.json
posted=$(omnigraph query review_comment --target code-indexer --graph code --branch "pr-$PR_NUMBER" \
  --params "{\"sha\":\"$SHA\"}" --json | jq '.rows | length')
if [ "$posted" = 0 ]; then
  code-graph/client/cg diff "pr-$PR_NUMBER" --markdown > review.md
  url=$(gh pr comment "$PR_NUMBER" --body-file review.md)
  omnigraph mutate record_review_comment --target code-indexer --graph code --branch "pr-$PR_NUMBER" \
    --params "{\"sha\":\"$SHA\",\"pull_request\":\"$PR_URL\",\"url\":\"$url\",\"posted_at\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"}" --json
fi
```

The comment goes out through `gh` before the record notes it. If the
`record_review_comment` step fails, the next run posts the review again, so
check the pull request before rerunning by hand. A revision has one review:
recording it again replaces the record rather than adding a second.

Query the branch before merging, then merge as a person when the pull request
merges, and retire the branch:

```bash
omnigraph alias callers --params '{"symbol":"src/router/`utils.ts`/createNullObject."}'   # main: none yet
omnigraph query callers --target local-reader --graph code --branch pr-5267 \
  --params '{"symbol":"src/router/`utils.ts`/createNullObject."}' --json                     # 14 definitions
omnigraph branch merge pr-5267 --into main --target local-writer --graph code --json
omnigraph branch delete pr-5267 --target local-writer --graph code --yes --json
```

The commit `main` had before the merge stays readable: pass its
`graph_commit_id` from `omnigraph commit list` to any read as `--snapshot`.

### Repository onboarding

Index the default branch and load it onto `main` with the writer role, as
[Index your own repository](#index-your-own-repository) shows. `cg load` onto
`main` of a local graph runs `optimize` itself; on a served graph, stop the
server and run `omnigraph optimize` on the storage root. Check what `main`
holds with `omnigraph query revision --target local-reader --graph code`.

### Unused code review

`cg unreferenced` (stored read `unreferenced_callables`) lists the functions
and methods nothing in the indexed code refers to. Entry points and public API
show up next to unused code, and so does every member reached only through an
interface: check each method with `cg implementers` on the interface member it
implements, and hand the rest to a person to confirm. Nothing here deletes
code.

### Load-bearing code

`cg hubs` (`most_referenced`) lists the twenty definitions the most code refers
to; `cg callers` on one shows who depends on it. A pull request whose branch
diff changes one of these deserves a closer review.

### Impact check before an edit

Before changing a function, an agent finds its key with `cg find NAME`, reads
`cg impact KEY` (everything that reaches it within sixteen hops of references
and implementations) and, for an interface or base member, `cg implementers
KEY`. It plans the change with that list, or asks a person when the list is
long.

### Code context for an agent

`cg callers`, `cg callees`, `cg members` and `cg find` answer what an agent
would otherwise grep for, on `main` or with `--branch` on its own pull
request's branch. Every read is a stored read, so the agent needs only the
reader role.

### Release comparison

Find the graph commit `main` had at the release in `omnigraph commit list`,
then run the same read at it and now:

```bash
omnigraph query callers --target local-reader --graph code --snapshot <graph commit id> \
  --params '{"symbol":"..."}' --json
omnigraph query callers --target local-reader --graph code --params '{"symbol":"..."}' --json
```

`revision` at the same snapshot names the git commit it was indexed from.

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
| `cg load FILE --branch B` | load a revision file, creating `B` from `--base` (default `main`) when it does not exist; a load onto `main` of a local graph then builds its indexes |
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
pr-5267 against main, revision a10592f3..4b44abe1: 2 symbols added, 0 removed, 5 changed; 18 references added, 0 removed, 0 changed; 53 definitions only moved.

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

Every list read stops at a limit: 1,000 symbols for a name, 2,000 callers,
callees, members or unreferenced callables, and 5,000 definitions for
`impact`. A read that returns exactly its limit may be cut, and `cg` says so
(`"cut": true` in JSON). `--path` filters a name inside the query, so a name
with more definitions than the limit is still found in its directory.

A revision file over 32 MiB loads into a local graph with `write_max_bytes`
raised to its size, which holds its largest type in memory as one batch; a
server's load request is capped at 32 MiB, so `cg` refuses such a file for a
server target before sending anything. `impact` walks two edge types, which
the engine admits against every selected edge table's full row count on each
probe; on a local graph `cg` lifts that `traversal_work_limit` and raises
`query_memory_bytes` to 2 GiB. A server's stored query takes no session
settings, so on a large served graph raise `OMNIGRAPH_TRAVERSAL_WORK_LIMIT`
and `OMNIGRAPH_QUERY_MEMORY_BYTES` on the server instead.

An overwrite load writes every table without its indexes, and until
`omnigraph optimize` builds them a read scans whole tables. On VS Code's
818,000 symbols `cg members` took 19 s before and 0.06 s after, so `cg load`
onto `main` of a local graph runs `optimize` itself. `optimize` covers only
`main`: a branch created from an optimized `main` shares its indexes, but rows
loaded onto a branch later read without them until `omnigraph index build
--branch B` covers them. That costs little on a small repository and matters
on a large one.

`cg index` runs scip-typescript from `CG_INDEXER`, the locked install in
`sources/indexer/node_modules` after `npm ci` there, or your `PATH`; the
converter always needs that `npm ci`, for the TypeScript parser. It refuses a
checkout with uncommitted changes or untracked files unless you pass
`--allow-dirty`, since the indexer reads untracked files too.

## Index your own repository

The converter reads any TypeScript SCIP index. Index the repository with
[scip-typescript](https://github.com/sourcegraph/scip-typescript) and convert
the index; `--slice` keeps only the paths you name. The converter reads the
checkout's files again with the TypeScript parser, so run `npm ci` in
`code-graph/sources/indexer` first.

```bash
npx @sourcegraph/scip-typescript@0.6.2 index --output index.scip     # in your repository
python3 code-graph/sources/build_seed.py --index index.scip --checkout . \
  --revision "$(git rev-parse HEAD)" --repository https://example.com/repo.git --out graph.jsonl
```

Load the first revision onto `main` and each later one with `--mode overwrite`,
and run `omnigraph optimize` after each load onto `main`, as `cg load` does.
`append` and `merge` stage at most 8,192 rows per type in one load; `overwrite`
does not have that limit, and a 10,000-symbol graph loaded in one commit. A
file larger than about 32 MiB needs a different transport; see the engine's
[load limits](https://github.com/ModernRelay/omnigraph/blob/v0.15.0/docs/user/mutations/index.md#limits-and-conflicts).

SCIP indexers exist for Java, Kotlin, Scala, Rust, C, C++, Ruby, Python and C#.
The converter relies on the enclosing ranges an indexer emits to find each
reference's caller, on TypeScript's parser for the definitions scip-typescript
gives no range, and on scip-typescript's symbol kinds; it has been checked
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
pinned version. `build_seed.py` uses the Python standard library and runs
`sources/indexer/extents.mjs` with Node.js. Both write under `sources/work/`,
which git ignores. CI runs the converter's tests, not these scripts; it
qualifies the committed files. After a change to the seed, update `seed.md`
from the reads' actual output.

## Writing

- **The code graph is only written by loading generated revisions.** Do not
  `mutate` symbols or references by hand: the next load of that revision
  replaces them. The one stored write, `record_review_comment`, adds a
  `ReviewComment` and touches nothing the converter writes.
- **Every revision loads with `--mode overwrite`.** It replaces each type in
  the file, so deleted symbols and references leave the branch; `merge` would
  keep them. A type missing from the file keeps its old rows, which is why
  `build_seed.py` refuses to write the cookbook's files without every type.
  Against a server, `overwrite` needs `--yes`.
- **`act-agent` is the indexer.** It opens branches and writes on them only,
  which covers loading a revision and recording a review; `act-writer` merges
  into `main` and deletes branches.

## Query notes

- Keys contain backticks and dots: ``src/router/`utils.ts`/createNullObject.``.
  Find a key with `symbols_named` (`symbols_named_in` for a name with many
  definitions) or `file_symbols`, and pass it in single quotes in a shell.
- Every list read has a `limit`; `cg_cli.py` `LIMITS` mirrors them and its
  tests check the two agree. Change both together.
- A line number is on `Location` (`$s definedAt $l`), never on `Symbol`.
- `References` means "names", not "calls": filter on the bound edge's `call`
  for call sites (`$c $r:references $t`, then `$r.call`).
- Multi-hop reads work because every definition is one `Symbol` type; keep it
  that way rather than adding a node type per kind.
- `ImplementedBy` runs from an interface or base member to each member
  implementing it, the way a call through it goes, so `impact` can walk
  `(references | implementedBy)` forwards; GQ cannot reverse one member of a
  multi-hop alternation.
- Lint after every edit: `omnigraph lint --schema schema.pg --query
  queries/code.gq`, and the same for `queries/mutations.gq`.

## What it does not do

- **`call` is a text check.** A reference counts as a call when the next
  characters are `(`, a backtick, `?.(` or `<`. The indexer does not mark
  call sites.
- **A reference belongs to the innermost definition around it.**
  scip-typescript gives a range only to functions, classes, interfaces, enums,
  type aliases, methods, constructors and constants whose initializer is a
  function. The converter reads the range of every other constant and
  variable, class field, getter and setter with the TypeScript parser
  (`sources/indexer/extents.mjs`), so `cookie: detectFromCookie` in
  `const detectors = {...}` belongs to `detectors`, and the code of a getter
  to the getter, not to the module or class. A nested anonymous function and
  a property in an object literal have no symbol, so their code belongs to the
  definition around them; a destructuring declaration's code belongs to the
  module.
- **A call through a table is a reference to the table.** `detectors[name](c)`
  names `detectors`, and `detectors` names each function in it, so `impact`
  reaches the caller in two hops, and `callers` of a function in the table
  lists `detectors`, not the code that calls through it. Telling a call
  through the table from a read of its keys would need the type checker's
  data flow, which SCIP does not record.
- **A function handed to another is a reference, not a call.** VS Code's
  `invokeFunction(fn)` calls `fn` and `createInstance(C)` constructs a `C`,
  but neither name is followed by `(`, so `call` is false there. `callers`
  still lists the code that hands them over, and `impact` follows it.
- **A static and an instance member of one name are one definition.**
  scip-typescript gives `static equals` and `equals` in one class the same
  symbol, so the graph holds one `equals` with the references of both.
- **`impact` follows at most sixteen hops.** Omnigraph requires a finite
  bound on a multi-hop traversal. The longest chain of references and
  implementations to a callable in hono's `src/` is 14; a deeper chain is
  cut at sixteen.
- **On 0.15, `impact` from a hub can exceed any memory limit.** On VS Code a
  hub such as `ILogService` asks for more than `query_memory_bytes` allows, 2
  or 8 GiB, within half a second on an optimized graph, because each traversal
  step holds every batch of its edge probe until the step ends. OmniGraph
  0.16.0 streams the probe instead
  ([ModernRelay/omnigraph#1460](https://github.com/ModernRelay/omnigraph/pull/1460));
  this repository still pins 0.15.0. Targets away from the hubs answer in well
  under a second.
- **Members of union types are not indexed.** scip-typescript gives no symbol
  to a property of an object type inside a union, so turning a type into a
  union looks like removing its properties.
- **Callable constants come from their initializer or their type.** A
  constant, variable or class field whose initializer is a function, even
  behind a type assertion as in `const C: FC = ((props) => {...}) as FC`, is
  callable whatever its declared type. One holding another function
  (`const verify = Jwt.verify`), or a property declared without an
  initializer, counts as callable when its type in the indexer's hover text is
  a function type.
- **No export information.** `unreferenced_callables` lists entry points and
  public API next to unused code. In the seed, most of its rows are the
  routers' own `add` and `match` methods: callers reach them through the
  `Router` interface, so combine it with `implementers`.
- **The seed's slice cuts edges.** References into the router from code
  outside the slice are left out. `RegExpRouter`'s constructor looks
  unreferenced in the seed only because its caller, `Hono`'s constructor in
  `src/hono.ts`, is outside it; `new RegExpRouter()` names the constructor.
- **No connectors and no posting integration.** CI runs `cg`, and the review
  goes out through the agent's own tools, such as `gh`.

Omnigraph CLI/schema reference: [ModernRelay/omnigraph](https://github.com/ModernRelay/omnigraph).
