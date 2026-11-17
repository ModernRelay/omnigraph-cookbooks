# code-graph benchmarks

Three benchmarks for the claims this cookbook makes, all on
[hono](https://github.com/honojs/hono), TypeScript, MIT. They are run by hand,
not in CI, and write everything they fetch or build under `work/`, which git
ignores.

| Benchmark | Claim | Ground truth |
|---|---|---|
| [PR diff](#pr-diff) | A pull request's branch diff is exactly what it changed | Two reference graphs built with the TypeScript compiler API, at the base and the merge commit |
| [Execution recall](#execution-recall) | The graph contains the calls the code really makes | Calls recorded while hono's own test suite runs |
| [Agent cost](#agent-cost) | An agent with the graph answers code-structure questions for fewer tokens and less time | Eight questions with keys from the compiler reference, checked against the source |

The cookbook resolves references through scip-typescript, which runs the
TypeScript compiler. A compiler-built reference therefore cannot test the
cookbook's resolution, only its conversion and diffs: the PR-diff benchmark
uses one for that. The execution-recall benchmark's truth comes from running
code, not from the compiler, so it can compare Omnigraph, loaded with this
cookbook's graph, with other tools.

## Requirements

git, Python 3, Node.js 22.23.4 or later, bun (hono's tests), the locked
indexer (`npm ci` in `code-graph/sources/indexer`) and the 0.14.0 `omnigraph`
CLI. Every `omnigraph` call runs with its own `OMNIGRAPH_HOME` under `work/`.
The agent-cost benchmark also needs a signed-in `claude` (Claude Code), uv, and
the other tools installed as the execution-recall benchmark installed them.

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
| Mechanics | 40 of 40 | 19 of 19 | 9 of 9 | 48 of 48 | 91 of 91 | 40 of 40 |
| Accuracy, precision | 37 of 40 | 1.000 | 0.667 | 0.938 | 1.000 | 0.875 |
| Accuracy, recall | | 1.000 | 1.000 | 1.000 | 1.000 | 0.972 |

The three inexact pull requests, checked against their source diffs:

- **`8a103aa5`**: three updates the reference does not count are real
  changes. A constant's value changed, such as `ONLY_WILDCARD_REG_EXP_STR`
  from `".*"` to `"[^]*"`, and a field's type changed; the cookbook reports
  them through `signature`. The reference tracks code changes of callables only.
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
the initializer.

The agent-cost benchmark then found that a constant holding a table of
functions owned none of its references. scip-typescript gives such a constant,
a class field, a getter and a setter no range, so their code belonged to the
module or class around them, and `impact` could not follow `detectLanguage`
through `detectors` to `detectFromCookie`. The converter now reads those
ranges with the TypeScript parser, and the reference and the traces use the
same owners. That gave 47 definitions a digest (25 class fields, 13 getters
and 9 constants) and made 13 callable, among them `Context.json` and the other
fields of `Context` that hold arrow functions, so calls to them are now call
edges. It also caught two changes the first run missed: `17ad0e21` and
`e9c01079` change `Context.header` and `Factory.createApp`, class fields
holding arrow functions that had no digest. `17ad0e21` is now exact;
`e9c01079` still is not, for the union type above. Cached conversions and
references are keyed by a digest of the code that made them.

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
executed 915 distinct calls between hono's definitions.

Recall is the share of executed calls a graph contains. An edge the tests
never ran is not wrong, so this measures recall only. Every graph is mapped
into one identity space, `path:Container.member`; a tool's local helper
functions map to the definition that holds them, as the traces do. The tools
ran at their defaults, each on its own copy of the checkout with a scratch
home, telemetry off and no model keys: codegraph 1.6.2 (calls and instantiations),
codebase-memory-mcp 0.12.1, GitNexus 1.6.12, Graphify 0.9.102 (calls,
AST only) and code-review-graph 2.3.9.

Results, `results/recall.json`:

| Graph | All 915 | Functions and methods (768) | Constructors (54) | Getters and setters (93) |
|---|---|---|---|---|
| Compiler reference | 0.893 | 0.882 | 0.907 | 0.978 |
| Omnigraph, every reference | 0.895 | 0.882 | 0.907 | 1.000 |
| Omnigraph, every reference with `Implements` | 0.934 | | | |
| Omnigraph, call edges only | 0.779 | 0.865 | 0.907 | 0 |
| codegraph | 0.680 | 0.749 | 0.870 | 0 |
| Graphify | 0.679 | 0.749 | 0.852 | 0 |
| GitNexus | 0.625 | 0.684 | 0.870 | 0 |
| codebase-memory-mcp | 0.624 | 0.685 | 0.833 | 0 |
| code-review-graph | 0.597 | 0.711 | 0 | 0 |

"Every reference" is what the cookbook's reads on Omnigraph answer: `callers`,
`callees` and `impact` follow every `References` edge and report `call` as a column, not
a filter. "Call edges only" keeps the edges whose `call` is true. "With
`Implements`" adds a second read, `implementers`: a call through an interface
member also reaches the implementations the graph records.

The tools record calls, so the like-for-like column is functions and
methods, where Omnigraph's call edges find 0.865 and its references 0.882.
Getter calls are property reads: only a graph of references contains them. A
graph of every reference also holds more edges than a call graph, and this
benchmark does not count the edges the tests never ran.

### Where the difference comes from

Two things separate Omnigraph from the tools, and they are of different
kinds. The first is what is recorded. Omnigraph's references contain 819
executed calls and its call edges 713; the 106 between them are 93 getter
calls, which run when a property is read, and 13 calls to functions the code
passes as values. That is half of the gap between 0.895 and the tools' best,
0.680, and it is a choice of what to record more than better extraction.

The second is resolution. The tools find definitions by name; the graph
loaded into Omnigraph comes from the type checker, through scip-typescript.
Recall on calls to functions and methods, from `functions_by_call_shape` in
`results/recall.json`:

| Callee | Executed | Omnigraph calls | codegraph | Graphify | GitNexus | codebase-memory-mcp | code-review-graph |
|---|---|---|---|---|---|---|---|
| Top-level function | 569 | 0.896 | 0.842 | 0.880 | 0.810 | 0.847 | 0.824 |
| Class member | 199 | 0.774 | 0.482 | 0.372 | 0.322 | 0.221 | 0.387 |
| Name defined once | 513 | 0.955 | 0.864 | 0.918 | 0.823 | 0.860 | 0.842 |
| Name defined 4 or more times | 125 | 0.640 | 0.424 | 0.288 | 0.272 | 0.192 | 0.264 |

Where a name identifies its definition, the tools come close: Graphify is
within two to four points of Omnigraph. The gap opens where it does not: a method
call such as `c.req.header()` resolves to `HonoRequest.header` only if the
type of `c.req` is known, and hono defines `header` in several places. Of
the calls to a shared class-member name each tool missed, it recorded 14 to
26 as the caller calling another definition of that name.

The tools find 23 executed calls Omnigraph lacks, 13 of them codegraph's.
Most are calls dispatched to an override, which matching by name catches by
linking every method of that name.

The compiler reference misses 98 executed calls, about one in nine. 47 are
function values called indirectly: a function passed as an argument, stored
in a property or returned, then called by code that never names it. 44 are
calls dispatched to an override, such as `this.getHeaders()` in an abstract
class running a subclass's method; Omnigraph's `Implements` edges recover
most of these. The other seven reach constructors and getters.

## Agent cost

```bash
python3 code-graph/bench/agent.py setup    # one hono worktree per arm, set up by each tool's own installer
python3 code-graph/bench/agent.py index    # each tool's first index of a fresh checkout, three times
python3 code-graph/bench/agent.py run      # 8 questions, 7 arms, 3 sessions each
python3 code-graph/bench/agent.py score    # results/agent.json
```

The other two benchmarks measure the graph. This one measures what a coding
agent spends with it: the tokens, time and turns Claude Code 2.1.267 takes to
answer a question about hono's code structure, and whether the answer is
right. Seven arms get the same model (Sonnet 5.5), the same questions and the
same read and search tools: no code graph, Omnigraph with this cookbook's
graph, and the five tools of the execution-recall benchmark.

Each tool is set up by its own Claude Code installer: its MCP server, the
instructions it writes into CLAUDE.md, its skills, subagents and hooks. An
installer that writes to the home directory writes to a scratch one, and
setup moves what it wrote into the project, so a session loads the tool and
nothing of the user's. Omnigraph has no installer for a repository: its arm
reads a local graph through `cg`, with a CLAUDE.md section written for this
benchmark (`OMNIGRAPH_CLAUDE_MD` in `agent.py`). Every arm may use Read, Grep,
Glob, skills, subagents and, in the shell, grep, find, ls, cat, head, tail and
wc; an arm whose tool has a command line may also run it. A session loads
project settings only and its arm's MCP servers only, with auto-memory off.

The eight questions in `agent-questions.json` each ask for a set of
definitions: the callers of a method whose name six definitions share, of a
function constant and of a uniquely named function; the classes implementing
an interface; the overrides a call dispatches to; the users of a property; the
constructions of a class; and the callers through any chain of calls. Keys
come from the compiler reference and were checked against the source. Two
were corrected after the runs, and their `note` says why: one call is reached
through a table of functions, which the reference records as no call, and one
definition only assigns the property, which "use" may or may not include. An
answer is the JSON list on a session's last `ANSWER:` line, mapped to the
definitions the answer format names (a getter or field to its class, a
constant that holds no function to its file) and graded by F1.

Results, `results/agent.json`. The seven arms ran 168 sessions on
2026-11-16. After the converter fix that this benchmark prompted (see
[PR diff](#pr-diff)), the Omnigraph arm was rebuilt and ran its 24 sessions
again on 2026-11-17; `results/agent.json` holds that rerun, and the first run's
Omnigraph row is kept below for comparison. Medians per session; input tokens
include every cached read:

| Arm | Exact answers | Cost | Wall time | Input tokens | Output tokens | Turns | Calls to its tool |
|---|---|---|---|---|---|---|---|
| No code graph | 24 of 24 | $0.100 | 16.1 s | 198k | 1,926 | 6 | |
| Omnigraph, rerun after the fix | 24 of 24 | $0.069 | 18.6 s* | 153k | 1,198 | 5 | 48% |
| Omnigraph, first run | 21 of 24 | $0.059 | 11.7 s | 187k | 1,018 | 5 | 52% |
| codegraph | 24 of 24 | $0.094 | 17.6 s | 221k | 1,766 | 6 | 0% |
| Graphify | 21 of 24 | $0.100 | 16.0 s | 165k | 1,866 | 6 | 9% |
| GitNexus | 22 of 24 | $0.102 | 14.3 s | 207k | 1,368 | 5 | 17% |
| codebase-memory-mcp | 24 of 24 | $0.114 | 18.1 s | 207k | 2,016 | 6 | 1% |
| code-review-graph | 24 of 24 | $0.107 | 20.1 s | 225k | 1,931 | 6 | 7% |

\* Not comparable with the other rows. During the rerun the API wrote 69
output tokens a second, against 111 in the first run. Per question the rerun
took within two turns of the first run and wrote about as many output tokens,
but spent 13% to 109% longer waiting on the API. Cost moves with prompt caching too: a session that writes 25k tokens to
the cache costs about $0.13, one that writes 4k about $0.05, for the same
answer, and with three sessions per question the median can land on either.

The same sessions paired with no code graph, question by question: the
geometric mean over the eight questions of the ratio of the two arms' medians,
and on how many questions the arm spent less:

| Arm | Cost | Wall time | Output tokens | Turns |
|---|---|---|---|---|
| Omnigraph, rerun after the fix | 0.84×, 5 of 8 | not comparable | 0.75×, 5 of 8 | 0.95×, 4 of 8 |
| Omnigraph, first run | 0.77×, 6 of 8 | 0.88×, 4 of 8 | 0.70×, 6 of 8 | 0.86×, 5 of 8 |
| codegraph | 1.01×, 5 of 8 | 1.02×, 4 of 8 | 0.91×, 6 of 8 | 0.98×, 2 of 8 |
| Graphify | 1.01×, 4 of 8 | 1.03×, 3 of 8 | 0.99×, 5 of 8 | 0.94×, 4 of 8 |
| GitNexus | 0.97×, 4 of 8 | 1.01×, 3 of 8 | 0.81×, 6 of 8 | 0.87×, 4 of 8 |
| codebase-memory-mcp | 1.14×, 0 of 8 | 1.11×, 1 of 8 | 1.04×, 1 of 8 | 1.06×, 2 of 8 |
| code-review-graph | 1.33×, 2 of 8 | 1.15×, 1 of 8 | 0.95×, 5 of 8 | 1.08×, 2 of 8 |

Input tokens are mostly the same context read again on every turn, cheap from
the cache; cost follows what each turn adds and what the model writes. A `cg`
read returns the definitions as one table, where a text search returns lines
to read, so in the first run an Omnigraph session added a median 3.8k tokens
to its context against 9.8k to 14.4k for the other arms. The saving was
largest where names repeat: for the callers of `HonoRequest.header` an
Omnigraph session cost $0.042 and took 14.6 s, against $0.161 and 34.2 s
without a graph, and for the users of `HonoRequest.path` $0.048 and 12.7 s
against $0.094 and 20.9 s. On questions one text search answers, such as the
classes implementing `Router`, it cost a little more.

A tool also costs context before the question: a session without a graph
starts at 36.2k tokens, and the tools add 0.4k (Omnigraph), 0.6k (Graphify),
5.7k (codegraph), 9.4k (codebase-memory-mcp), 15.9k (code-review-graph) and
20.0k (GitNexus) of tool schemas, instructions and skills.

The agents with the other tools mostly searched text, calling their tool for
0 to 17% of their tool calls. codegraph delivers its graph through a hook that
adds context to every prompt, which needs no call; the context it gave for
`header` counted 2 callers of `HonoRequest.header` and 14 of `Context.header`,
which matching names produces, and its agents searched to check.

In the first run, Omnigraph's three inexact answers were the three sessions
of the transitive question: `detectLanguage` calls `detectFromCookie` through
the `detectors` table, the reference from the table to `detectFromCookie`
belonged to the module, and `impact` stopped after three hops on a five-hop
chain, so the agents that followed the graph stopped short of `detectLanguage`
and `languageDetector`. Agents that read the code found both. The converter
now gives the table its own references and `impact` follows sixteen hops; in
the rerun all three sessions answered exactly, each running `impact` and then
reading `language.ts` once to rule out `validateOptions`, which reads the
table's keys, and the `Detectors` type. Graphify and GitNexus missed the two
in two of three sessions, and one Graphify session missed `serveStatic`'s
chained `header` call.

Each tool's first index of a fresh checkout, median of three, from
`index_seconds_fresh` in `work/agent/ARM/setup.json`:

| Arm | Index time | Three runs |
|---|---|---|
| Omnigraph: scip-typescript, convert and load | 2.3 s | 2.2, 2.3, 2.3 |
| codebase-memory-mcp | 2.0 s | 2.0, 1.7, 2.0 |
| codegraph | 3.9 s | 4.2, 3.9, 3.9 |
| Graphify, without its LLM extraction | 4.3 s | 4.3, 4.0, 4.5 |
| code-review-graph | 5.8 s | 5.8, 5.8, 4.9 |
| GitNexus | 21.3 s | 23.0, 21.3, 20.3 |

## Limits

- One repository in one language. The ranking may differ elsewhere.
- The agent-cost benchmark ran one model, in one harness, three sessions per
  question and arm, with list prices. Omnigraph's instructions were written
  for it, the other tools' by their authors, and the keys come from the same
  compiler as Omnigraph's graph; every key was checked against the source.
- The reference shares the TypeScript compiler with scip-typescript, so the
  PR-diff accuracy measures conversion and modeling, not resolution.
- Execution recall covers only what hono's tests run, and the tracer skips
  two generators.
- Tools are mapped by file, name and line into the reference's identities; a
  tool's own node that the reference does not model counts as not found.
